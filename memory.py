"""
memory.py — 詞庫記憶與自動學習系統
模仿 Typeless 的 Personal Dictionary + Personalization Progress
"""
import difflib
import re
import threading
from datetime import datetime
from config import (
    load_dictionary, save_dictionary, load_history, save_history,
    BASE_CUSTOM_WORDS, BASE_CORRECTIONS, CASE_INSENSITIVE_CORRECTIONS,
    PROTECTED_CANONICAL_TERMS_BY_CASEFOLD,
)
from multilingual import language_profile


class Memory:
    def __init__(self):
        self.dictionary = load_dictionary()
        self.history = load_history()
        self._history_lock = threading.Lock()
        self._history_write_count = 0
        self._normalize_dictionary_schema()
        # 自動清理不合規的詞庫規則（避免壞規則堆積）
        self.cleanup_bad_corrections()

    def reload(self):
        self.dictionary = load_dictionary()
        self.history = load_history()
        self._normalize_dictionary_schema()
        self.cleanup_bad_corrections()

    def _normalize_dictionary_schema(self):
        """Migrate every historical custom-word shape into one flat schema.

        Previous versions alternated between top-level lists, a nested object, and a
        standalone ``custom_words`` list written by the promotion script.  Merge them
        without losing ordering, then persist once so all runtime/UI paths agree.
        """
        if not isinstance(self.dictionary, dict):
            self.dictionary = {}
        changed = False
        legacy = self.dictionary.pop("custom_words", None)
        if legacy is not None:
            changed = True

        manual = self.dictionary.get("manual_added", [])
        auto = self.dictionary.get("auto_added", [])
        if not isinstance(manual, list):
            manual = []
            changed = True
        if not isinstance(auto, list):
            auto = []
            changed = True

        legacy_manual = []
        legacy_auto = []
        if isinstance(legacy, dict):
            legacy_manual = legacy.get("manual_added", [])
            legacy_auto = legacy.get("auto_added", [])
        elif isinstance(legacy, list):
            legacy_manual = legacy

        def _merge_words(primary, extra):
            values = []
            seen = set()
            for word in [*primary, *(extra if isinstance(extra, list) else [])]:
                if not isinstance(word, str):
                    continue
                word = word.strip()
                if not word or word in seen:
                    continue
                seen.add(word)
                values.append(word)
            return values

        normalized_manual = _merge_words(manual, legacy_manual)
        normalized_auto = _merge_words(auto, legacy_auto)
        if normalized_manual != manual or normalized_auto != auto:
            changed = True
        self.dictionary["manual_added"] = normalized_manual
        self.dictionary["auto_added"] = normalized_auto
        for key, default in (
            ("corrections", {}),
            ("frequency", {}),
            ("corrections_by_scene", {}),
            ("corrections_by_app", {}),
        ):
            if not isinstance(self.dictionary.get(key), dict):
                self.dictionary[key] = default
                changed = True
            elif key not in self.dictionary:
                self.dictionary[key] = default
                changed = True
        if changed:
            save_dictionary(self.dictionary)

    def clear_all_in_memory(self):
        """v2.4.0：wipe_all GDPR Art. 17 後呼叫 — 把 process 內快取的 history / dictionary
        重置為空，避免後續寫入又把已刪資料 persistence 回磁碟。
        ⚠️ 此 method 只清 RAM，不碰磁碟（磁碟刪除由 caller 完成）。"""
        with self._history_lock:
            self.history = []
            self._history_write_count = 0
        # dictionary 重置為空骨架，使用者下次 add 從零開始
        # Dictionary runtime schema is intentionally flat.  Older wipe code created a
        # nested ``custom_words`` object even though every add/remove/UI path reads the
        # top-level lists, so words added after a wipe could silently disappear from the
        # active vocabulary.
        self.dictionary = {
            "manual_added": [],
            "auto_added": [],
            "corrections": {},
            "frequency": {},
            "corrections_by_scene": {},
            "corrections_by_app": {},
        }

    # ─── Whisper Prompt ──────────────────────────────────

    def build_whisper_prompt(self, custom_words, scene_words=None):
        """合併 config + 個人詞庫 + scene + BASE 詞彙後注入 Whisper prompt。
        ⚠️ 嚴格限制數量（≤20 詞）和長度（≤200 字元），
        否則 Whisper 會在短音訊/低音量時幻覺出字典詞彙。
        優先順序：使用者 config 詞彙 > 個人手動詞彙 > 場景詞彙 > 基礎詞庫。
        auto_added（73+ 個人名地名）不再注入 prompt，改由 corrections 機制處理。"""
        MAX_TERMS = 20   # 超過 20 個就容易讓 Whisper 過度「腦補」
        MAX_CHARS = 200  # prompt 太長 Whisper 會把 prompt 內容當成辨識結果
        # Dashboard 的「手動新增詞彙」存於 dictionary.manual_added。舊版只讀
        # config.custom_words，造成 UI 看得到、STT/LLM 卻完全沒使用。
        manual_words = self.dictionary.get("manual_added", [])
        if not isinstance(manual_words, list):
            manual_words = []

        # 優先順序：config > 個人手動 > 場景 > 基礎（不含 auto_added）
        seen = set()
        terms = []
        all_words = list(custom_words or []) + manual_words + (scene_words or []) + BASE_CUSTOM_WORDS
        for w in all_words:
            if not isinstance(w, str):
                continue
            w = w.strip()
            if not w or w in seen:
                continue
            candidate = ", ".join([*terms, w])
            # Never slice a term in half: a truncated brand/name is a particularly
            # harmful ASR bias.  Stop before the next complete term exceeds the cap.
            if len(candidate) > MAX_CHARS:
                continue
            seen.add(w)
            terms.append(w)
            if len(terms) >= MAX_TERMS:
                break
        if not terms:
            return ""
        return ", ".join(terms)

    # ─── Apply Corrections ───────────────────────────────

    def apply_corrections(self, text, scene_corrections=None, scene_key=None, app_id=None):
        """套用修正，多層合併（後者覆蓋前者）：
            BASE_CORRECTIONS  ← 程式碼基底
            corrections_by_scene[scene_key]  ← 使用者場景層
            scene_corrections  ← SCENE_PRESETS 內建（呼叫者傳入）
            corrections_by_app[app_id]  ← 使用者 App 層
            corrections (global)  ← 使用者全域層（最高優先）

        ⚠️ 自動學習路徑只能寫入 global `corrections`，per-scene / per-app 規則一律手動透過 UI/API。
        詳見 feedback memory: 詞庫嚴格控管。
        """
        merged = {**BASE_CORRECTIONS}
        if scene_key:
            merged.update(self.dictionary.get("corrections_by_scene", {}).get(scene_key, {}))
        if scene_corrections:
            merged.update(scene_corrections)
        if app_id:
            merged.update(self.dictionary.get("corrections_by_app", {}).get(app_id, {}))
        merged.update(self.dictionary.get("corrections", {}))
        result = text
        # 長詞優先，避免短詞先匹配破壞長詞
        for wrong, right in sorted(merged.items(), key=lambda x: -len(x[0])):
            # 舊版自動學習可能留下 LINE→line、Cloud→Claude 這類破壞正確品牌／
            # 技術詞的規則。canonical term 已經正確時，不允許任何層覆寫。
            canonical = PROTECTED_CANONICAL_TERMS_BY_CASEFOLD.get(wrong.casefold())
            if canonical is not None and right != canonical:
                continue
            if CASE_INSENSITIVE_CORRECTIONS:
                # 不分大小寫替換：用正則 re.IGNORECASE
                pattern = re.escape(wrong)
                # 純 ASCII 且頭尾是 word char 的規則套 word boundary，
                # 否則 "cloud"→"Claude" 會把 Cloudflare 改成 Claudeflare、
                # "Google Cloud Platform" 改成 "Google Claude Platform"。
                # CJK 規則維持子字串匹配（中日文無空白分詞，\b 不適用）。
                if wrong.isascii() and re.match(r"\w", wrong) and re.search(r"\w$", wrong):
                    pattern = r"\b" + pattern + r"\b"
                result = re.sub(pattern, right, result, flags=re.IGNORECASE)
            else:
                result = result.replace(wrong, right)
        return result

    # ─── 多層詞庫管理（手動 only，永不自動寫入）─────────────
    def add_scene_correction(self, scene_key, wrong, right):
        """手動新增場景級修正規則。⚠️ 不過守門員以外的自動寫入路徑都禁止呼叫這個。"""
        if not scene_key or not wrong or not right or wrong == right:
            return False
        if not self._is_meaningful_correction(wrong, right, source="manual-scene"):
            return False
        bucket = self.dictionary.setdefault("corrections_by_scene", {}).setdefault(scene_key, {})
        bucket[wrong] = right
        save_dictionary(self.dictionary)
        return True

    def remove_scene_correction(self, scene_key, wrong):
        bucket = self.dictionary.get("corrections_by_scene", {}).get(scene_key, {})
        if wrong in bucket:
            del bucket[wrong]
            save_dictionary(self.dictionary)
            return True
        return False

    def add_app_correction(self, app_id, wrong, right):
        if not app_id or not wrong or not right or wrong == right:
            return False
        if not self._is_meaningful_correction(wrong, right, source="manual-app"):
            return False
        bucket = self.dictionary.setdefault("corrections_by_app", {}).setdefault(app_id, {})
        bucket[wrong] = right
        save_dictionary(self.dictionary)
        return True

    def remove_app_correction(self, app_id, wrong):
        bucket = self.dictionary.get("corrections_by_app", {}).get(app_id, {})
        if wrong in bucket:
            del bucket[wrong]
            save_dictionary(self.dictionary)
            return True
        return False

    def get_scene_corrections(self, scene_key=None):
        d = self.dictionary.get("corrections_by_scene", {})
        return d.get(scene_key, {}) if scene_key else d

    def get_app_corrections(self, app_id=None):
        d = self.dictionary.get("corrections_by_app", {})
        return d.get(app_id, {}) if app_id else d

    # ─── Auto Learn ──────────────────────────────────────

    # ── 自動學習守門員（避免污染詞庫）─────────────────
    _PUNCT_RE = re.compile(r"[\s　-〿＀-￯，。、！？；：「」『』（）【】〈〉《》,.!?;:()\[\]{}\"'\\\\\n\r\t　]+")
    _KANA_RE = re.compile(r"[぀-ゟ゠-ヿ]")  # 平假名 + 片假名
    _KANJI_RE = re.compile(r"[一-鿿㐀-䶿]")
    _LATIN_RE = re.compile(r"[A-Za-z]")
    _LEARN_MAX_LEN = 20   # 單一規則最大字元數（防長段落整段對應）
    _LEARN_MIN_SIM = 0.45  # 相似度下限（防完全跨語意）

    def _is_pure_kana(self, s):
        """是否為純假名（不含漢字、不含拉丁字母）。"""
        return bool(self._KANA_RE.search(s)) and not self._KANJI_RE.search(s) and not self._LATIN_RE.search(s)

    def _is_transliteration(self, wrong, right):
        """跨字符系統的音譯：要求兩邊都是「純」單一字符系統（避免混合字元的 paraphrase）。
        合法：純假名↔純漢字、純假名↔純拉丁、純漢字↔純拉丁、純漢字↔純漢字（簡繁，需有共同字元）。
        例：クスリジャパン→KusuriJapan、ハイク→Haiku、医薬品→醫藥品。"""
        only_kana_w = bool(self._KANA_RE.search(wrong)) and not self._KANJI_RE.search(wrong) and not self._LATIN_RE.search(wrong)
        only_kana_r = bool(self._KANA_RE.search(right)) and not self._KANJI_RE.search(right) and not self._LATIN_RE.search(right)
        only_kanji_w = bool(self._KANJI_RE.search(wrong)) and not self._LATIN_RE.search(wrong) and not self._KANA_RE.search(wrong)
        only_kanji_r = bool(self._KANJI_RE.search(right)) and not self._LATIN_RE.search(right) and not self._KANA_RE.search(right)
        only_latin_w = bool(self._LATIN_RE.search(wrong)) and not self._KANJI_RE.search(wrong) and not self._KANA_RE.search(wrong)
        only_latin_r = bool(self._LATIN_RE.search(right)) and not self._KANJI_RE.search(right) and not self._KANA_RE.search(right)

        # 1) 純假名 ↔ 純拉丁（クスリジャパン→KusuriJapan）：假名邊 ≥3 字
        if (only_kana_w and only_latin_r and len(wrong) >= 3) or (only_latin_w and only_kana_r and len(right) >= 3):
            return True
        # 2) 純假名 ↔ 純漢字（しんぎほう→新義豊）：假名邊 ≥3 字
        if (only_kana_w and only_kanji_r and len(wrong) >= 3) or (only_kanji_w and only_kana_r and len(right) >= 3):
            return True
        # 3) 純漢字 ↔ 純拉丁（hakataeki minami→博多駅南）
        if (only_kanji_w and only_latin_r) or (only_latin_w and only_kanji_r):
            return True
        # 4) 純漢字 ↔ 純漢字（簡繁/異體字）：要求字元集合有交集
        if only_kanji_w and only_kanji_r:
            return len(set(wrong) & set(right)) >= 1
        return False

    def _is_meaningful_correction(self, wrong, right, source):
        """嚴格守門：避免把標點調整、長段落改寫、跨語意 paraphrase 學成 correction。
        對「跨字符系統音譯」（假名↔英文/漢字）放寬相似度檢查。"""
        if not wrong or not right or wrong == right:
            return False
        # 1. 含換行 / Tab → 拒絕（多行對應幾乎都是 paraphrase）
        if any(c in wrong + right for c in "\n\r\t"):
            return False
        # 2. 任一邊超過長度上限 → 拒絕（「ちは、Sawna.Darumas → なっております」這類）
        if len(wrong) > self._LEARN_MAX_LEN or len(right) > self._LEARN_MAX_LEN:
            return False
        # 3. 去掉所有標點/空白後相同 → 純標點調整，不學（防「？ → ，」）
        w_core = self._PUNCT_RE.sub("", wrong)
        r_core = self._PUNCT_RE.sub("", right)
        if w_core == r_core:
            return False
        if not w_core or not r_core:
            return False
        # 4. 跨字符系統音譯（假名↔英文/漢字、簡繁）→ 跳過相似度與長度比檢查
        if self._is_transliteration(w_core, r_core):
            return True
        # 5. 長度比 > 2.5 倍 → 拒絕
        shorter = min(len(w_core), len(r_core))
        longer = max(len(w_core), len(r_core))
        if longer / shorter > 2.5:
            return False
        # 6. 單字元 ↔ 多字元（非 ASCII）→ 通常是誤判，拒絕
        if (len(w_core) == 1 and len(r_core) >= 2 and not w_core.isascii()) or \
           (len(r_core) == 1 and len(w_core) >= 2 and not r_core.isascii()):
            return False
        # 7. 相似度過低 → 拒絕（ASCII 互換 0.42，其餘 0.45；防 compared drug→import）
        similarity = difflib.SequenceMatcher(None, w_core.lower(), r_core.lower()).ratio()
        both_ascii = w_core.isascii() and r_core.isascii()
        threshold = 0.42 if both_ascii else self._LEARN_MIN_SIM
        if similarity < threshold:
            return False
        return True

    def learn_correction(self, original, corrected, source="manual"):
        """從手動修正中自動學習。所有來源都套用嚴格守門，避免污染詞庫。"""
        if original.strip() == corrected.strip():
            return []

        learned = []
        # 將字串切分為：英文單字、空白、以及獨立的非英文/非空白字元（例如中日韓漢字）
        def tokenize(text):
            return re.findall(r'[a-zA-Z0-9_\'-]+|\s+|[^\sa-zA-Z0-9_\'-]', text)

        orig_words = tokenize(original)
        corr_words = tokenize(corrected)
        matcher = difflib.SequenceMatcher(None, orig_words, corr_words)

        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op != "replace":
                continue
            wrong = "".join(orig_words[i1:i2]).strip()
            right = "".join(corr_words[j1:j2]).strip()
            if not self._is_meaningful_correction(wrong, right, source):
                continue
            self.dictionary.setdefault("corrections", {})[wrong] = right
            freq = self.dictionary.setdefault("frequency", {})
            freq[wrong] = freq.get(wrong, 0) + 1
            learned.append({"wrong": wrong, "right": right})

        if learned:
            save_dictionary(self.dictionary)
        return learned

    def cleanup_bad_corrections(self):
        """清理現有 corrections 中不符合守門規則的條目（自動執行）。"""
        corr = self.dictionary.get("corrections", {})
        # 與 BASE_CORRECTIONS 重複的條目視為合法（基底有就不刪）
        base_keys = set(BASE_CORRECTIONS.keys())
        removed_count = 0
        for w, r in list(corr.items()):
            if w in base_keys:
                continue
            if not self._is_meaningful_correction(w, r, source="cleanup"):
                del corr[w]
                removed_count += 1
        if removed_count > 0:
            save_dictionary(self.dictionary)
            print(f" 🧹 已自動清理 {removed_count} 筆不合規的詞庫規則")
        return []

    def add_custom_word(self, word):
        """手動新增詞彙到詞庫"""
        manual = self.dictionary.setdefault("manual_added", [])
        if word not in manual:
            manual.append(word)
            save_dictionary(self.dictionary)
            return True
        return False

    def add_auto_word(self, word):
        """系統自動提取的詞彙"""
        auto = self.dictionary.setdefault("auto_added", [])
        if word not in auto:
            auto.append(word)
            save_dictionary(self.dictionary)
            return True
        return False

    def remove_custom_word(self, word):
        """刪除自訂詞彙（會檢查自動或手動）"""
        removed = False
        if word in self.dictionary.get("auto_added", []):
            self.dictionary["auto_added"].remove(word)
            removed = True
        if word in self.dictionary.setdefault("manual_added", []):
            self.dictionary["manual_added"].remove(word)
            removed = True
        
        if removed:
            save_dictionary(self.dictionary)
        return removed

    def add_correction(self, wrong, right, force=False):
        """新增 corrections 規則。預設過守門員防止偽規則（標點對應、跨語意 paraphrase 等）。
        force=True 才允許繞過守門員（僅供 CLI/測試使用，UI 路徑禁止傳 force）。
        回傳：True=已寫入，False=被守門員拒絕（rejected）。"""
        if not wrong or not right or wrong == right:
            return False
        if not force and not self._is_meaningful_correction(wrong, right, source="manual"):
            return False
        self.dictionary.setdefault("corrections", {})[wrong] = right
        save_dictionary(self.dictionary)
        return True

    def get_style_profile(self):
        """獲取用戶個人風格特徵描述（用於注入 Prompt）。
        ⚠️ 預設必須為空：舊版預設「偏好專業、精確且有禮貌的商務語氣」會在每一次
        dictate 請求中與 _DICTATE_SYSTEM 的逐字轉寫契約（NEVER paraphrase）正面衝突，
        是改寫型幻覺（→ 被 validator 丟棄 → fallback 連鎖 → 延遲上升）的系統性誘因。
        風格只能由使用者明確設定。"""
        return self.dictionary.get("style_profile", "")

    def update_style_profile(self, new_profile):
        """更新風格特徵描述"""
        self.dictionary["style_profile"] = new_profile
        save_dictionary(self.dictionary)

    def remove_correction(self, wrong):
        """刪除修正規則"""
        corrections = self.dictionary.get("corrections", {})
        if wrong in corrections:
            del corrections[wrong]
            save_dictionary(self.dictionary)
            return True
        return False

    def get_all_corrections(self):
        return self.dictionary.get("corrections", {})

    def get_all_custom_words(self):
        # 兼容原本寫法，返回全部
        return self.dictionary.get("auto_added", []) + self.dictionary.get("manual_added", [])

    def get_dictionary_words(self):
        """為 UI 返回區分來源的單字"""
        return {
            "auto_added": self.dictionary.get("auto_added", []),
            "manual_added": self.dictionary.get("manual_added", [])
        }

    # ─── Personalization Progress ────────────────────────

    def get_personalization_score(self):
        """計算個人化進度。改良版：總分難更上限，加入最近 7 天活躍度（持續使用會有成就感）。
        分項：詞庫 25 + 詞彙 20 + 累計使用 25 + 本週活躍 30 = 100"""
        from datetime import date, timedelta
        corrections_count = len(self.dictionary.get("corrections", {}))
        words_count = len(self.dictionary.get("auto_added", [])) + len(self.dictionary.get("manual_added", []))
        history_count = len(self.history)

        # 7 天活躍度統計
        today = date.today()
        days_iso = [(today - timedelta(days=i)).isoformat() for i in range(7)]
        days_set = set(days_iso)
        with self._history_lock:
            week_entries = [h for h in self.history if (h.get("timestamp", "") or "")[:10] in days_set]
        week_count = len(week_entries)
        week_chars = sum(len(h.get("final_text", "") or "") for h in week_entries)
        active_days = len({(h.get("timestamp", "") or "")[:10] for h in week_entries})

        # 分項評分（滿分難達到，但有持續使用能持續累積）
        # 詞庫：250 條滿分（每條 0.1 分，目前 115 條 = 11.5 分）
        dict_score = min(25.0, corrections_count * 0.1)
        # 詞彙：400 個滿分（每個 0.05 分）
        vocab_score = min(20.0, words_count * 0.05)
        # 累計使用：5000 次滿分（每次 0.005 分；之前 1000 次就滿，太容易）
        usage_score = min(25.0, history_count * 0.005)
        # 本週活躍：30 分上限。每活躍日 4 分（28 分）+ 字數量加成 (本週 ≥10000 字 +2 分)
        active_score = active_days * 4.0 + (2.0 if week_chars >= 10000 else 0.0)
        active_score = min(30.0, active_score)

        return {
            "total": min(100, int(dict_score + vocab_score + usage_score + active_score)),
            "dictionary_entries": corrections_count,
            "vocabulary_words": words_count,
            "total_dictations": history_count,
            "dict_score": int(dict_score),
            "dict_max": 25,
            "vocab_score": int(vocab_score),
            "vocab_max": 20,
            "usage_score": int(usage_score),
            "usage_max": 25,
            "active_score": int(active_score),
            "active_max": 30,
            "week_dictations": week_count,
            "week_chars": week_chars,
            "week_active_days": active_days,
        }

    # ─── History ─────────────────────────────────────────

    def add_to_history(self, entry):
        """新增歷史紀錄並立即原子落盤。

        history 是 verified few-shot 與人工修正的來源，不能再因常駐 App 未正常關閉而
        落後最多 9 筆。檔案只保留 2000 筆，逐筆寫入的 IO 成本可控。
        """
        with self._history_lock:
            self.history.append(entry)
            if len(self.history) > 2000:
                self.history = self.history[-2000:]
            try:
                save_history(self.history)
                self._history_write_count = 0
                return True
            except OSError:
                # 保留 RAM 內容並讓 shutdown flush 再試；history 寫入失敗不應拖垮轉寫。
                self._history_write_count += 1
                return False

    def flush_history(self):
        """強制寫入 history 到磁碟（程式結束前呼叫）"""
        with self._history_lock:
            if self._history_write_count > 0:
                save_history(self.history)
                self._history_write_count = 0

    def get_recent_context(self, n=5):
        """取得最近 N 筆辨識結果（供 Claude 上下文）"""
        with self._history_lock:
            recent = self.history[-n:] if self.history else []
        return [h.get("final_text", "") for h in recent]

    def get_few_shot_examples(
        self,
        n=3,
        min_chars=12,
        max_chars=240,
        current_text=None,
        verified_only=False,
    ):
        """取得個人化 few-shot 範例：whisper_raw → final_text。
        優先使用者手動編輯過的（edited=True），不足時 fallback 到 LLM 自動處理過的隱性正例對。
        範例會被當成 user/assistant 訊息對注入 LLM 的 messages 陣列。

        ``current_text`` 有值時只選相同語言 profile，避免把中文
        範例注入日文，或把 English/Kana code-switch 範例注入純中文。
        ``verified_only=True`` 時只使用者明確編輯過的範例，禁止模型用自己的未驗證
        輸出自我強化。"""
        with self._history_lock:
            items = list(reversed(self.history))  # 新→舊

        examples = []
        seen_raw = set()
        target_profile = language_profile(current_text) if current_text else None

        def _try_add(h):
            raw = (h.get("whisper_raw") or "").strip()
            fin = (h.get("final_text") or "").strip()
            # 只有逐字聽寫可當逐字聽寫範例；translate/edit/Email/SOAP/retry 的輸出本來
            # 就允許改寫，注入 dictate 會教模型翻譯或重組內容。
            if h.get("mode") not in {"dictate", "continuous"}:
                return False
            if not raw or not fin or raw == fin:
                return False
            if len(raw) < min_chars or len(raw) > max_chars:
                return False
            if len(fin) > max_chars:
                return False
            if target_profile is not None and language_profile(raw) != target_profile:
                return False
            # 即使 edited=True，raw→final 若跨語言（例如中譯英）也不可當 transcoder 範例。
            # 日文內部 Kana→Kanji 校正仍屬同一 profile，可安全保留。
            if language_profile(fin) != language_profile(raw):
                return False
            if raw in seen_raw:
                return False
            seen_raw.add(raw)
            examples.append((raw, fin))
            return True

        # Pass 1: 使用者明確編輯過的（最高品質）
        for h in items:
            if not h.get("edited"):
                continue
            _try_add(h)
            if len(examples) >= n:
                return examples

        if verified_only:
            return examples

        # Pass 2: LLM 自動處理過、使用者未編輯（隱性正例；僅 legacy opt-in）
        for h in items:
            if h.get("edited"):
                continue
            _try_add(h)
            if len(examples) >= n:
                return examples

        return examples

    def get_history(self, n=100, search=None):
        """取得歷史紀錄（支援搜尋）"""
        with self._history_lock:
            items = list(self.history)  # 拷貝快照，釋鎖後再過濾
        if search:
            search = search.lower()
            items = [h for h in items
                     if search in h.get("final_text", "").lower()
                     or search in h.get("whisper_raw", "").lower()]
        return list(reversed(items[-n:]))

    def update_history_item(self, timestamp, new_final_text, source="manual"):
        """持久化使用者確認過的修正，並回傳修改前文字。

        ``edited=True`` 是 verified few-shot 與安全 promotion 的唯一信任邊界；
        clipboard observer 也必須走這個方法，不能只改 RAM。
        """
        with self._history_lock:
            for h in self.history:
                if h.get("timestamp") == timestamp:
                    old_text = h.get("final_text", "")
                    h["final_text"] = new_final_text
                    h["edited"] = True
                    h["correction_source"] = str(source or "manual")
                    h["edited_at"] = datetime.now().isoformat()
                    save_history(self.history)
                    self._history_write_count = 0
                    return old_text
        return None

    def get_verified_example_count(self):
        """回傳可供個人化使用的人工確認逐字聽寫數量（不含 edit/translate）。"""
        with self._history_lock:
            return sum(
                1 for h in self.history
                if h.get("edited") and h.get("mode") in {"dictate", "continuous"}
                and (h.get("whisper_raw") or "").strip()
                and (h.get("final_text") or "").strip()
            )

    def delete_history_item(self, timestamp):
        """刪除單一歷史紀錄"""
        with self._history_lock:
            # 原地修改避免重新賦值 — 其他執行緒持有同一 list 參考才安全
            self.history[:] = [h for h in self.history if h.get("timestamp") != timestamp]
            save_history(self.history)
            self._history_write_count = 0

    def clear_history(self):
        with self._history_lock:
            self.history = []
            save_history(self.history)
            self._history_write_count = 0

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
    BASE_CUSTOM_WORDS, BASE_CORRECTIONS,
)


class Memory:
    def __init__(self):
        self.dictionary = load_dictionary()
        self.history = load_history()
        self._history_lock = threading.Lock()
        self._history_write_count = 0

    def reload(self):
        self.dictionary = load_dictionary()
        self.history = load_history()

    # ─── Whisper Prompt ──────────────────────────────────

    def build_whisper_prompt(self, custom_words, scene_words=None):
        """合併 custom_words + scene_words + BASE_CUSTOM_WORDS 去重後注入 Whisper prompt。
        ⚠️ 嚴格限制數量（≤20 詞）和長度（≤200 字元），
        否則 Whisper 會在短音訊/低音量時幻覺出字典詞彙。
        優先順序：使用者 config 詞彙 > 場景詞彙 > 基礎詞庫。
        auto_added（73+ 個人名地名）不再注入 prompt，改由 corrections 機制處理。"""
        MAX_TERMS = 20   # 超過 20 個就容易讓 Whisper 過度「腦補」
        MAX_CHARS = 200  # prompt 太長 Whisper 會把 prompt 內容當成辨識結果
        # 優先順序：使用者自訂 > 場景 > 基礎（不含 auto_added）
        seen = set()
        terms = []
        all_words = list(custom_words) + (scene_words or []) + BASE_CUSTOM_WORDS
        for w in all_words:
            if w not in seen:
                seen.add(w)
                terms.append(w)
            if len(terms) >= MAX_TERMS:
                break
        if not terms:
            return ""
        prompt = ", ".join(terms)
        return prompt[:MAX_CHARS]

    # ─── Apply Corrections ───────────────────────────────

    def apply_corrections(self, text, scene_corrections=None):
        """套用修正：基礎修正 + 場景修正 + 使用者自訂修正（使用者規則 > 場景規則 > 基底規則）"""
        merged = {**BASE_CORRECTIONS}
        if scene_corrections:
            merged.update(scene_corrections)
        merged.update(self.dictionary.get("corrections", {}))
        result = text
        for wrong, right in sorted(merged.items(), key=lambda x: -len(x[0])):
            result = result.replace(wrong, right)
        return result

    # ─── Auto Learn ──────────────────────────────────────

    def learn_correction(self, original, corrected):
        """從手動修正中自動學習"""
        if original.strip() == corrected.strip():
            return []

        learned = []
        # 將字串切分為：英文單字、空白、以及獨立的非英文/非空白字元（例如中日韓漢字）
        import re
        def tokenize(text):
            return re.findall(r'[a-zA-Z0-9_\'-]+|\s+|[^\sa-zA-Z0-9_\'-]', text)
        
        orig_words = tokenize(original)
        corr_words = tokenize(corrected)
        matcher = difflib.SequenceMatcher(None, orig_words, corr_words)

        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "replace":
                wrong = "".join(orig_words[i1:i2]).strip()
                right = "".join(corr_words[j1:j2]).strip()
                if wrong and right and wrong != right:
                    self.dictionary.setdefault("corrections", {})[wrong] = right
                    freq = self.dictionary.setdefault("frequency", {})
                    freq[wrong] = freq.get(wrong, 0) + 1
                    # 記錄正確詞到自動詞庫
                    auto = self.dictionary.setdefault("auto_added", [])
                    if right not in auto:
                        auto.append(right)
                    learned.append({"wrong": wrong, "right": right})

        save_dictionary(self.dictionary)
        return learned

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

    def add_correction(self, wrong, right):
        """手動新增修正規則"""
        self.dictionary.setdefault("corrections", {})[wrong] = right
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
        """計算個人化進度（模仿 Typeless）"""
        corrections_count = len(self.dictionary.get("corrections", {}))
        words_count = len(self.dictionary.get("auto_added", [])) + len(self.dictionary.get("manual_added", []))
        history_count = len(self.history)

        # 各項權重評分（滿分 100，調高門檻讓 100% 變難）
        # 需要 100 個 correction 才能滿 30 分
        dict_score = min(30.0, corrections_count * 0.3)
        # 需要 150 個 vocabulary 才能滿 30 分
        vocab_score = min(30.0, words_count * 0.2)
        # 需要 1000 次錄音才能滿 40 分
        usage_score = min(40.0, history_count * 0.04)

        return {
            "total": min(100, int(dict_score + vocab_score + usage_score)),
            "dictionary_entries": corrections_count,
            "vocabulary_words": words_count,
            "total_dictations": history_count,
            "dict_score": int(dict_score),
            "vocab_score": int(vocab_score),
            "usage_score": int(usage_score),
        }

    # ─── History ─────────────────────────────────────────

    def add_to_history(self, entry):
        """新增歷史紀錄（threading-safe，每 10 次完整寫入一次磁碟）"""
        with self._history_lock:
            self.history.append(entry)
            self._history_write_count += 1
            # 每 10 次完整寫入，減少大量 IO
            if self._history_write_count >= 10:
                save_history(self.history)
                self._history_write_count = 0

    def flush_history(self):
        """強制寫入 history 到磁碟（程式結束前呼叫）"""
        with self._history_lock:
            if self._history_write_count > 0:
                save_history(self.history)
                self._history_write_count = 0

    def get_recent_context(self, n=5):
        """取得最近 N 筆辨識結果（供 Claude 上下文）"""
        recent = self.history[-n:] if self.history else []
        return [h.get("final_text", "") for h in recent]

    def get_history(self, n=100, search=None):
        """取得歷史紀錄（支援搜尋）"""
        items = self.history
        if search:
            search = search.lower()
            items = [h for h in items
                     if search in h.get("final_text", "").lower()
                     or search in h.get("whisper_raw", "").lower()]
        return list(reversed(items[-n:]))

    def update_history_item(self, timestamp, new_final_text):
        """更新歷史紀錄的 final_text，並回傳原始文字（供 learn_correction 使用）"""
        with self._history_lock:
            for h in self.history:
                if h.get("timestamp") == timestamp:
                    old_text = h.get("final_text", "")
                    h["final_text"] = new_final_text
                    h["edited"] = True
                    save_history(self.history)
                    return old_text
        return None

    def delete_history_item(self, timestamp):
        """刪除單一歷史紀錄"""
        with self._history_lock:
            self.history = [h for h in self.history if h.get("timestamp") != timestamp]
            save_history(self.history)
            self._history_write_count = 0

    def clear_history(self):
        with self._history_lock:
            self.history = []
            save_history(self.history)
            self._history_write_count = 0

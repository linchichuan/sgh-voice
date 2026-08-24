"""
medical_dictionary.py — SGH Voice 醫療詞庫 Phase 1（科別／租戶分片 + 版本化 bundle）

實作範圍對應 docs/MEDICAL_DICTIONARY_ROADMAP.md（下稱「roadmap」）§10.2 Phase 1
（line 390-406），以及它依賴的資料模型／檢索／治理規則：
    §4   Layer 與資料模型（line 90-152）
    §5   Prompt 上限與資源配額（line 171-214）
    §6   檢索與快取策略（line 216-250）
    §7.2 審核狀態流程（line 272-283）
    §7.3 安全輸入檢查（line 285-293）
    §8.3 回滾（line 321-328）

⚠️ 明確不做（roadmap 本輪禁止或本模組刻意排除的範圍，見任務回報的逐條對照）：
    - 不做即時 server retrieval（roadmap §10.1 MVP／10.3 Phase 2 才討論；本模組純本機 bundle）。
    - 不做模糊 auto-replace；只有 exact alias 命中、且 status=active、
      risk_class=normal、auto_replace=true 才允許確定性替換（§6.2 步驟 3、§9.2）。
    - medication 類別一律禁止 auto_replace=true（§5.1：「medication 預設只做 canonical
      prompt bias，不啟用模糊 auto-replace」）。
    - ko-KR shard 因缺乏來源／reviewer，本輪不建立（§4.3、§10.2）。
    - 不從患者紀錄、通話錄音或使用者輸入自動學習詞彙寫回 bundle（§7.1、§10.2「只收集
      去識別的 term 命中、回改與效能指標」——本模組只提供 record_term_hit/record_term_revert
      供未來遙測管線呼叫，本身不寫回任何原始文字）。
    - 不新增 Dashboard 管理 UI；租戶/科別/reviewer 操作皆透過本模組的 Python API 呼叫
      （BundleStore 的 stage/activate/disable/revoke/rollback 方法），這是刻意的範圍縮減，
      理由見本次交付回報的取捨說明（未另建 CHANGELOG 條目）。

與現有 pipeline 的整合點（僅此，未改動 memory.py 既有演算法本身）：
    - transcriber.py 在 scene_key == "medical" 時，呼叫本模組的
      augment_scene_words() / augment_scene_corrections()，把 bundle 選出的詞彙／
      修正規則併入既有的 scene_words / scene_corrections，再交給
      memory.Memory.build_whisper_prompt() / apply_corrections()（現有、已測試的
      20 詞／200 字硬上限、長詞優先、ASCII word boundary 邏輯）把關，不重新發明這些規則。
    - medical_consultation（SOAP／edit 模式）與其他非 medical 場景完全不受影響
      （roadmap §2.3：「dictation、translation、edit／SOAP 三種任務不得混用詞庫行為」）。
"""
import copy
import json
import os
import re
import tempfile
import threading
import unicodedata

import config

SCHEMA_VERSION = 1

TERM_TYPES = {"exam", "department", "medication", "anatomy", "acronym", "organization"}
RISK_CLASSES = {"normal", "ambiguous", "high"}

# roadmap §7.2 審核狀態流程（line 274-277）
STATUS_PIPELINE = [
    "candidate",
    "source-verified",
    "language-reviewed",
    "domain-reviewed",
    "staged",
    "active",
    "deprecated",
    "revoked",
]
_STATUS_RANK = {name: i for i, name in enumerate(STATUS_PIPELINE)}

# §7.2：「candidate 不可進入 runtime」。staged 代表已通過 schema/來源檢查、
# 但尚未取得正式 domain reviewer 簽核，只允許影響風險較低的 prompt bias。
# deprecated/revoked 是終止狀態，不可因排序在 active 之後而重新進入 runtime。
PROMPT_RUNTIME_STATUSES = frozenset({"staged", "active"})
# §6.2：只有已核准 active 才允許確定性替換（比 prompt bias 風險更高）。
AUTO_REPLACE_RUNTIME_STATUSES = frozenset({"active"})

# §5.2 Bundle、索引與快取上限
MAX_ACTIVE_SHARDS_IN_MEMORY = 3
MAX_CANONICAL_TERMS_PER_SHARD = 5000
MAX_ALIASES_PER_SHARD = 10000

# §5.3：ASR 後 alias retrieval 最多回傳 50 個候選
POST_ASR_MAX_CANDIDATES = 50

# §5.1 配額表（line 186-192）。本模組只負責 tenant 與 specialty／common-medical
# 兩層；user-manual／pinned（8）與 base（2）由既有 dictionary.manual_added /
# BASE_CUSTOM_WORDS 承擔（見 memory.py:build_whisper_prompt 既有優先序），
# 這是本模組與既有程式碼邊界的明確取捨，記錄於任務回報。
TENANT_QUOTA = 4
SPECIALTY_COMMON_QUOTA = 6

# §5.1：「medication 預設只做 canonical prompt bias，不啟用模糊 auto-replace」
_HIGH_RISK_TERM_TYPES = {"medication"}

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class BundleValidationError(ValueError):
    """bundle 未通過 schema／安全輸入檢查（roadmap §4.2、§7.3）。"""


class BundleStateError(RuntimeError):
    """治理 state 損壞且沒有可驗證的 last-valid backup；整層必須 fail closed。"""


# ─── §7.3 安全輸入檢查 helpers ──────────────────────────────

def _valid_text(value, max_len=200):
    """空字串、控制字元、異常超長詞一律拒絕（§7.3 line 287-293）。"""
    if not isinstance(value, str):
        return False
    if not value.strip():
        return False
    if _CONTROL_CHAR_RE.search(value):
        return False
    if len(value) > max_len:
        return False
    return True


def validate_bundle(bundle):
    """驗證一個 bundle 是否符合 roadmap §4.2 schema 與 §7.3 安全輸入檢查。
    回傳錯誤字串 list；空 list 代表通過。"""
    errors = []
    if not isinstance(bundle, dict):
        return ["bundle must be a JSON object"]

    for field in ("schema_version", "bundle_version", "tenant_id", "specialty", "language", "terms"):
        if field not in bundle:
            errors.append(f"missing required field: {field}")

    if bundle.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {bundle.get('schema_version')!r}")

    for field in ("bundle_version", "tenant_id", "specialty", "language"):
        value = bundle.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")

    terms = bundle.get("terms")
    if not isinstance(terms, list):
        errors.append("terms must be a list")
        return errors
    if len(terms) > MAX_CANONICAL_TERMS_PER_SHARD:
        errors.append(f"too many terms: {len(terms)} > {MAX_CANONICAL_TERMS_PER_SHARD}")

    seen_ids = set()
    total_aliases = 0
    alias_to_canonical = {}
    for idx, term in enumerate(terms):
        prefix = f"terms[{idx}]"
        if not isinstance(term, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        term_id = term.get("term_id")
        if not isinstance(term_id, str) or not term_id.strip():
            errors.append(f"{prefix}: term_id must be a non-empty string")
        elif term_id in seen_ids:
            errors.append(f"{prefix}: duplicate term_id {term_id!r}")
        else:
            seen_ids.add(term_id)

        canonical = term.get("canonical")
        if not _valid_text(canonical, max_len=100):
            errors.append(f"{prefix}: canonical must be a non-empty, control-char-free string (<=100 chars)")

        aliases = term.get("aliases")
        if not isinstance(aliases, list) or not aliases:
            errors.append(f"{prefix}: aliases must be a non-empty list (§7.3 empty correction rejected)")
            aliases = []
        for alias in aliases:
            if not _valid_text(alias, max_len=100):
                errors.append(f"{prefix}: alias {alias!r} is invalid (empty/control-char/oversized)")
                continue
            if isinstance(canonical, str) and alias == canonical:
                errors.append(f"{prefix}: alias equals canonical ({alias!r}) — invalid correction (§7.3)")
                continue
            existing = alias_to_canonical.get(alias)
            if existing is not None and existing != canonical and term.get("risk_class") != "ambiguous":
                errors.append(
                    f"{prefix}: alias {alias!r} maps to multiple canonicals "
                    f"({existing!r} vs {canonical!r}) in this bundle but is not risk_class=ambiguous (§7.3, §4.1)"
                )
            alias_to_canonical[alias] = canonical
        total_aliases += len(aliases)

        if term.get("term_type") not in TERM_TYPES:
            errors.append(f"{prefix}: term_type must be one of {sorted(TERM_TYPES)}")
        if term.get("risk_class") not in RISK_CLASSES:
            errors.append(f"{prefix}: risk_class must be one of {sorted(RISK_CLASSES)}")

        status = term.get("status")
        if status not in _STATUS_RANK:
            errors.append(f"{prefix}: status must be one of {STATUS_PIPELINE}")
        elif status == "candidate":
            errors.append(f"{prefix}: status 'candidate' 不可進入 runtime bundle（§7.2）")

        if not term.get("source_ids"):
            errors.append(f"{prefix}: source_ids is required（§7.3 缺來源即拒絕）")
        if not term.get("reviewed_by"):
            errors.append(f"{prefix}: reviewed_by is required（§7.3 缺 reviewer 即拒絕）")
        if not term.get("languages"):
            errors.append(f"{prefix}: languages is required（§7.3 缺語言即拒絕）")

        if term.get("term_type") in _HIGH_RISK_TERM_TYPES and term.get("auto_replace") is True:
            errors.append(f"{prefix}: medication 類別禁止 auto_replace=true（§5.1）")
        if term.get("risk_class") in ("high", "ambiguous") and term.get("auto_replace") is True:
            errors.append(f"{prefix}: risk_class={term.get('risk_class')!r} 不得 auto_replace=true（§6.2）")

    if total_aliases > MAX_ALIASES_PER_SHARD:
        errors.append(f"too many aliases: {total_aliases} > {MAX_ALIASES_PER_SHARD}")

    return errors


# ─── shard key helpers（roadmap §4.3 line 156-160）──────────

def shard_key(tenant_id, specialty, language):
    return f"{tenant_id}/{specialty}/{language}"


def shard_key_with_version(tenant_id, specialty, language, version):
    return f"{shard_key(tenant_id, specialty, language)}@{version}"


def bundle_layer(bundle):
    """把一個 bundle 對應到 roadmap §4.1 的 layer 名稱（本模組只處理中間三層）。"""
    tenant_id = bundle.get("tenant_id")
    specialty = bundle.get("specialty")
    if tenant_id == "common" and specialty == "general-medical":
        return "common-medical"
    if tenant_id == "common":
        return "specialty"
    return "tenant"


def _safe_filename_part(value):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value))


def _find_alias_span(text, alias):
    """§6.2：ASCII alias 用 word boundary；CJK alias 用子字串匹配
    （中日文無空白分詞，\\b 不適用 —— 與 memory.py:apply_corrections 的既有規則一致）。"""
    if not alias:
        return None
    if alias.isascii() and re.match(r"\w", alias) and re.search(r"\w$", alias):
        m = re.search(r"\b" + re.escape(alias) + r"\b", text, flags=re.IGNORECASE)
        if m:
            return [m.start(), m.end()]
        return None
    idx = text.find(alias)
    if idx == -1:
        return None
    return [idx, idx + len(alias)]


class BundleStore:
    """本機版本化 medical dictionary bundle 的 staging / activate / rollback /
    term-disable / bundle-revoke / tenant isolation / LRU cache（roadmap §10.2、
    §6.3、§8.3）。純本機、無 server retrieval，符合 §10.1「使用本機版本化 bundle，
    不做即時 server retrieval」的延續要求。
    """

    def __init__(self, root=None):
        self._root = root  # None = 動態讀 config.DATA_DIR（見 _resolve_root）
        self._lock = threading.RLock()
        self._cache = {}        # shard_key@version -> bundle dict（LRU，見 §5.2/§6.3）
        self._cache_order = []  # 最近使用在尾端
        self._active_version = {}    # shard_key(無版本) -> 目前 active 的 bundle_version
        self._last_known_good = {}   # shard_key(無版本) -> last-known-good 版本（§6.3/§8.3）
        self._disabled_terms = {}    # shard_key(無版本) -> {term_id, ...}（單詞停用，§8.3）
        self._revoked_versions = {}  # shard_key(無版本) -> {version, ...}（整包撤回，§8.3）
        # 去識別化計數：term_id -> count。絕不保存原始 transcript（§6.3、§9.1 User revert rate）。
        self._hit_counts = {}
        self._loaded_state = False
        self._state_error = None
        self._state_loaded_from_backup = False

    # ---- paths（動態讀 config.DATA_DIR，尊重測試對它做的 monkeypatch）----

    def _resolve_root(self):
        if self._root:
            return self._root
        return os.path.join(config.DATA_DIR, "medical_dictionary")

    def _state_file(self):
        return os.path.join(self._resolve_root(), "state.json")

    def _state_backup_file(self):
        return os.path.join(self._resolve_root(), "state.last-valid.json")

    def _bundle_dir(self):
        return os.path.join(self._resolve_root(), "bundles")

    def _bundle_path(self, tenant_id, specialty, language, version):
        fname = "__".join(
            _safe_filename_part(part) for part in (tenant_id, specialty, language, version)
        ) + ".json"
        return os.path.join(self._bundle_dir(), fname)

    # ---- state persistence（tmp + os.replace 原子寫入，與 config.py 慣例一致）----

    @staticmethod
    def _validate_state_payload(raw):
        if not isinstance(raw, dict):
            raise BundleStateError("medical dictionary state must be a JSON object")

        required = {"active_version", "last_known_good", "disabled_terms", "revoked_versions"}
        if not required.issubset(raw):
            missing = sorted(required - set(raw))
            raise BundleStateError(f"medical dictionary state missing fields: {missing}")

        for field in ("active_version", "last_known_good"):
            value = raw.get(field)
            if not isinstance(value, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in value.items()
            ):
                raise BundleStateError(f"medical dictionary state field {field!r} is invalid")

        for field in ("disabled_terms", "revoked_versions"):
            value = raw.get(field)
            if not isinstance(value, dict) or not all(
                isinstance(k, str)
                and isinstance(v, list)
                and all(isinstance(item, str) for item in v)
                for k, v in value.items()
            ):
                raise BundleStateError(f"medical dictionary state field {field!r} is invalid")
        return raw

    @classmethod
    def _read_valid_state(cls, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls._validate_state_payload(json.load(f))
        except BundleStateError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise BundleStateError(f"unable to read medical dictionary state: {path}") from exc

    def _apply_state_payload(self, raw):
        self._active_version = dict(raw["active_version"])
        self._last_known_good = dict(raw["last_known_good"])
        self._disabled_terms = {k: set(v) for k, v in raw["disabled_terms"].items()}
        self._revoked_versions = {k: set(v) for k, v in raw["revoked_versions"].items()}

    def _ensure_state_loaded(self):
        if self._loaded_state:
            if self._state_error is not None:
                raise self._state_error
            return
        self._loaded_state = True
        path = self._state_file()
        backup_path = self._state_backup_file()
        if not os.path.exists(path) and not os.path.exists(backup_path):
            return

        try:
            raw = self._read_valid_state(path)
        except BundleStateError as primary_error:
            if not os.path.exists(backup_path):
                self._state_error = primary_error
                raise
            try:
                raw = self._read_valid_state(backup_path)
            except BundleStateError as backup_error:
                self._state_error = BundleStateError(
                    "medical dictionary primary state and last-valid backup are both unavailable"
                )
                raise self._state_error from backup_error
            self._state_loaded_from_backup = True
        self._apply_state_payload(raw)

    def _atomic_write_json(self, path, payload):
        parent = os.path.dirname(path) or "."
        os.makedirs(parent, mode=0o700, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=f".{os.path.basename(path)}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
            tmp_path = None
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _save_state(self):
        self._ensure_state_loaded()
        payload = {
            "active_version": self._active_version,
            "last_known_good": self._last_known_good,
            "disabled_terms": {k: sorted(v) for k, v in self._disabled_terms.items()},
            "revoked_versions": {k: sorted(v) for k, v in self._revoked_versions.items()},
        }
        self._atomic_write_json(self._state_file(), payload)
        self._atomic_write_json(self._state_backup_file(), payload)
        self._state_loaded_from_backup = False

    def get_state(self):
        with self._lock:
            self._ensure_state_loaded()
            return {
                "active_version": dict(self._active_version),
                "last_known_good": dict(self._last_known_good),
                "disabled_terms": {k: sorted(v) for k, v in self._disabled_terms.items()},
                "revoked_versions": {k: sorted(v) for k, v in self._revoked_versions.items()},
            }

    # ---- bundle on-disk persistence + in-memory LRU（§5.2/§6.3）----

    def _persist_bundle(self, bundle):
        path = self._bundle_path(bundle["tenant_id"], bundle["specialty"], bundle["language"], bundle["bundle_version"])
        self._atomic_write_json(path, bundle)

    def _delete_persisted_bundle(self, tenant_id, specialty, language, version):
        path = self._bundle_path(tenant_id, specialty, language, version)
        try:
            os.remove(path)
        except OSError:
            pass

    def _load_bundle_from_disk(self, tenant_id, specialty, language, version):
        path = self._bundle_path(tenant_id, specialty, language, version)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _put_cache(self, cache_key, bundle):
        if cache_key in self._cache:
            self._cache_order.remove(cache_key)
        self._cache[cache_key] = bundle
        self._cache_order.append(cache_key)
        while len(self._cache_order) > MAX_ACTIVE_SHARDS_IN_MEMORY:
            oldest = self._cache_order.pop(0)
            self._cache.pop(oldest, None)

    def _get_cached_or_load(self, tenant_id, specialty, language, version):
        cache_key = shard_key_with_version(tenant_id, specialty, language, version)
        if cache_key in self._cache:
            self._cache_order.remove(cache_key)
            self._cache_order.append(cache_key)
            return self._cache[cache_key]
        bundle = self._load_bundle_from_disk(tenant_id, specialty, language, version)
        if bundle is not None:
            self._put_cache(cache_key, bundle)
        return bundle

    # ---- staging / activation / rollback / revoke（§8.2、§8.3）----

    def stage_bundle(self, bundle):
        """驗證 + 寫入 staging（磁碟 + 記憶體 cache），不改變任何 shard 的 active pointer。"""
        errors = validate_bundle(bundle)
        if errors:
            raise BundleValidationError("; ".join(errors))
        key = shard_key(bundle["tenant_id"], bundle["specialty"], bundle["language"])
        version = bundle["bundle_version"]
        with self._lock:
            self._ensure_state_loaded()
            if version in self._revoked_versions.get(key, set()):
                raise BundleValidationError(f"bundle_version {version!r} is revoked for shard {key!r}")
            staged = copy.deepcopy(bundle)
            self._persist_bundle(staged)
            self._put_cache(shard_key_with_version(bundle["tenant_id"], bundle["specialty"], bundle["language"], version), staged)
        return key, version

    def activate_bundle(self, bundle):
        """驗證 → staging → 原子切換 runtime pointer。

        這個動作不會替 term 升格；staged term 仍只能做 prompt bias。要把 staged
        term 升為 active 並取得 deterministic replacement 資格，必須改走
        :meth:`promote_bundle`，由獨立 reviewer 留下 attestation。
        """
        key, version = self.stage_bundle(bundle)
        with self._lock:
            previous = self._active_version.get(key)
            if previous and previous != version:
                self._last_known_good[key] = previous
            self._active_version[key] = version
            self._save_state()
        return key, version

    def promote_bundle(
        self,
        tenant_id,
        specialty,
        language,
        version,
        *,
        reviewer_id,
        reviewed_at,
    ):
        """以獨立 reviewer attestation 將已 staged 的 bundle term 升格為 active。

        `pending-*` 佔位 reviewer、自我重複 reviewer、空白 reviewer／時間一律拒絕；
        升格後重新跑完整 schema/safety validation，再原子切換 runtime pointer。
        """
        reviewer = str(reviewer_id or "").strip()
        review_time = str(reviewed_at or "").strip()
        if not _valid_text(reviewer, max_len=120) or "pending" in reviewer.lower():
            raise BundleValidationError("independent reviewer_id is required for promotion")
        if not _valid_text(review_time, max_len=80):
            raise BundleValidationError("reviewed_at is required for promotion")

        key = shard_key(tenant_id, specialty, language)
        with self._lock:
            self._ensure_state_loaded()
            if version in self._revoked_versions.get(key, set()):
                raise BundleValidationError(f"bundle_version {version!r} is revoked for shard {key!r}")
            bundle = self._get_cached_or_load(tenant_id, specialty, language, version)
            if bundle is None:
                raise BundleValidationError(f"staged bundle {key!r}@{version!r} was not found")

            promoted = copy.deepcopy(bundle)
            for term in promoted.get("terms", []):
                current_status = term.get("status")
                if current_status != "staged":
                    raise BundleValidationError(
                        f"term {term.get('term_id')!r} must be staged before promotion"
                    )
                reviewers = list(term.get("reviewed_by") or [])
                if reviewer in reviewers:
                    raise BundleValidationError(
                        f"reviewer {reviewer!r} is not independent for term {term.get('term_id')!r}"
                    )
                reviewers.append(reviewer)
                term["reviewed_by"] = reviewers
                term["reviewed_at"] = review_time
                term["status"] = "active"

            errors = validate_bundle(promoted)
            if errors:
                raise BundleValidationError("; ".join(errors))

        return self.activate_bundle(promoted)

    def rollback(self, tenant_id, specialty, language):
        """§8.3：切回 last-known-good；純本機 state，離線可操作。回傳是否成功。"""
        key = shard_key(tenant_id, specialty, language)
        with self._lock:
            self._ensure_state_loaded()
            lkg = self._last_known_good.get(key)
            if not lkg:
                return False
            self._active_version[key] = lkg
            self._save_state()
            return True

    def revoke_bundle(self, tenant_id, specialty, language, version):
        """§8.3：整包撤回。清除記憶體 cache 與磁碟檔，禁止下次啟動重新載入；
        若被撤回的剛好是目前 active 版本，立即降級到 last-known-good（fail closed），
        沒有可用的 last-known-good 就直接停用該 shard（不留在 active）。"""
        key = shard_key(tenant_id, specialty, language)
        with self._lock:
            self._ensure_state_loaded()
            self._revoked_versions.setdefault(key, set()).add(version)
            cache_key = shard_key_with_version(tenant_id, specialty, language, version)
            self._cache.pop(cache_key, None)
            if cache_key in self._cache_order:
                self._cache_order.remove(cache_key)
            self._delete_persisted_bundle(tenant_id, specialty, language, version)
            if self._active_version.get(key) == version:
                fallback = self._last_known_good.get(key)
                if fallback and fallback != version and fallback not in self._revoked_versions.get(key, set()):
                    self._active_version[key] = fallback
                else:
                    self._active_version.pop(key, None)
            if self._last_known_good.get(key) == version:
                self._last_known_good.pop(key, None)
            self._save_state()

    def disable_term(self, tenant_id, specialty, language, term_id):
        """§8.3：單詞粒度緊急停用（比整包 revoke 更細）。"""
        key = shard_key(tenant_id, specialty, language)
        with self._lock:
            self._ensure_state_loaded()
            self._disabled_terms.setdefault(key, set()).add(term_id)
            self._save_state()

    def enable_term(self, tenant_id, specialty, language, term_id):
        key = shard_key(tenant_id, specialty, language)
        with self._lock:
            self._ensure_state_loaded()
            self._disabled_terms.get(key, set()).discard(term_id)
            self._save_state()

    def clear_tenant_cache(self, tenant_id):
        """§6.3：tenant 切換時清除上一租戶的記憶體 cache（隔離測試需證明無跨租戶命中）。"""
        with self._lock:
            drop = [k for k in self._cache if k.startswith(f"{tenant_id}/")]
            for k in drop:
                self._cache.pop(k, None)
                if k in self._cache_order:
                    self._cache_order.remove(k)

    # ---- 選字 / 檢索（§5.1、§6.1、§6.2）----

    def _collect_active_bundles(self, tenant_id, specialty):
        """回傳目前生效、且與呼叫端指定 tenant/specialty 相關的 bundle：
        永遠包含 common/general-medical；tenant_id 指定時額外納入該租戶 overlay；
        specialty 指定且非 general-medical 時額外納入該科別的 common shard。"""
        with self._lock:
            self._ensure_state_loaded()
            bundles = []
            for key, version in list(self._active_version.items()):
                t, s, l = key.split("/", 2)
                relevant = (
                    (t == "common" and s == "general-medical")
                    or (specialty and t == "common" and s == specialty)
                    or (tenant_id and t == tenant_id)
                )
                if not relevant:
                    continue
                bundle = self._get_cached_or_load(t, s, l, version)
                if bundle is not None:
                    bundles.append(bundle)
            return bundles

    def select_prompt_terms(self, languages=None, specialty="general-medical", tenant_id=None):
        """roadmap §5.1（line 184-193）：tenant 最多 4 詞、specialty／common-medical
        合計最多 6 詞，高優先層未用滿時名額往下流。回傳排序後的 canonical 詞 list。
        ⚠️ 這裡不重新定義 20 詞／200 字硬上限與「不可截斷單詞」規則——那是
        memory.Memory.build_whisper_prompt() 已經測試過的既有邏輯，呼叫端把這裡的
        輸出當成 scene_words 併入即可，避免兩處各自維護一份上限造成不同步。"""
        languages = set(languages or [])
        tenant_pool, specialty_pool = [], []
        for bundle in self._collect_active_bundles(tenant_id, specialty):
            layer = bundle_layer(bundle)
            pool = tenant_pool if layer == "tenant" else specialty_pool
            key = shard_key(bundle["tenant_id"], bundle["specialty"], bundle["language"])
            disabled = self._disabled_terms.get(key, set())
            for term in bundle.get("terms", []):
                if term.get("term_id") in disabled:
                    continue
                if term.get("status") not in PROMPT_RUNTIME_STATUSES:
                    continue
                if languages and not (set(term.get("languages", [])) & languages):
                    continue
                pool.append(term)
        tenant_pool.sort(key=lambda t: -int(t.get("priority", 0) or 0))
        specialty_pool.sort(key=lambda t: -int(t.get("priority", 0) or 0))

        selected, seen_canon = [], set()

        def take(pool, limit):
            taken = 0
            for term in pool:
                if taken >= limit:
                    break
                canonical = term.get("canonical")
                if canonical in seen_canon:
                    continue
                seen_canon.add(canonical)
                selected.append(canonical)
                taken += 1
            return taken

        used_tenant = take(tenant_pool, TENANT_QUOTA)
        # 名額往下流：tenant 沒用滿的名額流向 specialty/common-medical（§5.1 line 193）
        take(specialty_pool, SPECIALTY_COMMON_QUOTA + (TENANT_QUOTA - used_tenant))
        return selected

    def get_deterministic_corrections(self, tenant_id=None, specialty="general-medical", languages=None):
        """§6.2 步驟 3：只有 status=active、auto_replace=true、risk_class=normal，
        且該 alias 在目前生效 shards 中唯一對應同一 canonical 時，才回傳為確定性修正
        （wrong -> right dict，交給既有 memory.apply_corrections 執行實際替換）。
        任何違反上述任一條件的 alias 一律排除，不做模糊猜測（§6.2 步驟 5）。"""
        languages = set(languages or [])
        alias_map, ambiguous = {}, set()
        for bundle in self._collect_active_bundles(tenant_id, specialty):
            key = shard_key(bundle["tenant_id"], bundle["specialty"], bundle["language"])
            disabled = self._disabled_terms.get(key, set())
            for term in bundle.get("terms", []):
                if term.get("term_id") in disabled:
                    continue
                if term.get("status") not in AUTO_REPLACE_RUNTIME_STATUSES:
                    continue
                if not term.get("auto_replace"):
                    continue
                if term.get("risk_class") != "normal":
                    continue
                if languages and not (set(term.get("languages", [])) & languages):
                    continue
                canonical = term.get("canonical")
                for alias in term.get("aliases", []):
                    if alias in alias_map and alias_map[alias] != canonical:
                        ambiguous.add(alias)
                        continue
                    alias_map[alias] = canonical
        for alias in ambiguous:
            alias_map.pop(alias, None)
        return alias_map

    def find_candidates(self, text, tenant_id=None, specialty="general-medical", languages=None,
                         max_candidates=POST_ASR_MAX_CANDIDATES):
        """§6.2 步驟 1-2、§5.3：NFC normalize transcript，exact alias map 找候選，
        最多回傳 50 個候選（不論風險高低，都只是候選 —— 高風險／歧義詞只會出現在
        這裡，絕不會被 get_deterministic_corrections() 自動套用，§6.2 步驟 5）。"""
        normalized = unicodedata.normalize("NFC", text or "")
        languages = set(languages or [])
        alias_terms = []
        for bundle in self._collect_active_bundles(tenant_id, specialty):
            key = shard_key(bundle["tenant_id"], bundle["specialty"], bundle["language"])
            disabled = self._disabled_terms.get(key, set())
            for term in bundle.get("terms", []):
                if term.get("term_id") in disabled:
                    continue
                if term.get("status") not in PROMPT_RUNTIME_STATUSES:
                    continue
                if languages and not (set(term.get("languages", [])) & languages):
                    continue
                for alias in term.get("aliases", []):
                    alias_terms.append((alias, term))
        # 長詞優先，避免短別名先佔滿候選名額（與 memory.py 既有規則一致）
        alias_terms.sort(key=lambda pair: -len(pair[0]))

        candidates, seen = [], set()
        for alias, term in alias_terms:
            if len(candidates) >= max_candidates:
                break
            dedup_key = (alias, term.get("term_id"))
            if dedup_key in seen:
                continue
            span = _find_alias_span(normalized, alias)
            if span is None:
                continue
            seen.add(dedup_key)
            eligible = (
                term.get("auto_replace") is True
                and term.get("risk_class") == "normal"
                and term.get("status") in AUTO_REPLACE_RUNTIME_STATUSES
            )
            candidates.append({
                "term_id": term.get("term_id"),
                "canonical": term.get("canonical"),
                "alias": alias,
                "risk_class": term.get("risk_class"),
                "auto_replace_eligible": eligible,
                "span": span,
            })
        return candidates

    # ---- 去識別化遙測（§6.3、§9.1、§10.2）----

    def record_term_hit(self, term_id):
        """只記 term_id 計數，絕不接受或保存原始 transcript 文字。"""
        with self._lock:
            self._hit_counts[term_id] = self._hit_counts.get(term_id, 0) + 1

    def record_term_revert(self, term_id):
        with self._lock:
            rkey = f"revert:{term_id}"
            self._hit_counts[rkey] = self._hit_counts.get(rkey, 0) + 1

    def get_telemetry_snapshot(self):
        with self._lock:
            return dict(self._hit_counts)


# ─── module-level singleton + transcriber.py 整合點 ─────────

_default_store_lock = threading.Lock()
_default_store = None


def get_default_store():
    """process-wide 單例；第一次呼叫時嘗試載入內建 seed（fail-open，見 _bootstrap_seed）。"""
    global _default_store
    with _default_store_lock:
        if _default_store is None:
            _default_store = BundleStore()
            _bootstrap_seed(_default_store)
        return _default_store


def reset_default_store_for_tests():
    """僅供測試使用：清除 process-wide 單例，避免跨測試互相污染 in-memory 狀態。"""
    global _default_store
    with _default_store_lock:
        _default_store = None


def load_builtin_seed_bundles():
    """讀取隨 repo 附帶的 seed bundle（medical_dictionary_seed/*.json，排除 manifest_*）。
    這是 instruction 要求的「≤50 條、provenance: manually curated 2026-08-24,
    pending full list」種子集，見該目錄各檔案的 `_provenance` 欄位。"""
    seed_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medical_dictionary_seed")
    bundles = []
    if not os.path.isdir(seed_dir):
        return bundles
    for name in sorted(os.listdir(seed_dir)):
        if not name.endswith(".json") or name.startswith("manifest"):
            continue
        path = os.path.join(seed_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                bundles.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    return bundles


def _bootstrap_seed(store):
    """首次使用時，若 common/general-medical 尚未有任何 active bundle，
    自動載入內建 seed。Seed 全數 status='staged'（非 'active'），因此只會
    影響 prompt bias，絕不會觸發任何確定性替換（§7.2、§6.2 分層風險控制）。
    任何載入失敗都 fail-open：絕不能讓醫療詞庫問題拖垮既有辨識管線。"""
    try:
        state = store.get_state()
        already_active = any(
            key.startswith("common/general-medical/") for key in state["active_version"]
        )
        if already_active:
            return
        for bundle in load_builtin_seed_bundles():
            try:
                store.activate_bundle(bundle)
            except BundleValidationError:
                continue
    except Exception:
        pass


def augment_scene_words(scene_key, base_words, config_dict=None):
    """transcriber.py 的整合點：scene_key != 'medical' 時原樣回傳 base_words
    （medical_consultation/SOAP、一般場景完全不受影響）。config_dict 可傳入
    self.config 以支援 enable_medical_dictionary_bundles=False 的整層緊急停用
    （roadmap §8.3：「緊急停用應支援整個 medical layer」）。任何內部例外都
    fail-open 回傳 base_words 不變，符合任務「行為不破壞現有辨識管線」的要求。"""
    if scene_key != "medical":
        return list(base_words or [])
    if config_dict is not None and not config_dict.get("enable_medical_dictionary_bundles", True):
        return list(base_words or [])
    try:
        bundle_words = get_default_store().select_prompt_terms()
    except Exception:
        return list(base_words or [])
    merged = list(base_words or [])
    seen = set(merged)
    for w in bundle_words:
        if w not in seen:
            merged.append(w)
            seen.add(w)
    return merged


def augment_scene_corrections(scene_key, base_corrections, config_dict=None):
    """同上，套用到 apply_corrections() 的 scene_corrections 參數。bundle 規則
    只補既有場景規則沒涵蓋的 alias，不覆蓋既有已審核規則（setdefault 語意）。"""
    if scene_key != "medical":
        return base_corrections
    if config_dict is not None and not config_dict.get("enable_medical_dictionary_bundles", True):
        return base_corrections
    try:
        bundle_corrections = get_default_store().get_deterministic_corrections()
    except Exception:
        return base_corrections
    merged = dict(base_corrections or {})
    for wrong, right in bundle_corrections.items():
        merged.setdefault(wrong, right)
    return merged

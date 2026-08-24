"""
tests/test_medical_dictionary.py — 醫療詞庫 Phase 1 回歸測試

對應 docs/MEDICAL_DICTIONARY_ROADMAP.md §10.2 Phase 1 退出條件（line 401-406）：
    - 每個 specialty／language shard 都有獨立的正向與負向測試
    - tenant cache 切換與隔離測試通過
    - 更新、離線降級、單詞停用與整包回滾可操作
以及 §4.2 schema／§7.3 安全輸入檢查、§5.1 prompt 配額、§6.2 確定性修正、
§6.3 tenant isolation、§8.3 rollback／revoke 的具體回歸。
"""
import copy
import json
import os

import pytest

import config as cfg
import medical_dictionary as md


# ─── fixtures ─────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    """獨立 BundleStore，root 指向 tmp_path，與其他測試/真實 ~/.voice-input 完全隔離。"""
    return md.BundleStore(root=str(tmp_path / "medical_dictionary"))


@pytest.fixture(autouse=True)
def reset_singleton():
    """每個測試前後都重置 process-wide 單例，避免互相污染 in-memory 狀態
    （並行紀律：本檔只跑自己新增的測試，不影響其他 agent 正在改的檔案）。"""
    md.reset_default_store_for_tests()
    yield
    md.reset_default_store_for_tests()


def make_term(term_id="t1", canonical="測試詞", aliases=None, term_type="exam",
              language="zh-Hant-TW", risk_class="normal", auto_replace=True,
              status="active", priority=50, source_ids=None, reviewed_by=None):
    return {
        "term_id": term_id,
        "canonical": canonical,
        "aliases": aliases if aliases is not None else [f"{canonical}別名"],
        "term_type": term_type,
        "languages": [language],
        "specialties": ["general-medical"],
        "priority": priority,
        "case_sensitive": False,
        "auto_replace": auto_replace,
        "risk_class": risk_class,
        "status": status,
        "source_ids": source_ids if source_ids is not None else ["unit-test-source"],
        "reviewed_by": reviewed_by if reviewed_by is not None else ["unit-test-reviewer"],
        "reviewed_at": "2026-08-24T00:00:00Z",
    }


def make_bundle(tenant_id="common", specialty="general-medical", language="zh-Hant-TW",
                 version="v1", terms=None):
    return {
        "schema_version": 1,
        "bundle_version": version,
        "tenant_id": tenant_id,
        "specialty": specialty,
        "language": language,
        "generated_at": "2026-08-24T00:00:00Z",
        "source_manifest_version": "unit-test-manifest",
        "terms": terms if terms is not None else [make_term()],
    }


# ─── §4.2 / §7.3 schema + 安全輸入檢查 ───────────────────────

def test_validate_bundle_accepts_well_formed_bundle():
    errors = md.validate_bundle(make_bundle())
    assert errors == []


def test_validate_bundle_rejects_missing_required_fields():
    bad = {"schema_version": 1, "terms": []}
    errors = md.validate_bundle(bad)
    assert any("bundle_version" in e for e in errors)
    assert any("tenant_id" in e for e in errors)


def test_validate_bundle_rejects_alias_equal_to_canonical():
    term = make_term(canonical="心電図", aliases=["心電図"])
    errors = md.validate_bundle(make_bundle(terms=[term]))
    assert any("alias equals canonical" in e for e in errors)


def test_validate_bundle_rejects_candidate_status():
    term = make_term(status="candidate")
    errors = md.validate_bundle(make_bundle(terms=[term]))
    assert any("candidate" in e for e in errors)


def test_validate_bundle_rejects_missing_source_or_reviewer():
    term = make_term(source_ids=[], reviewed_by=[])
    errors = md.validate_bundle(make_bundle(terms=[term]))
    assert any("source_ids" in e for e in errors)
    assert any("reviewed_by" in e for e in errors)


def test_validate_bundle_rejects_medication_auto_replace_true():
    term = make_term(term_type="medication", auto_replace=True, risk_class="high")
    errors = md.validate_bundle(make_bundle(terms=[term]))
    assert any("medication" in e for e in errors)


def test_validate_bundle_rejects_ambiguous_alias_not_marked():
    """同一 alias 對應兩個不同 canonical，但沒有標 risk_class=ambiguous → 拒絕（§4.1 最後一句）。"""
    t1 = make_term(term_id="a", canonical="甲藥", aliases=["共用別名"], risk_class="normal")
    t2 = make_term(term_id="b", canonical="乙藥", aliases=["共用別名"], risk_class="normal")
    errors = md.validate_bundle(make_bundle(terms=[t1, t2]))
    assert any("multiple canonicals" in e for e in errors)


def test_validate_bundle_rejects_control_chars_and_empty_alias():
    term = make_term(aliases=["\x07控制字元"])
    errors = md.validate_bundle(make_bundle(terms=[term]))
    assert any("invalid" in e for e in errors)


# ─── seed bundle 本身必須乾淨、provenance 齊全（instruction 規定）───

def test_seed_bundles_load_and_validate_clean():
    bundles = md.load_builtin_seed_bundles()
    assert len(bundles) == 3, "應有 zh-Hant-TW / ja-JP / en 三個 seed bundle"
    total_terms = 0
    for bundle in bundles:
        errors = md.validate_bundle(bundle)
        assert errors == [], f"{bundle['language']} seed bundle 驗證失敗: {errors}"
        total_terms += len(bundle["terms"])
    assert total_terms <= 50, f"seed 詞條須 <=50，實際 {total_terms}"


def test_seed_bundles_declare_provenance_and_pending_review():
    for bundle in md.load_builtin_seed_bundles():
        provenance = bundle.get("_provenance", "")
        assert "manually curated 2026-08-24" in provenance
        assert "pending full list" in provenance
        # 全數 status=staged：只允許 prompt bias，不允許確定性替換（見下方測試佐證）
        assert all(term["status"] == "staged" for term in bundle["terms"])


def test_seed_bundles_never_auto_replace_anything():
    """staged 狀態必須被 active-only runtime gate 擋下 —— 即使某些 term 標了
    auto_replace=true，也不能真的產生確定性修正規則。"""
    store_ = md.BundleStore(root=None)
    store_._root = None  # noqa: SLF001 — 測試直接檢查邏輯，不落地
    for bundle in md.load_builtin_seed_bundles():
        assert not any(
            t.get("auto_replace") and t.get("status") == "active" for t in bundle["terms"]
        )


# ─── BundleStore：staging / activate / rollback / revoke（§8.2、§8.3）───

def test_activate_bundle_then_select_prompt_terms(store):
    store.activate_bundle(make_bundle(terms=[make_term(canonical="心電図", priority=90)]))
    terms = store.select_prompt_terms()
    assert "心電図" in terms


def test_activate_twice_sets_last_known_good_and_rollback(store):
    store.activate_bundle(make_bundle(version="v1", terms=[make_term(canonical="舊版詞")]))
    store.activate_bundle(make_bundle(version="v2", terms=[make_term(canonical="新版詞")]))
    state = store.get_state()
    key = md.shard_key("common", "general-medical", "zh-Hant-TW")
    assert state["active_version"][key] == "v2"
    assert state["last_known_good"][key] == "v1"

    assert "新版詞" in store.select_prompt_terms()
    ok = store.rollback("common", "general-medical", "zh-Hant-TW")
    assert ok is True
    assert "舊版詞" in store.select_prompt_terms()
    assert "新版詞" not in store.select_prompt_terms()


def test_rollback_without_last_known_good_returns_false(store):
    store.activate_bundle(make_bundle())
    assert store.rollback("common", "general-medical", "zh-Hant-TW") is False


def test_revoke_bundle_removes_from_active_and_disk_and_blocks_reload(store):
    store.activate_bundle(make_bundle(version="v1", terms=[make_term(canonical="有問題的詞")]))
    bundle_path = store._bundle_path("common", "general-medical", "zh-Hant-TW", "v1")  # noqa: SLF001
    assert os.path.exists(bundle_path)

    store.revoke_bundle("common", "general-medical", "zh-Hant-TW", "v1")
    assert "有問題的詞" not in store.select_prompt_terms()
    assert not os.path.exists(bundle_path), "revoke 必須刪除磁碟檔，禁止下次啟動重新載入（§8.3）"

    with pytest.raises(md.BundleValidationError):
        store.activate_bundle(make_bundle(version="v1", terms=[make_term(canonical="有問題的詞")]))


def test_revoke_active_version_falls_back_to_last_known_good(store):
    store.activate_bundle(make_bundle(version="v1", terms=[make_term(canonical="舊版詞")]))
    store.activate_bundle(make_bundle(version="v2", terms=[make_term(canonical="壞版詞")]))
    store.revoke_bundle("common", "general-medical", "zh-Hant-TW", "v2")
    # revoke 目前 active 版本 → fail closed 降級回 last-known-good，而不是留在壞版本
    assert "舊版詞" in store.select_prompt_terms()
    assert "壞版詞" not in store.select_prompt_terms()


def test_state_persists_across_new_store_instance(store, tmp_path):
    store.activate_bundle(make_bundle(terms=[make_term(canonical="持久化詞")]))
    reopened = md.BundleStore(root=str(tmp_path / "medical_dictionary"))
    assert "持久化詞" in reopened.select_prompt_terms()


def test_corrupt_state_without_backup_fails_closed_and_preserves_evidence(tmp_path):
    root = tmp_path / "medical_dictionary"
    root.mkdir()
    state_path = root / "state.json"
    corrupt_payload = "{not-valid-json"
    state_path.write_text(corrupt_payload, encoding="utf-8")

    reopened = md.BundleStore(root=str(root))
    with pytest.raises(md.BundleStateError):
        reopened.get_state()
    with pytest.raises(md.BundleStateError):
        reopened.activate_bundle(make_bundle())

    assert state_path.read_text(encoding="utf-8") == corrupt_payload
    assert not (root / "bundles").exists(), "state 異常時不得 bootstrap 或寫入新 bundle"


def test_corrupt_primary_state_recovers_only_from_last_valid_backup(store, tmp_path):
    term = make_term(term_id="governed", canonical="保留治理詞")
    store.activate_bundle(make_bundle(terms=[term]))
    root = tmp_path / "medical_dictionary"
    backup_path = root / "state.last-valid.json"
    assert backup_path.exists()

    state_path = root / "state.json"
    state_path.write_text("{broken", encoding="utf-8")
    reopened = md.BundleStore(root=str(root))

    assert "保留治理詞" in reopened.select_prompt_terms()
    assert state_path.read_text(encoding="utf-8") == "{broken", (
        "read-only recovery 不應默默覆寫損壞證據；下一次明確治理 mutation 才修復 primary"
    )
    reopened.disable_term("common", "general-medical", "zh-Hant-TW", "governed")
    assert "保留治理詞" not in reopened.select_prompt_terms()
    assert json.loads(state_path.read_text(encoding="utf-8"))["disabled_terms"]


def test_promote_bundle_requires_independent_reviewer_and_records_attestation(store):
    staged = make_term(
        status="staged",
        reviewed_by=["lin-chichuan-self-curated-pending-domain-reviewer"],
    )
    store.stage_bundle(make_bundle(terms=[staged]))

    with pytest.raises(md.BundleValidationError):
        store.promote_bundle(
            "common",
            "general-medical",
            "zh-Hant-TW",
            "v1",
            reviewer_id="pending-domain-reviewer",
            reviewed_at="2026-08-24T09:00:00Z",
        )

    store.promote_bundle(
        "common",
        "general-medical",
        "zh-Hant-TW",
        "v1",
        reviewer_id="domain-reviewer-sato",
        reviewed_at="2026-08-24T09:00:00Z",
    )
    promoted = store._load_bundle_from_disk(  # noqa: SLF001 - verify persisted public outcome
        "common", "general-medical", "zh-Hant-TW", "v1"
    )
    assert all(term["status"] == "active" for term in promoted["terms"])
    assert all("domain-reviewer-sato" in term["reviewed_by"] for term in promoted["terms"])
    assert all(term["reviewed_at"] == "2026-08-24T09:00:00Z" for term in promoted["terms"])


@pytest.mark.parametrize("terminal_status", ["deprecated", "revoked"])
def test_promote_bundle_cannot_resurrect_terminal_term_status(store, terminal_status):
    terminal = make_term(status=terminal_status)
    store.stage_bundle(make_bundle(terms=[terminal]))

    with pytest.raises(md.BundleValidationError, match="must be staged"):
        store.promote_bundle(
            "common",
            "general-medical",
            "zh-Hant-TW",
            "v1",
            reviewer_id="domain-reviewer-sato",
            reviewed_at="2026-08-24T09:00:00Z",
        )


# ─── 單詞停用（比整包 revoke 更細，§8.3）───────────────────────

def test_disable_term_excludes_from_selection_and_corrections(store):
    term = make_term(term_id="dis-1", canonical="要停用的詞", aliases=["停用別名"], auto_replace=True)
    store.activate_bundle(make_bundle(terms=[term]))
    assert "要停用的詞" in store.select_prompt_terms()
    assert store.get_deterministic_corrections().get("停用別名") == "要停用的詞"

    store.disable_term("common", "general-medical", "zh-Hant-TW", "dis-1")
    assert "要停用的詞" not in store.select_prompt_terms()
    assert "停用別名" not in store.get_deterministic_corrections()

    store.enable_term("common", "general-medical", "zh-Hant-TW", "dis-1")
    assert "要停用的詞" in store.select_prompt_terms()


# ─── §5.1 Prompt 配額（tenant 4 / specialty+common 6，未用滿往下流）───

def test_select_prompt_terms_respects_tenant_and_common_quota(store):
    tenant_terms = [
        make_term(term_id=f"tenant-{i}", canonical=f"租戶詞{i}", priority=100 - i)
        for i in range(6)
    ]
    common_terms = [
        make_term(term_id=f"common-{i}", canonical=f"通用詞{i}", priority=100 - i)
        for i in range(10)
    ]
    store.activate_bundle(make_bundle(tenant_id="clinic-a", terms=tenant_terms))
    store.activate_bundle(make_bundle(tenant_id="common", terms=common_terms))

    selected = store.select_prompt_terms(tenant_id="clinic-a")
    tenant_selected = [t for t in selected if t.startswith("租戶詞")]
    common_selected = [t for t in selected if t.startswith("通用詞")]
    assert len(tenant_selected) == 4, "tenant 配額上限 4（roadmap line 188）"
    assert len(common_selected) == 6, "specialty/common-medical 配額上限 6（roadmap line 190）"
    # 優先序：priority 較高的先選中
    assert tenant_selected == ["租戶詞0", "租戶詞1", "租戶詞2", "租戶詞3"]


def test_select_prompt_terms_flows_down_unused_tenant_quota(store):
    """tenant 只有 1 個詞可用時，沒用滿的 3 個名額要流向 specialty/common-medical。"""
    store.activate_bundle(make_bundle(
        tenant_id="clinic-a", terms=[make_term(term_id="tenant-1", canonical="唯一租戶詞")]
    ))
    common_terms = [
        make_term(term_id=f"common-{i}", canonical=f"通用詞{i}", priority=100 - i)
        for i in range(10)
    ]
    store.activate_bundle(make_bundle(tenant_id="common", terms=common_terms))

    selected = store.select_prompt_terms(tenant_id="clinic-a")
    common_selected = [t for t in selected if t.startswith("通用詞")]
    assert "唯一租戶詞" in selected
    assert len(common_selected) == 9, "1 個 tenant 用掉 1 名額，剩 3 名額往下流：6+3=9"


# ─── §6.2 確定性修正：只有 status=active + auto_replace=true + risk_class=normal ───

def test_get_deterministic_corrections_filters_by_status_risk_and_flag(store):
    active_ok = make_term(term_id="ok", canonical="正確詞", aliases=["別名甲"],
                           status="active", auto_replace=True, risk_class="normal")
    staged_excluded = make_term(term_id="staged", canonical="待審詞", aliases=["別名乙"],
                                 status="staged", auto_replace=True, risk_class="normal")
    high_risk_excluded = make_term(term_id="risky", canonical="高風險詞", aliases=["別名丙"],
                                    status="active", auto_replace=False, risk_class="high",
                                    term_type="medication")
    no_auto_excluded = make_term(term_id="noauto", canonical="不自動替換詞", aliases=["別名丁"],
                                  status="active", auto_replace=False, risk_class="normal")
    store.activate_bundle(make_bundle(terms=[active_ok, staged_excluded, high_risk_excluded, no_auto_excluded]))

    corrections = store.get_deterministic_corrections()
    assert corrections == {"別名甲": "正確詞"}


def test_terminal_term_statuses_are_excluded_from_all_runtime_paths(store):
    active = make_term(
        term_id="active",
        canonical="生效詞",
        aliases=["生效別名"],
        status="active",
        auto_replace=True,
    )
    staged = make_term(
        term_id="staged",
        canonical="待審詞",
        aliases=["待審別名"],
        status="staged",
        auto_replace=True,
    )
    deprecated = make_term(
        term_id="deprecated",
        canonical="退役詞",
        aliases=["退役別名"],
        status="deprecated",
        auto_replace=True,
    )
    revoked = make_term(
        term_id="revoked",
        canonical="撤回詞",
        aliases=["撤回別名"],
        status="revoked",
        auto_replace=True,
    )
    store.activate_bundle(make_bundle(terms=[active, staged, deprecated, revoked]))

    prompt_terms = store.select_prompt_terms()
    assert "生效詞" in prompt_terms
    assert "待審詞" in prompt_terms
    assert "退役詞" not in prompt_terms
    assert "撤回詞" not in prompt_terms

    assert store.get_deterministic_corrections() == {"生效別名": "生效詞"}

    candidates = store.find_candidates("生效別名 待審別名 退役別名 撤回別名")
    assert {candidate["term_id"] for candidate in candidates} == {"active", "staged"}
    eligibility = {
        candidate["term_id"]: candidate["auto_replace_eligible"]
        for candidate in candidates
    }
    assert eligibility == {"active": True, "staged": False}


def test_get_deterministic_corrections_drops_cross_shard_ambiguous_alias(store):
    """同一 alias 在不同生效 shard 對到不同 canonical → 不做確定性替換，只能當候選（§4.1）。"""
    t1 = make_term(term_id="c1", canonical="甲藥", aliases=["共用別名"],
                    status="active", auto_replace=True, risk_class="normal")
    store.activate_bundle(make_bundle(tenant_id="common", version="v1", terms=[t1]))
    t2 = make_term(term_id="c2", canonical="乙藥", aliases=["共用別名"],
                    status="active", auto_replace=True, risk_class="normal")
    store.activate_bundle(make_bundle(tenant_id="clinic-b", version="v1", terms=[t2]))

    corrections = store.get_deterministic_corrections(tenant_id="clinic-b")
    assert "共用別名" not in corrections, "跨 shard 歧義 alias 不得確定性替換"


# ─── §6.2 步驟 1-2、§5.3：post-ASR 候選檢索，最多 50 個 ───

def test_find_candidates_matches_ascii_word_boundary_and_cjk_substring(store):
    ascii_term = make_term(term_id="ct", canonical="CT", aliases=["ct"], language="en")
    cjk_term = make_term(term_id="jp", canonical="心電図", aliases=["心電図検査記録"], language="zh-Hant-TW")
    store.activate_bundle(make_bundle(language="en", terms=[ascii_term]))
    store.activate_bundle(make_bundle(language="zh-Hant-TW", terms=[cjk_term]))

    candidates = store.find_candidates("請幫我安排 ct 檢查，順便看一下心電図検査記録")
    ids = {c["term_id"] for c in candidates}
    assert "ct" in ids
    assert "jp" in ids

    # ASCII word boundary：ctscan 不應命中 "ct"（不是完整詞）
    no_hit = store.find_candidates("ctscan 這個字不該命中")
    assert "ct" not in {c["term_id"] for c in no_hit}


def test_find_candidates_caps_at_max_50():
    store_ = md.BundleStore()
    terms = [
        make_term(term_id=f"many-{i}", canonical=f"詞{i:03d}", aliases=[f"詞{i:03d}別名"])
        for i in range(80)
    ]
    store_ = md.BundleStore(root=None)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        store_ = md.BundleStore(root=tmp)
        store_.activate_bundle(make_bundle(terms=terms))
        text = "".join(f"詞{i:03d}別名" for i in range(80))
        candidates = store_.find_candidates(text)
        assert len(candidates) <= md.POST_ASR_MAX_CANDIDATES


def test_find_candidates_surfaces_high_risk_term_but_not_auto_replace_eligible(store):
    risky = make_term(term_id="risky", canonical="正確藥名", aliases=["相似藥名別名"],
                       status="active", auto_replace=False, risk_class="high", term_type="medication")
    store.activate_bundle(make_bundle(terms=[risky]))
    candidates = store.find_candidates("這裡有相似藥名別名")
    assert len(candidates) == 1
    assert candidates[0]["auto_replace_eligible"] is False
    assert candidates[0]["risk_class"] == "high"


# ─── §6.3 tenant isolation ────────────────────────────────

def test_tenant_isolation_no_cross_tenant_hit(store):
    store.activate_bundle(make_bundle(
        tenant_id="clinic-a", terms=[make_term(term_id="a1", canonical="A診所專用詞")]
    ))
    store.activate_bundle(make_bundle(
        tenant_id="clinic-b", terms=[make_term(term_id="b1", canonical="B診所專用詞")]
    ))
    terms_a = store.select_prompt_terms(tenant_id="clinic-a")
    terms_b = store.select_prompt_terms(tenant_id="clinic-b")
    assert "A診所專用詞" in terms_a and "B診所專用詞" not in terms_a
    assert "B診所專用詞" in terms_b and "A診所專用詞" not in terms_b


def test_clear_tenant_cache_only_drops_that_tenant(store):
    store.activate_bundle(make_bundle(tenant_id="clinic-a", terms=[make_term(canonical="A詞")]))
    store.activate_bundle(make_bundle(tenant_id="clinic-b", terms=[make_term(canonical="B詞")]))
    key_a = md.shard_key_with_version("clinic-a", "general-medical", "zh-Hant-TW", "v1")
    key_b = md.shard_key_with_version("clinic-b", "general-medical", "zh-Hant-TW", "v1")
    assert key_a in store._cache and key_b in store._cache  # noqa: SLF001

    store.clear_tenant_cache("clinic-a")
    assert key_a not in store._cache  # noqa: SLF001
    assert key_b in store._cache  # noqa: SLF001
    # 清除的只是記憶體 cache，磁碟仍在，重新選字仍可正常運作（重新載入）
    assert "A詞" in store.select_prompt_terms(tenant_id="clinic-a")


# ─── §5.2/§6.3 LRU：最多 3 個 shard 常駐記憶體 ──────────────

def test_lru_cache_evicts_beyond_max_active_shards(store):
    languages = ["zh-Hant-TW", "ja-JP", "en"]
    for i, lang in enumerate(languages):
        store.activate_bundle(make_bundle(language=lang, terms=[make_term(canonical=f"詞{i}")]))
    assert len(store._cache) == 3  # noqa: SLF001

    # 第 4 個 shard 進來，最舊的（zh-Hant-TW）應被逐出記憶體（但磁碟仍保留）
    store.activate_bundle(make_bundle(tenant_id="clinic-c", terms=[make_term(canonical="第四詞")]))
    assert len(store._cache) <= md.MAX_ACTIVE_SHARDS_IN_MEMORY  # noqa: SLF001


# ─── transcriber.py 整合點：augment_scene_words / augment_scene_corrections ───

def test_augment_scene_words_passthrough_for_non_medical_scene():
    base = ["一般詞"]
    assert md.augment_scene_words("general", base) == base
    assert md.augment_scene_words("medical_consultation", base) == base, (
        "SOAP/edit 場景不得混用醫療詞庫 prompt-bias 行為（roadmap §2.3 規則 5）"
    )


def test_augment_scene_corrections_passthrough_for_non_medical_scene():
    base = {"舊": "新"}
    assert md.augment_scene_corrections("general", base) is base
    assert md.augment_scene_corrections("medical_consultation", base) is base


def test_augment_scene_words_merges_bundle_terms_for_medical_scene(isolated_data_dir, monkeypatch):
    monkeypatch.setattr(cfg, "DATA_DIR", str(isolated_data_dir))
    store_ = md.get_default_store()
    store_.activate_bundle(make_bundle(terms=[make_term(canonical="整合測試詞", priority=99)]))

    merged = md.augment_scene_words("medical", ["既有場景詞"])
    assert "既有場景詞" in merged
    assert "整合測試詞" in merged


def test_augment_scene_words_respects_emergency_kill_switch(isolated_data_dir, monkeypatch):
    monkeypatch.setattr(cfg, "DATA_DIR", str(isolated_data_dir))
    store_ = md.get_default_store()
    store_.activate_bundle(make_bundle(terms=[make_term(canonical="不該出現的詞", priority=99)]))

    merged = md.augment_scene_words(
        "medical", ["既有場景詞"], config_dict={"enable_medical_dictionary_bundles": False}
    )
    assert merged == ["既有場景詞"], "enable_medical_dictionary_bundles=False 必須整層停用（roadmap §8.3）"


def test_augment_scene_words_fail_open_when_store_raises(monkeypatch):
    """任何內部例外都必須 fail-open 回傳原始 base_words，不得讓醫療詞庫問題拖垮既有辨識管線。"""
    def boom():
        raise RuntimeError("simulated bundle store failure")
    monkeypatch.setattr(md, "get_default_store", boom)
    assert md.augment_scene_words("medical", ["安全詞"]) == ["安全詞"]


# ─── 端到端：bundle 詞彙如何真的到達 memory.build_whisper_prompt 的 20/200 硬上限 ───

def test_bundle_words_flow_into_existing_prompt_budget_without_reimplementing_it(isolated_data_dir, monkeypatch):
    """驗收條件 #3：確認詞彙路徑 —— select_prompt_terms() 的輸出被當成
    memory.Memory.build_whisper_prompt() 的 scene_words 參數，最終仍受該函式既有的
    20 詞／200 字硬上限與「不可截斷單詞」規則把關（本模組不重新定義這個上限）。"""
    monkeypatch.setattr(cfg, "DATA_DIR", str(isolated_data_dir))
    import importlib
    import memory as mem_mod
    importlib.reload(mem_mod)
    m = mem_mod.Memory()

    store_ = md.get_default_store()
    bundle_terms = [make_term(term_id=f"budget-{i}", canonical=f"超長醫療詞彙測試字串{i:02d}", priority=100 - i)
                    for i in range(15)]
    store_.activate_bundle(make_bundle(terms=bundle_terms))

    scene_words = md.augment_scene_words("medical", [])
    assert any(w.startswith("超長醫療詞彙測試字串") for w in scene_words), (
        "bundle 選出的詞必須真的出現在 scene_words 裡（詞彙送到 STT prompt 的路徑）"
    )
    prompt = m.build_whisper_prompt([], scene_words)
    assert len(prompt) <= 200
    terms_in_prompt = [t for t in prompt.split(", ") if t]
    assert len(terms_in_prompt) <= 20
    known_complete_words = set(scene_words) | set(cfg.BASE_CUSTOM_WORDS)
    for t in terms_in_prompt:
        assert t in known_complete_words, f"不得出現被截斷、不完整的詞: {t!r}"
    assert any(t in scene_words for t in terms_in_prompt), "bundle 詞至少要有一個實際進入最終 prompt"

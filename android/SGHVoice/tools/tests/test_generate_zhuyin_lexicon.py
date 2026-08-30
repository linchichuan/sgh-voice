#!/usr/bin/env python3

import importlib.util
import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
ANDROID_ROOT = TOOLS_DIR.parent
GENERATOR_PATH = TOOLS_DIR / "generate_zhuyin_lexicon.py"
EXACT_ASSET_PATH = (
    ANDROID_ROOT
    / "app"
    / "src"
    / "main"
    / "assets"
    / "zhuyin"
    / "traditional_zhuyin_exact.zlex"
)
CONTEXT_ASSET_PATH = EXACT_ASSET_PATH.with_name("traditional_zhuyin_context.zlex")
SNAPSHOT_PATH = EXACT_ASSET_PATH.with_name("snapshot.json")

SPEC = importlib.util.spec_from_file_location("generate_zhuyin_lexicon", GENERATOR_PATH)
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generator
SPEC.loader.exec_module(generator)


def load_asset_entries(path: Path) -> dict[str, dict[str, int]]:
    entries: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        reading, encoded_candidates = line.split("\t", 1)
        by_text: dict[str, int] = {}
        for encoded in encoded_candidates.split("|"):
            text, score = encoded.rsplit(":", 1)
            by_text[text] = int(score)
        entries[reading] = by_text
    return entries


class ZhuyinLexiconGeneratorTest(unittest.TestCase):
    def test_native_mcbopomofo_data_keeps_common_forms_and_phrases(self) -> None:
        data = """# format org.openvanilla.mcbopomofo.sorted
ㄔㄨ 出 -2.8
ㄔㄨ 齣 -5.1
ㄕㄢ 山 -3.4
ㄕㄢ 刪 -4.6
ㄕㄢ-ㄔㄨˊ 刪除 -4.5
"""
        base = """出 ㄔㄨ chu tj big5
齣 ㄔㄨ chu a big5
刪 ㄕㄢ shan g0 big5
删 ㄕㄢ shan g0 utf8
"""
        frequencies = "出 58735\n刪 815\n刪除 328\n"

        entries, stats = generator.build_mcbopomofo_lexicon(
            data,
            base,
            frequencies,
            max_candidates=24,
        )

        self.assertEqual(["出", "齣"], [text for text, _ in entries["ㄔㄨ"]])
        self.assertIn("刪", [text for text, _ in entries["ㄕㄢ"]])
        self.assertEqual(["刪除"], [text for text, _ in entries["ㄕㄢ ㄔㄨˊ"]])
        self.assertNotIn("删", [text for text, _ in entries["ㄕㄢ"]])
        self.assertEqual(5, stats["includedCandidateCount"])

    def test_mcbopomofo_associated_phrase_commits_only_the_suffix(self) -> None:
        associated = """# format org.openvanilla.mcbopomofo.sorted
刪-ㄕㄢ-掉-ㄉㄧㄠˋ -5.4813
刪-ㄕㄢ-除-ㄔㄨˊ -4.6556
刪-ㄕㄢ-除-ㄔㄨˊ-了-ㄌㄜ˙ -5.5097
"""

        entries, stats = generator.build_mcbopomofo_context_lexicon(
            associated,
            max_candidates=24,
        )

        self.assertEqual(["除", "掉", "除了"], [text for text, _ in entries["刪"]])
        self.assertEqual(3, stats["includedContextCandidateCount"])

    def test_shipped_asset_contains_a_production_sized_traditional_lexicon(self) -> None:
        entries = load_asset_entries(EXACT_ASSET_PATH)
        candidates = [text for values in entries.values() for text in values]
        phrase_count = sum(len(text) > 1 for text in candidates)
        single_character_count = sum(len(text) == 1 for text in candidates)

        self.assertGreaterEqual(len(entries), 120_000)
        self.assertGreaterEqual(phrase_count, 130_000)
        self.assertGreaterEqual(single_character_count, 10_000)
        expected = {
            "ㄕㄢ": "刪",
            "ㄕㄢ ㄔㄨˊ": "刪除",
            "ㄊㄨㄟ ㄐㄧㄢˋ": "推薦",
            "ㄏㄡˋ ㄒㄩㄢˇ": "候選",
            "ㄗ ㄌㄧㄠˋ ㄎㄨˋ": "資料庫",
            "ㄧ ㄌㄧㄠˊ": "醫療",
            "ㄩˋ ㄩㄝ": "預約",
            "ㄉㄧㄢˋ ㄏㄨㄚˋ": "電話",
            "ㄍㄥ ㄒㄧㄣ": "更新",
        }
        for reading, text in expected.items():
            self.assertIn(text, entries.get(reading, {}), f"{reading} should include {text}")

        self.assertEqual("出", max(entries["ㄔㄨ"], key=entries["ㄔㄨ"].get))
        self.assertEqual("家", max(entries["ㄐㄧㄚ"], key=entries["ㄐㄧㄚ"].get))
        self.assertEqual("同", max(entries["ㄊㄨㄥˊ"], key=entries["ㄊㄨㄥˊ"].get))
        self.assertEqual("了", max(entries["ㄌㄜ˙"], key=entries["ㄌㄜ˙"].get))

        context_entries = load_asset_entries(CONTEXT_ASSET_PATH)
        self.assertEqual("除", max(context_entries["刪"], key=context_entries["刪"].get))

        import json

        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(2, snapshot["formatVersion"])
        self.assertEqual("MIT", snapshot["dataLicence"])
        self.assertEqual(EXACT_ASSET_PATH.stat().st_size, snapshot["exactLexiconBytes"])
        self.assertEqual(CONTEXT_ASSET_PATH.stat().st_size, snapshot["contextLexiconBytes"])

    def test_sparse_indexes_point_to_real_sorted_rows(self) -> None:
        for asset_path in (
            EXACT_ASSET_PATH,
            EXACT_ASSET_PATH.with_name("traditional_zhuyin_folded.zlex"),
            CONTEXT_ASSET_PATH,
        ):
            index_path = asset_path.with_suffix(".zidx")
            data = asset_path.read_bytes()
            previous_key = ""
            for line in index_path.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                key, offset_text = line.split("\t", 1)
                offset = int(offset_text)
                row = data[offset : data.find(b"\n", offset)].decode("utf-8")
                self.assertEqual(key, row.split("\t", 1)[0])
                self.assertGreaterEqual(key, previous_key)
                previous_key = key


if __name__ == "__main__":
    unittest.main()

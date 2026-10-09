import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


english = module("generate_english_lexicon")
japanese = module("generate_japanese_lexicon")


class OfflineLexiconGeneratorTest(unittest.TestCase):
    def test_english_filters_flags_nonwords_names_and_low_frequency(self):
        source = """dictionary=test
 word=hello,f=120,flags=,originalFreq=120
 word=hello,f=125,flags=,originalFreq=125
 word=don't,f=100,flags=,originalFreq=100
 word=Name,f=180,flags=,originalFreq=180
 word=offensive,f=180,flags=offensive,originalFreq=180
 word=http://url,f=150,flags=,originalFreq=150
 word=rare,f=20,flags=,originalFreq=20
 word=bad,f=notnumber,flags=,originalFreq=20
"""
        words, _ = english.extract_words(source)
        self.assertEqual({"hello": 125, "don't": 100}, words)
        self.assertEqual({"hello": 125}, english.extract_words(source, max_words=1)[0])

    def test_japanese_expands_second_tier_and_keeps_native_glyphs(self):
        xml = """<?xml version="1.0"?><JMdict>
<entry><k_ele><keb>会議</keb><ke_pri>news2</ke_pri></k_ele><r_ele><reb>かいぎ</reb></r_ele><sense><pos>noun</pos></sense></entry>
<entry><k_ele><keb>画像</keb><ke_pri>nf30</ke_pri></k_ele><r_ele><reb>がぞう</reb></r_ele><sense><pos>noun</pos></sense></entry>
<entry><k_ele><keb>會議</keb><ke_inf>word containing outdated kanji or kanji usage</ke_inf><ke_pri>news2</ke_pri></k_ele><r_ele><reb>かいぎ</reb></r_ele></entry>
<entry><k_ele><keb>旧語</keb><ke_pri>news2</ke_pri></k_ele><r_ele><reb>きゅうご</reb></r_ele><sense><misc>archaic</misc></sense></entry>
<entry><k_ele><keb>枚</keb><ke_pri>news2</ke_pri></k_ele><r_ele><reb>まい</reb></r_ele><sense><pos>counter</pos></sense></entry>
</JMdict>""".encode()
        words, stats = japanese.extract_candidates(xml, set(japanese.DEFAULT_PRIORITY_TAGS))
        self.assertEqual({"会議"}, set(words["かいぎ"]))
        self.assertEqual({"画像"}, set(words["がぞう"]))
        self.assertNotIn("きゅうご", words)
        self.assertNotIn("まい", words)
        self.assertEqual(1, stats["excludedFormCount"])

    def test_packaged_assets_match_recorded_hashes_and_bounds(self):
        for language in ("english", "japanese"):
            root = ROOT / "app/src/main/assets" / language
            snapshot = json.loads((root / "snapshot.json").read_text())
            data = (root / snapshot["lexiconFile"]).read_bytes()
            self.assertEqual(snapshot["lexiconBytes"], len(data))
            self.assertEqual(snapshot["lexiconSha256"], hashlib.sha256(data).hexdigest())
            self.assertLess(len(data), 3_000_000)
            if language == "english":
                self.assertGreaterEqual(snapshot["wordCount"], 40_000)
                self.assertIn("Lexiteria", (root / "AOSP_NOTICE.txt").read_text())
            else:
                self.assertGreater(snapshot["candidateCount"], 30_000)
                self.assertIn("news2", snapshot["priorityTags"])
                for word in ("画像", "会議", "来週", "電車"):
                    self.assertIn(("\t" + word + "\n").encode(), data)


if __name__ == "__main__":
    unittest.main()

"""Synthetic terminology regression checks; no audio or real patient data."""

from dataclasses import FrozenInstanceError, asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from windows_client.lexicon import LexiconError, load_terms, suggestions


RESOURCE = Path(__file__).resolve().parent.parent / "resources" / "windows" / "psychiatry-ja-v1.json"


class TestWindowsLexicon(unittest.TestCase):
    def setUp(self):
        self.lexicon = load_terms()
        self.data = json.loads(RESOURCE.read_text(encoding="utf-8"))

    def invalid_resource(self, change):
        change(self.data)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "test.json"
            path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(LexiconError):
                load_terms(path)

    def test_resource_version_sources_and_immutable_terms(self):
        self.assertEqual((self.lexicon.version, self.lexicon.locale), ("1.0.0", "ja-JP"))
        self.assertEqual(len(self.lexicon.terms), 20)
        self.assertEqual(len(self.lexicon.sources), 5)
        source_ids = {source.source_id for source in self.lexicon.sources}
        self.assertTrue(all(set(term.source_ids) <= source_ids for term in self.lexicon.terms))
        with self.assertRaises(FrozenInstanceError):
            self.lexicon.version = "2.0.0"
        self.assertTrue(all(isinstance(term.aliases, tuple) for term in self.lexicon.terms))

    def test_synthetic_benchmarks_preserve_exact_bytes_doses_negation_and_uncertainty(self):
        fixture = self.data["synthetic_benchmarks"]
        self.assertIs(fixture["synthetic_only"], True)
        self.assertIs(fixture["accuracy_claim"], False)
        self.assertGreaterEqual(len(fixture["cases"]), 12)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                text = case["text"]
                before = text.encode("utf-8")
                candidates = self.lexicon.suggestions(text)
                self.assertEqual([candidate.term_id for candidate in candidates], case["expected_ids"])
                self.assertEqual(text.encode("utf-8"), before)
                self.assertEqual(case["text"], text)
                for protected in case["protected_spans"]:
                    self.assertIn(protected, text)
                for candidate in candidates:
                    self.assertEqual(set(asdict(candidate)), {
                        "term_id", "preferred", "matched_alias", "category", "source_ids",
                    })
                    self.assertNotIn("replacement", asdict(candidate))
                    self.assertNotIn("transcript", asdict(candidate))

    def test_word_candidate_has_provenance_without_clinical_context(self):
        candidate, = suggestions("とうごうしっちょうしょうの疑い。", lexicon=self.lexicon)
        self.assertEqual(candidate.preferred, "統合失調症")
        self.assertEqual(candidate.matched_alias, "とうごうしっちょうしょう")
        self.assertEqual(candidate.category, "diagnosis")
        self.assertEqual(candidate.source_ids, ("ncnp-schizophrenia",))
        self.assertNotIn("疑い", candidate.preferred)

    def test_exact_readings_only_and_conservative_boundaries(self):
        for text in ("とうごうしちょうしょう", "とうごう しっちょうしょう", "ふみんしょうがく",
                     "あふみんしょう", "abcふみんしょう", "ふみんしょうxyz", "もうそう", "うつ",
                     "統合失調症", "双極性障害", "認知行動療法"):
            with self.subTest(text=text):
                self.assertEqual(self.lexicon.suggestions(text), ())
        self.assertEqual(len(self.lexicon.suggestions("（ふみんしょう）は未確定。")), 1)

    def test_deduplicates_orders_by_occurrence_and_respects_limit(self):
        text = "ちゅうとかくせい。とうごうしっちょうしょう。ちゅうとかくせい。げんちょう。"
        self.assertEqual([candidate.term_id for candidate in self.lexicon.suggestions(text)],
                         ["nocturnal-awakening", "schizophrenia", "auditory-hallucination"])
        self.assertEqual(len(self.lexicon.suggestions(text, limit=1)), 1)
        self.assertEqual(self.lexicon.suggestions(text, limit=0), ())

    def test_glossary_helper_is_opt_in_bounded_and_has_no_sentence_instructions(self):
        self.assertEqual(self.lexicon.glossary_prompt(max_chars=0), "")
        self.assertEqual(self.lexicon.glossary_prompt(max_chars=5), "統合失調症")
        self.assertLessEqual(len(self.lexicon.glossary_prompt(max_chars=30)), 30)
        self.assertNotIn("mg", self.lexicon.glossary_prompt())
        with patch.object(type(self.lexicon), "glossary_prompt", side_effect=AssertionError("not opt-in")):
            self.assertEqual(len(self.lexicon.suggestions("げんちょうはない。")), 1)

    def test_no_network_or_patient_text_logging_during_load_and_match(self):
        with patch("socket.create_connection", side_effect=AssertionError("network")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
                patch("logging.Logger._log", side_effect=AssertionError("logging")), \
                patch("builtins.print", side_effect=AssertionError("print")):
            loaded = load_terms()
            self.assertEqual(len(loaded.suggestions("げんちょうはない。")), 1)

    def test_pyinstaller_bundle_path_and_missing_bundle_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "resources" / "windows" / RESOURCE.name
            destination.parent.mkdir(parents=True)
            altered = self.data.copy()
            altered["version"] = "1.0.1"
            destination.write_text(json.dumps(altered, ensure_ascii=False), encoding="utf-8")
            with patch("windows_client.lexicon.sys._MEIPASS", temporary, create=True):
                self.assertEqual(load_terms().version, "1.0.1")
                destination.unlink()
                self.assertEqual(load_terms().version, "1.0.0")

    def test_invalid_schema_and_unvalidated_suggestion_policy_rejected(self):
        for key, value in (("schema_version", 2), ("locale", "en-US"),
                           ("version", "latest"), ("automatic_replacement", True),
                           ("clinically_validated", True)):
            with self.subTest(key=key):
                self.data = json.loads(RESOURCE.read_text(encoding="utf-8"))
                self.invalid_resource(lambda data: data.update({key: value}))

    def test_missing_provenance_and_unofficial_source_rejected(self):
        self.invalid_resource(lambda data: data["terms"][0].update(source_ids=["missing"]))
        self.data = json.loads(RESOURCE.read_text(encoding="utf-8"))
        self.invalid_resource(lambda data: data["sources"][0].update(url="https://example.com/terms"))
        self.data = json.loads(RESOURCE.read_text(encoding="utf-8"))
        self.invalid_resource(lambda data: data["sources"][0].update(url="https://kokoro.ncnp.go.jp@evil.example/"))

    def test_short_ambiguous_numeric_negation_and_instruction_aliases_rejected(self):
        for alias in ("うつ", "もうそう", "0.5mg", "とうごうしっちょうしょうではない", "しっちょうしょうなし"):
            with self.subTest(alias=alias):
                self.data = json.loads(RESOURCE.read_text(encoding="utf-8"))
                self.invalid_resource(lambda data: data["terms"][0].update(aliases=[alias]))
        self.data = json.loads(RESOURCE.read_text(encoding="utf-8"))
        self.invalid_resource(lambda data: data["terms"][0].update(preferred="統合失調症なし"))

    def test_duplicate_readings_and_unknown_categories_rejected(self):
        self.invalid_resource(lambda data: data["terms"][1].update(aliases=data["terms"][0]["aliases"]))
        self.data = json.loads(RESOURCE.read_text(encoding="utf-8"))
        self.invalid_resource(lambda data: data["terms"][0].update(category="dose"))
        self.data = json.loads(RESOURCE.read_text(encoding="utf-8"))
        self.invalid_resource(lambda data: data["terms"][0].update(category={"untrusted": "payload"}))

    def test_missing_and_malformed_files_have_content_free_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "patient-secret-name.json"
            with self.assertRaises(LexiconError) as error:
                load_terms(missing)
            self.assertNotIn("patient-secret", str(error.exception))
            missing.write_text("private patient text not JSON", encoding="utf-8")
            with self.assertRaises(LexiconError) as error:
                load_terms(missing)
            self.assertNotIn("patient", str(error.exception))

    def test_input_and_limits_are_bounded(self):
        for limit in (-1, 33, True, "8"):
            with self.subTest(limit=limit), self.assertRaises(LexiconError):
                self.lexicon.suggestions("", limit=limit)
        with self.assertRaises(LexiconError):
            self.lexicon.suggestions("a" * 100001)
        with self.assertRaises(TypeError):
            self.lexicon.suggestions(None)
        with self.assertRaises(LexiconError):
            self.lexicon.glossary_prompt(max_chars=4001)


if __name__ == "__main__":
    unittest.main()

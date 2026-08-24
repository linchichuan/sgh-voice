import json
from pathlib import Path

import pytest

from translation import TranslationError, validate_translation_semantics


_CORPUS_PATH = (
    Path(__file__).parent / "fixtures" / "translation_semantic_cases.json"
)
_CORPUS = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))


def test_translation_regression_corpus_schema():
    assert len(_CORPUS) >= 10
    assert len({case["id"] for case in _CORPUS}) == len(_CORPUS)

    for case in _CORPUS:
        assert set(case) == {
            "id",
            "category",
            "source",
            "targets",
            "translations",
            "expected",
        }
        assert case["expected"] in {"accept", "reject"}
        assert set(case["targets"]) == set(case["translations"])


@pytest.mark.parametrize("case", _CORPUS, ids=lambda case: case["id"])
def test_translation_semantic_regression_case(case):
    if case["expected"] == "accept":
        assert validate_translation_semantics(
            case["source"],
            case["translations"],
            case["targets"],
        ) == case["translations"]
        return

    with pytest.raises(TranslationError):
        validate_translation_semantics(
            case["source"],
            case["translations"],
            case["targets"],
        )

from __future__ import annotations

import pytest

from noecho.core.providers import (
    CitedStatement,
    DisabledLLMProvider,
    FeatureDisabledError,
    SimilarityBackend,
    ThreadAnswer,
    validate_answer,
)
from noecho.core.similarity import TfidfSimilarity


def test_local_backend_satisfies_protocol():
    assert isinstance(TfidfSimilarity(), SimilarityBackend)


def test_disabled_provider():
    p = DisabledLLMProvider()
    assert p.coach("draft", ["a"]) is None
    with pytest.raises(FeatureDisabledError):
        p.answer("what has been said?", [(1, "a")])


def test_synthesis_must_cite_known_comments():
    ok = ThreadAnswer(cited=(CitedStatement("x", (1,)),), gaps=("nobody mentioned cost",))
    validate_answer(ok, {1, 2})
    with pytest.raises(ValueError):
        validate_answer(ThreadAnswer(cited=(CitedStatement("x", ()),)), {1})
    with pytest.raises(ValueError):
        validate_answer(ThreadAnswer(cited=(CitedStatement("x", (9,)),)), {1})

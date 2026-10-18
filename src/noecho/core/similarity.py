"""Local similarity backend: TF-IDF cosine over word and character n-grams.

The IDF is computed over the thread being checked (existing comments plus the
candidate), so terms that every comment in the thread shares (usually the
thread's topic words) count for less than terms specific to one point.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from noecho.core.text import char_features, tokens, word_features


def _idf(docs: Sequence[Counter[str]]) -> dict[str, float]:
    n = len(docs)
    df: Counter[str] = Counter()
    for doc in docs:
        df.update(doc.keys())
    # Smoothed IDF, as in scikit-learn: ln((1 + n) / (1 + df)) + 1.
    return {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}


def _vector(counts: Counter[str], idf: dict[str, float]) -> dict[str, float]:
    vec = {t: (1.0 + math.log(c)) * idf[t] for t, c in counts.items()}
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0.0:
        return {}
    return {t: v / norm for t, v in vec.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


class TfidfSimilarity:
    """Scores a candidate against each text in a corpus, returning values in [0, 1].

    ``word_weight`` blends the word-level and character-level cosines. Word
    features reward shared phrasing; character features reward shared word
    stems and survive typos.
    """

    name = "tfidf-local"

    def __init__(self, word_weight: float = 0.5) -> None:
        if not 0.0 <= word_weight <= 1.0:
            raise ValueError("word_weight must be between 0 and 1")
        self.word_weight = word_weight

    def score(self, candidate: str, corpus: Sequence[str]) -> list[float]:
        if not corpus:
            return []
        cand_tokens = tokens(candidate)
        words = [word_features(t) for t in corpus]
        chars = [char_features(t) for t in corpus]
        cand_w = word_features(candidate)
        cand_c = char_features(candidate)

        idf_w = _idf([*words, cand_w])
        idf_c = _idf([*chars, cand_c])
        cv_w = _vector(cand_w, idf_w)
        cv_c = _vector(cand_c, idf_c)

        scores: list[float] = []
        for text, w, c in zip(corpus, words, chars, strict=True):
            if cand_tokens and tokens(text) == cand_tokens:
                # Same content tokens in the same order: an exact echo.
                scores.append(1.0)
                continue
            s = self.word_weight * _cosine(cv_w, _vector(w, idf_w)) + (
                1.0 - self.word_weight
            ) * _cosine(cv_c, _vector(c, idf_c))
            scores.append(max(0.0, min(1.0, s)))
        return scores

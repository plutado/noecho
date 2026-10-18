"""Text normalization and feature extraction for the local similarity backend.

Everything here is deterministic and dependency-free so the uniqueness gate
works offline, with no API key, and gives the same answer on every machine.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from itertools import pairwise

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Curly quotes and long dashes, written as escapes so the source stays ASCII.
_PUNCT_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
    }
)

# A deliberately short list. Removing too many words erases negation and
# quantifiers, which are often the whole point of a distinct comment.
_STOPWORD_TEXT = """
a an the and or but if then so of to in on at by for from with as is are was were be
been being it its this that these those i you he she we they me him her us them my your
our their there here just really very also too can could would should will shall do does
did has have had about into over than which who whom what when where while
"""
STOPWORDS = frozenset(_STOPWORD_TEXT.split())

# Words that change meaning. They are kept out of STOPWORDS on purpose.
_KEEP = frozenset({"not", "no", "never", "none", "nor", "without", "against", "only"})


def normalize(text: str) -> str:
    """Unicode-normalize, casefold, unify punctuation, and collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).translate(_PUNCT_MAP).casefold()
    text = text.replace("n't", " not")
    return " ".join(text.split())


def _stem(word: str) -> str:
    """A tiny suffix stripper. Not linguistically complete; it only needs to
    make 'prices'/'price' and 'raising'/'raised' land near each other."""
    for suffix in ("ingly", "edly", "ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            if suffix == "s" and word.endswith("ss"):
                return word
            return word[: -len(suffix)]
    return word


def tokens(text: str) -> list[str]:
    """Content tokens: normalized, stopwords removed, lightly stemmed."""
    return [_stem(t) for t in _TOKEN_RE.findall(normalize(text)) if t not in STOPWORDS]


def word_features(text: str) -> Counter[str]:
    """Unigrams plus bigrams of content tokens."""
    toks = tokens(text)
    feats: Counter[str] = Counter(toks)
    feats.update(f"{a} {b}" for a, b in pairwise(toks))
    return feats


def char_features(text: str, n_min: int = 3, n_max: int = 5) -> Counter[str]:
    """Character n-grams within padded words (like scikit-learn's ``char_wb``).

    These catch misspellings, inflections, and light rewording that word
    features miss.
    """
    feats: Counter[str] = Counter()
    for word in _TOKEN_RE.findall(normalize(text)):
        if word in STOPWORDS:
            continue
        padded = f" {word} "
        for n in range(n_min, n_max + 1):
            if len(padded) < n:
                continue
            feats.update(padded[i : i + n] for i in range(len(padded) - n + 1))
    return feats

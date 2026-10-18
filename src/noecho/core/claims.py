"""Claim typing and citation rules.

A claim's status is a pure function of its kind and its attached citations:

* opinion claims are always ``opinion`` and accept no citations;
* a factual claim with no qualifying evidence is ``unverified``;
* supporting evidence only (from enough distinct sources) is ``verified``;
* refuting evidence only (from enough distinct sources) is ``refuted``;
* evidence on both sides is ``disputed``, and stays disputed. Nothing here
  counts people, and there is no way to resolve a dispute by vote.

A citation whose normalized URL is already attached to the claim, on either
side, is rejected: repeating a source adds nothing.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from noecho.core.models import ClaimKind, ClaimStatus, Stance

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src"})


class CitationRejectedError(ValueError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def normalize_source(url: str) -> str:
    """Canonical form of a source URL, used to detect repeated citations.

    Lowercases scheme and host, drops ``www.``, default ports, fragments,
    tracking parameters and trailing slashes, and sorts the query string.
    """
    raw = url.strip()
    parts = urlsplit(raw)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise CitationRejectedError("invalid_url", f"not an http(s) URL: {url!r}")
    host = parts.hostname.lower().removeprefix("www.")
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_KEYS and not k.lower().startswith(_TRACKING_PREFIXES)
    )
    path = parts.path.rstrip("/") or ""
    # Scheme is folded to https: the same document over http is the same source.
    return urlunsplit(("https", host, path, urlencode(query), ""))


def source_domain(normalized_url: str) -> str:
    return urlsplit(normalized_url).netloc


def check_citation(kind: ClaimKind, existing_normalized: Iterable[str], new_url: str) -> str:
    """Validate a new citation and return its normalized URL, or raise."""
    if kind is ClaimKind.OPINION:
        raise CitationRejectedError(
            "opinion_claim", "opinion claims are not verifiable and take no citations"
        )
    normalized = normalize_source(new_url)
    if normalized in set(existing_normalized):
        raise CitationRejectedError(
            "duplicate_citation", "this source is already attached to the claim"
        )
    return normalized


def derive_status(
    kind: ClaimKind,
    citations: Iterable[tuple[str, Stance]],
    min_sources: int = 1,
) -> ClaimStatus:
    """Compute a claim's bucket from ``(normalized_url, stance)`` pairs.

    ``min_sources`` is the number of distinct source *domains* needed on a
    side for that side to count. Two pages from one site are one source.
    """
    if min_sources < 1:
        raise ValueError("min_sources must be at least 1")
    if kind is ClaimKind.OPINION:
        return ClaimStatus.OPINION
    support: set[str] = set()
    refute: set[str] = set()
    for url, stance in citations:
        (support if stance is Stance.SUPPORTS else refute).add(source_domain(url))
    has_support = len(support) >= min_sources
    has_refute = len(refute) >= min_sources
    if has_support and has_refute:
        return ClaimStatus.DISPUTED
    if has_support:
        return ClaimStatus.VERIFIED
    if has_refute:
        return ClaimStatus.REFUTED
    return ClaimStatus.UNVERIFIED

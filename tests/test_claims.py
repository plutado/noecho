from __future__ import annotations

import pytest

from noecho.core.claims import (
    CitationRejectedError,
    check_citation,
    derive_status,
    normalize_source,
)
from noecho.core.models import ClaimKind, ClaimStatus, Stance

F = ClaimKind.FACTUAL
S, R = Stance.SUPPORTS, Stance.REFUTES


def _n(url: str) -> str:
    return normalize_source(url)


class TestDeriveStatus:
    def test_factual_without_evidence_is_unverified(self):
        assert derive_status(F, []) is ClaimStatus.UNVERIFIED

    def test_support_verifies(self):
        assert derive_status(F, [(_n("https://a.example/1"), S)]) is ClaimStatus.VERIFIED

    def test_refutation_refutes(self):
        assert derive_status(F, [(_n("https://a.example/1"), R)]) is ClaimStatus.REFUTED

    def test_both_sides_is_disputed(self):
        cites = [(_n("https://a.example/1"), S), (_n("https://b.example/2"), R)]
        assert derive_status(F, cites) is ClaimStatus.DISPUTED

    def test_opinion_is_always_opinion(self):
        assert derive_status(ClaimKind.OPINION, [(_n("https://a.example"), S)]) is (
            ClaimStatus.OPINION
        )

    def test_min_sources_counts_domains_not_pages(self):
        same_site = [(_n("https://a.example/1"), S), (_n("https://a.example/2"), S)]
        assert derive_status(F, same_site, min_sources=2) is ClaimStatus.UNVERIFIED
        two_sites = [*same_site, (_n("https://b.example/x"), S)]
        assert derive_status(F, two_sites, min_sources=2) is ClaimStatus.VERIFIED

    def test_min_sources_must_be_positive(self):
        with pytest.raises(ValueError):
            derive_status(F, [], min_sources=0)


class TestNormalizeSource:
    @pytest.mark.parametrize(
        "variant",
        [
            "https://example.org/report",
            "http://example.org/report",
            "https://www.example.org/report/",
            "HTTPS://Example.ORG/report#section-2",
            "https://example.org/report?utm_source=feed&utm_medium=x",
            "https://example.org:443/report?fbclid=abc",
        ],
    )
    def test_variants_collapse(self, variant):
        assert _n(variant) == "https://example.org/report"

    def test_query_order_is_irrelevant(self):
        assert _n("https://e.example/r?b=2&a=1") == _n("https://e.example/r?a=1&b=2")

    def test_meaningful_query_is_kept(self):
        assert _n("https://e.example/r?id=1") != _n("https://e.example/r?id=2")

    @pytest.mark.parametrize("bad", ["ftp://e.example/x", "not a url", "javascript:alert(1)"])
    def test_rejects_non_http(self, bad):
        with pytest.raises(CitationRejectedError) as exc:
            _n(bad)
        assert exc.value.reason == "invalid_url"


class TestCheckCitation:
    def test_duplicate_source_adds_nothing(self):
        existing = [_n("https://example.org/report")]
        with pytest.raises(CitationRejectedError) as exc:
            check_citation(F, existing, "https://www.example.org/report/?utm_campaign=z")
        assert exc.value.reason == "duplicate_citation"

    def test_opinion_takes_no_citations(self):
        with pytest.raises(CitationRejectedError) as exc:
            check_citation(ClaimKind.OPINION, [], "https://example.org")
        assert exc.value.reason == "opinion_claim"


class TestTransitionsThroughEngine:
    """Status moves only as evidence is attached. Nothing counts people."""

    @pytest.fixture
    def claim(self, engine):
        thread = engine.create_thread("Claims")
        comment = engine.post_comment(thread.id, "x", "The bridge opened in 1931.").comment
        return engine.add_claim(comment.id, "The bridge opened in 1931.", F)

    def test_unverified_to_verified_to_disputed(self, engine, claim):
        assert claim.status is ClaimStatus.UNVERIFIED
        _, claim = engine.attach_citation(claim.id, "https://archive.example/bridge", S)
        assert claim.status is ClaimStatus.VERIFIED
        _, claim = engine.attach_citation(claim.id, "https://records.example/b", R)
        assert claim.status is ClaimStatus.DISPUTED

    def test_refuted_to_disputed(self, engine, claim):
        _, claim = engine.attach_citation(claim.id, "https://records.example/b", R)
        assert claim.status is ClaimStatus.REFUTED
        _, claim = engine.attach_citation(claim.id, "https://archive.example/bridge", S)
        assert claim.status is ClaimStatus.DISPUTED

    def test_disputed_cannot_be_resolved_by_piling_on(self, engine, claim):
        engine.attach_citation(claim.id, "https://a.example/1", S)
        engine.attach_citation(claim.id, "https://b.example/1", R)
        for i in range(5):
            _, claim = engine.attach_citation(claim.id, f"https://s{i}.example/x", S)
        assert claim.status is ClaimStatus.DISPUTED

    def test_duplicate_citation_is_rejected_and_not_stored(self, engine, claim):
        engine.attach_citation(claim.id, "https://archive.example/bridge", S)
        with pytest.raises(CitationRejectedError):
            engine.attach_citation(claim.id, "http://www.archive.example/bridge/", R)
        assert len(engine.list_citations(claim.id)) == 1
        assert engine.get_claim(claim.id).status is ClaimStatus.VERIFIED

    def test_same_source_may_back_a_different_claim(self, engine, claim):
        other = engine.add_claim(claim.comment_id, "It was the longest span in the county.", F)
        engine.attach_citation(claim.id, "https://archive.example/bridge", S)
        _, other = engine.attach_citation(other.id, "https://archive.example/bridge", S)
        assert other.status is ClaimStatus.VERIFIED

    def test_opinion_claim_rejects_citations(self, engine, claim):
        op = engine.add_claim(
            claim.comment_id, "It is the town's best landmark.", ClaimKind.OPINION
        )
        assert op.status is ClaimStatus.OPINION
        with pytest.raises(CitationRejectedError):
            engine.attach_citation(op.id, "https://a.example", S)

"""Engine service: wires the pure core to a store.

The web layer talks to this class only. It owns the two invariants that span
core and storage: a comment is inserted only after the gate has seen every
earlier comment in the thread, and a claim's stored status always equals
``derive_status`` over its stored citations.
"""

from __future__ import annotations

from dataclasses import dataclass

from noecho.core.claims import check_citation, derive_status
from noecho.core.gate import GateDecision, Prior, UniquenessGate
from noecho.core.models import Citation, Claim, ClaimKind, Comment, Stance, Thread
from noecho.core.ordering import Order, order_comments
from noecho.storage.sqlite import SQLiteStore


class NotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class PostResult:
    decision: GateDecision
    comment: Comment | None = None
    matched: Comment | None = None


class Engine:
    def __init__(self, store: SQLiteStore, gate: UniquenessGate, min_sources: int = 1) -> None:
        self.store = store
        self.gate = gate
        self.min_sources = min_sources

    # Threads

    def create_thread(self, title: str, source_url: str | None = None) -> Thread:
        return self.store.create_thread(title, source_url)

    def get_thread(self, thread_id: int) -> Thread:
        thread = self.store.get_thread(thread_id)
        if thread is None:
            raise NotFoundError(f"thread {thread_id} not found")
        return thread

    def list_threads(self) -> list[Thread]:
        return self.store.list_threads()

    # Comments

    def list_comments(self, thread_id: int, order: Order = Order.CHRONOLOGICAL) -> list[Comment]:
        self.get_thread(thread_id)
        return order_comments(self.store.list_comments(thread_id), order)

    def check(self, thread_id: int, body: str) -> tuple[GateDecision, Comment | None]:
        """Run the gate without posting. Used for composition-time feedback."""
        self.get_thread(thread_id)
        existing = self.store.list_comments(thread_id)
        decision = self.gate.check(body, [Prior(c.id, c.body) for c in existing])
        return decision, self._matched(decision)

    def post_comment(self, thread_id: int, author: str, body: str) -> PostResult:
        self.get_thread(thread_id)
        with self.store.transaction():
            existing = self.store.list_comments(thread_id)
            decision = self.gate.check(body, [Prior(c.id, c.body) for c in existing])
            if decision.blocked:
                return PostResult(decision=decision, matched=self._matched(decision))
            comment = self.store.add_comment(thread_id, author, body)
        return PostResult(decision=decision, comment=comment)

    def get_comment(self, comment_id: int) -> Comment:
        comment = self.store.get_comment(comment_id)
        if comment is None:
            raise NotFoundError(f"comment {comment_id} not found")
        return comment

    def _matched(self, decision: GateDecision) -> Comment | None:
        if decision.matched_id is None:
            return None
        return self.store.get_comment(decision.matched_id)

    # Claims

    def add_claim(self, comment_id: int, text: str, kind: ClaimKind) -> Claim:
        self.get_comment(comment_id)
        status = derive_status(kind, [], self.min_sources)
        return self.store.add_claim(comment_id, text, kind, status)

    def get_claim(self, claim_id: int) -> Claim:
        claim = self.store.get_claim(claim_id)
        if claim is None:
            raise NotFoundError(f"claim {claim_id} not found")
        return claim

    def list_claims(self, comment_id: int) -> list[Claim]:
        self.get_comment(comment_id)
        return self.store.list_claims(comment_id)

    def list_citations(self, claim_id: int) -> list[Citation]:
        self.get_claim(claim_id)
        return self.store.list_citations(claim_id)

    def attach_citation(
        self, claim_id: int, url: str, stance: Stance, note: str | None = None
    ) -> tuple[Citation, Claim]:
        """Attach evidence and recompute status. Raises ``CitationRejectedError``."""
        with self.store.transaction():
            claim = self.get_claim(claim_id)
            existing = self.store.list_citations(claim_id)
            normalized = check_citation(claim.kind, (c.normalized_url for c in existing), url)
            citation = self.store.add_citation(claim_id, url.strip(), normalized, stance, note)
            status = derive_status(
                claim.kind,
                [(c.normalized_url, c.stance) for c in [*existing, citation]],
                self.min_sources,
            )
            if status is not claim.status:
                self.store.set_claim_status(claim_id, status)
        return citation, self.get_claim(claim_id)

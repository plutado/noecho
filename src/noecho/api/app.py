"""HTTP API. A thin translation layer over ``noecho.service.Engine``.

Run with:  uv run uvicorn noecho.api.app:create_app --factory
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from noecho.api.schemas import (
    AttributionOut,
    CitationIn,
    CitationOut,
    ClaimIn,
    ClaimOut,
    CommentIn,
    CommentOut,
    DraftIn,
    GateOut,
    MatchOut,
    PostedOut,
    ThreadIn,
    ThreadOut,
)
from noecho.config import Settings, load_settings
from noecho.core.claims import CitationRejectedError
from noecho.core.gate import GateDecision, UniquenessGate
from noecho.core.models import Citation, Claim, Comment, Thread
from noecho.core.ordering import Order
from noecho.service import Engine, NotFoundError
from noecho.storage.sqlite import SQLiteStore


def _thread_out(t: Thread) -> ThreadOut:
    return ThreadOut(id=t.id, title=t.title, source_url=t.source_url, created_at=t.created_at)


def _comment_out(c: Comment) -> CommentOut:
    return CommentOut(id=c.id, thread_id=c.thread_id, body=c.body, created_at=c.created_at)


def _gate_out(d: GateDecision, matched: Comment | None) -> GateOut:
    return GateOut(
        blocked=d.blocked,
        score=d.score,
        threshold=d.threshold,
        backend=d.backend,
        nearest=[MatchOut(comment_id=m.id, score=m.score) for m in d.nearest],
        matched=_comment_out(matched) if matched else None,
    )


def _citation_out(c: Citation) -> CitationOut:
    return CitationOut(
        id=c.id,
        claim_id=c.claim_id,
        url=c.url,
        stance=c.stance,
        note=c.note,
        created_at=c.created_at,
    )


def _claim_out(c: Claim, citations: list[Citation]) -> ClaimOut:
    return ClaimOut(
        id=c.id,
        comment_id=c.comment_id,
        text=c.text,
        kind=c.kind,
        status=c.status,
        created_at=c.created_at,
        citations=[_citation_out(x) for x in citations],
    )


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or load_settings()
    if settings.llm_provider != "none":
        raise RuntimeError(
            f"LLM provider {settings.llm_provider!r} is not available in this release; "
            "set NOECHO_LLM_PROVIDER=none"
        )
    if engine is None:
        engine = Engine(
            SQLiteStore(settings.db_path),
            UniquenessGate(threshold=settings.gate_threshold),
            min_sources=settings.min_sources,
        )

    app = FastAPI(
        title="No Echo",
        version="0.1.0",
        summary="A discussion engine where a thread only accepts unique contributions.",
    )
    app.state.engine = engine

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": "not_found", "detail": str(exc)})

    @app.exception_handler(CitationRejectedError)
    async def _rejected(_: Request, exc: CitationRejectedError) -> JSONResponse:
        status = 409 if exc.reason == "duplicate_citation" else 422
        return JSONResponse(status_code=status, content={"error": exc.reason, "detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "similarity": engine.gate.backend.name, "llm": "none"}

    @app.post("/threads", status_code=201)
    def create_thread(body: ThreadIn) -> ThreadOut:
        return _thread_out(engine.create_thread(body.title, body.source_url))

    @app.get("/threads")
    def list_threads() -> list[ThreadOut]:
        return [_thread_out(t) for t in engine.list_threads()]

    @app.get("/threads/{thread_id}")
    def get_thread(thread_id: int) -> ThreadOut:
        return _thread_out(engine.get_thread(thread_id))

    @app.get("/threads/{thread_id}/comments")
    def list_comments(thread_id: int, order: Order = Order.CHRONOLOGICAL) -> list[CommentOut]:
        """Comments in time order. ``order=reverse`` flips it; there is no other sort."""
        return [_comment_out(c) for c in engine.list_comments(thread_id, order)]

    @app.post("/threads/{thread_id}/check")
    def check_draft(thread_id: int, body: DraftIn) -> GateOut:
        """Run the uniqueness gate on a draft without posting it."""
        decision, matched = engine.check(thread_id, body.body)
        return _gate_out(decision, matched)

    @app.post(
        "/threads/{thread_id}/comments",
        status_code=201,
        response_model=PostedOut,
        responses={409: {"model": GateOut, "description": "Blocked as a duplicate."}},
    )
    def post_comment(thread_id: int, body: CommentIn) -> PostedOut | JSONResponse:
        result = engine.post_comment(thread_id, body.author, body.body)
        if result.comment is None:
            gate = _gate_out(result.decision, result.matched)
            return JSONResponse(status_code=409, content=gate.model_dump(mode="json"))
        return PostedOut(
            comment=_comment_out(result.comment), gate=_gate_out(result.decision, None)
        )

    @app.get("/comments/{comment_id}")
    def get_comment(comment_id: int) -> CommentOut:
        return _comment_out(engine.get_comment(comment_id))

    @app.get("/comments/{comment_id}/attribution")
    def get_attribution(comment_id: int) -> AttributionOut:
        """Authorship is available only by explicit request, never in the stream."""
        c = engine.get_comment(comment_id)
        return AttributionOut(comment_id=c.id, author=c.author)

    @app.post("/comments/{comment_id}/claims", status_code=201)
    def add_claim(comment_id: int, body: ClaimIn) -> ClaimOut:
        return _claim_out(engine.add_claim(comment_id, body.text, body.kind), [])

    @app.get("/comments/{comment_id}/claims")
    def list_claims(comment_id: int) -> list[ClaimOut]:
        return [_claim_out(c, engine.list_citations(c.id)) for c in engine.list_claims(comment_id)]

    @app.get("/claims/{claim_id}")
    def get_claim(claim_id: int) -> ClaimOut:
        return _claim_out(engine.get_claim(claim_id), engine.list_citations(claim_id))

    @app.post("/claims/{claim_id}/citations", status_code=201)
    def add_citation(claim_id: int, body: CitationIn) -> ClaimOut:
        _, claim = engine.attach_citation(claim_id, body.url, body.stance, body.note)
        return _claim_out(claim, engine.list_citations(claim_id))

    return app

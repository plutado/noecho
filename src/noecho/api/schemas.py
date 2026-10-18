"""Request and response bodies. Response models never expose a popularity field,
and comment listings never include the author."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from noecho.core.models import ClaimKind, ClaimStatus, Stance


class ThreadIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    source_url: str | None = Field(default=None, max_length=2000)


class ThreadOut(BaseModel):
    id: int
    title: str
    source_url: str | None
    created_at: datetime


class CommentIn(BaseModel):
    author: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=10_000)


class DraftIn(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class CommentOut(BaseModel):
    """A comment as it appears in the stream: no author."""

    id: int
    thread_id: int
    body: str
    created_at: datetime


class AttributionOut(BaseModel):
    comment_id: int
    author: str


class MatchOut(BaseModel):
    comment_id: int
    score: float


class GateOut(BaseModel):
    blocked: bool
    score: float
    threshold: float
    backend: str
    nearest: list[MatchOut]
    matched: CommentOut | None = None


class PostedOut(BaseModel):
    comment: CommentOut
    gate: GateOut


class ClaimIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    kind: ClaimKind


class CitationIn(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    stance: Stance
    note: str | None = Field(default=None, max_length=1000)


class CitationOut(BaseModel):
    id: int
    claim_id: int
    url: str
    stance: Stance
    note: str | None
    created_at: datetime


class ClaimOut(BaseModel):
    id: int
    comment_id: int
    text: str
    kind: ClaimKind
    status: ClaimStatus
    created_at: datetime
    citations: list[CitationOut] = []


class ErrorOut(BaseModel):
    error: str
    detail: str

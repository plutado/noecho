"""Domain records. Plain dataclasses with no storage or web dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ClaimKind(StrEnum):
    """Whether a claim asserts something checkable or states a viewpoint."""

    FACTUAL = "factual"
    OPINION = "opinion"


class ClaimStatus(StrEnum):
    """The five buckets. Status is derived from attached evidence, never from votes."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    REFUTED = "refuted"
    DISPUTED = "disputed"
    OPINION = "opinion"


class Stance(StrEnum):
    """What a citation does to the claim it is attached to."""

    SUPPORTS = "supports"
    REFUTES = "refutes"


@dataclass(frozen=True, slots=True)
class Thread:
    id: int
    title: str
    source_url: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Comment:
    id: int
    thread_id: int
    author: str
    body: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Claim:
    id: int
    comment_id: int
    text: str
    kind: ClaimKind
    status: ClaimStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Citation:
    id: int
    claim_id: int
    url: str
    normalized_url: str
    stance: Stance
    note: str | None
    created_at: datetime

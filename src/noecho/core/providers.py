"""Pluggable provider interfaces.

The engine depends only on these protocols. The local TF-IDF backend
satisfies ``SimilarityBackend`` with no network access. LLM features
(composition coaching, thread Q&A) sit behind ``LLMProvider`` and are disabled
unless an implementation is configured; none ships in this release.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@runtime_checkable
class SimilarityBackend(Protocol):
    """Scores a candidate against each corpus text. Scores are in [0, 1]."""

    name: str

    def score(self, candidate: str, corpus: Sequence[str]) -> list[float]: ...


@dataclass(frozen=True, slots=True)
class CitedStatement:
    """A sentence of synthesis and the comment ids it is grounded in."""

    text: str
    comment_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ThreadAnswer:
    """Answer to a question about a thread.

    ``cited`` is synthesis of what has been said; every entry must reference
    at least one comment. ``gaps`` is labeled inference about what has not
    been said; it cites nothing and the UI must present it as analysis.
    """

    cited: tuple[CitedStatement, ...] = field(default_factory=tuple)
    gaps: tuple[str, ...] = field(default_factory=tuple)


class FeatureDisabledError(RuntimeError):
    """Raised when an optional LLM feature is called with no provider configured."""


class LLMProvider(Protocol):
    name: str

    def coach(self, draft: str, thread: Sequence[str]) -> str | None:
        """Return a short prompt nudging the writer toward novelty, or None."""
        ...

    def answer(self, question: str, thread: Sequence[tuple[int, str]]) -> ThreadAnswer: ...


class DisabledLLMProvider:
    """The default. Keeps the optional surfaces explicit about being off."""

    name = "none"

    def coach(self, draft: str, thread: Sequence[str]) -> str | None:
        return None

    def answer(self, question: str, thread: Sequence[tuple[int, str]]) -> ThreadAnswer:
        raise FeatureDisabledError("thread Q&A requires an LLM provider (NOECHO_LLM_PROVIDER)")


def validate_answer(answer: ThreadAnswer, known_ids: set[int]) -> None:
    """Reject synthesis that cites nothing or cites comments outside the thread.

    Applied to any provider's output before it reaches a client, so a provider
    cannot turn the Q&A surface into an uncited assertion stream.
    """
    for stmt in answer.cited:
        if not stmt.comment_ids:
            raise ValueError(f"uncited synthesis: {stmt.text!r}")
        unknown = set(stmt.comment_ids) - known_ids
        if unknown:
            raise ValueError(f"synthesis cites unknown comments: {sorted(unknown)}")

"""The uniqueness gate.

A submission is compared against every existing comment in its thread. If the
best match scores at or above the threshold, the submission is blocked and the
decision carries the matched comment's id and score so the caller can show the
submitter exactly what they collided with. The gate never blocks silently.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from noecho.core.providers import SimilarityBackend
from noecho.core.similarity import TfidfSimilarity

# Chosen against the fixtures in tests/test_gate.py. See docs/system-design.md
# ("Threshold tuning") for why this is a starting point, not a settled value.
DEFAULT_THRESHOLD = 0.45


@dataclass(frozen=True, slots=True)
class Prior:
    """An existing comment as the gate sees it: an id and its text."""

    id: int
    text: str


@dataclass(frozen=True, slots=True)
class Match:
    id: int
    score: float


@dataclass(frozen=True, slots=True)
class GateDecision:
    blocked: bool
    score: float
    threshold: float
    backend: str
    matched_id: int | None = None
    nearest: tuple[Match, ...] = field(default_factory=tuple)


class UniquenessGate:
    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        backend: SimilarityBackend | None = None,
        nearest_k: int = 3,
    ) -> None:
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        self.threshold = threshold
        self.backend: SimilarityBackend = backend or TfidfSimilarity()
        self.nearest_k = nearest_k

    def check(self, candidate: str, existing: Sequence[Prior]) -> GateDecision:
        """Score ``candidate`` against ``existing`` and decide.

        ``nearest`` is always populated (up to ``nearest_k`` entries) so that
        an accepted submission can still show what it was closest to.
        """
        scores = self.backend.score(candidate, [p.text for p in existing])
        ranked = sorted(
            (Match(p.id, round(s, 4)) for p, s in zip(existing, scores, strict=True)),
            key=lambda m: (-m.score, m.id),
        )
        nearest = tuple(ranked[: self.nearest_k])
        best = nearest[0] if nearest else None
        best_score = best.score if best else 0.0
        blocked = best is not None and best_score >= self.threshold
        return GateDecision(
            blocked=blocked,
            score=best_score,
            threshold=self.threshold,
            backend=self.backend.name,
            matched_id=best.id if blocked and best else None,
            nearest=nearest,
        )

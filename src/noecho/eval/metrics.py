"""Scoring labeled pairs with the gate and computing classification metrics.

The positive class is ``duplicate``: a pair is predicted duplicate when the
gate's best score against the thread is at or above the threshold, exactly as
``UniquenessGate.check`` decides. Precision answers "of what the gate blocks,
how much really was a repeat?"; recall answers "of the real repeats, how many
did it block?". Low precision means suppressed new points, which the design
treats as the worse error.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from noecho.core.gate import Prior, UniquenessGate
from noecho.eval.pairs import Label, LabeledPair


@dataclass(frozen=True, slots=True)
class ScoredPair:
    pair: LabeledPair
    score: float
    nearest_index: int | None
    """Index into ``pair.thread`` of the best-scoring comment."""


def score_pairs(pairs: Iterable[LabeledPair], gate: UniquenessGate) -> list[ScoredPair]:
    """Run the gate's backend on each pair. Thread comments get ids 0..n-1."""
    scored: list[ScoredPair] = []
    for pair in pairs:
        priors = [Prior(i, body) for i, body in enumerate(pair.thread)]
        decision = gate.check(pair.candidate, priors)
        nearest = decision.nearest[0].id if decision.nearest else None
        scored.append(ScoredPair(pair, decision.score, nearest))
    return scored


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


@dataclass(frozen=True, slots=True)
class Confusion:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.fn + self.tn

    @property
    def precision(self) -> float | None:
        """None when nothing was predicted duplicate (undefined, not zero)."""
        return _ratio(self.tp, self.tp + self.fp)

    @property
    def recall(self) -> float | None:
        """None when the corpus slice has no duplicate pairs."""
        return _ratio(self.tp, self.tp + self.fn)

    @property
    def f1(self) -> float | None:
        """2TP / (2TP + FP + FN): zero when there are errors but no hits, None
        only when there are neither positives nor predicted positives."""
        return _ratio(2 * self.tp, 2 * self.tp + self.fp + self.fn)


def is_blocked(score: float, threshold: float) -> bool:
    return score >= threshold


def confusion(scored: Iterable[ScoredPair], threshold: float) -> Confusion:
    tp = fp = fn = tn = 0
    for s in scored:
        predicted = is_blocked(s.score, threshold)
        actual = s.pair.label is Label.DUPLICATE
        if predicted and actual:
            tp += 1
        elif predicted:
            fp += 1
        elif actual:
            fn += 1
        else:
            tn += 1
    return Confusion(tp, fp, fn, tn)


@dataclass(frozen=True, slots=True)
class ScoreSummary:
    n: int
    minimum: float
    mean: float
    median: float
    maximum: float


def summarize(scores: Sequence[float]) -> ScoreSummary | None:
    if not scores:
        return None
    return ScoreSummary(
        n=len(scores),
        minimum=min(scores),
        mean=statistics.fmean(scores),
        median=statistics.median(scores),
        maximum=max(scores),
    )


def scores_by_label(scored: Iterable[ScoredPair]) -> dict[Label, list[float]]:
    out: dict[Label, list[float]] = {label: [] for label in Label}
    for s in scored:
        out[s.pair.label].append(s.score)
    return out


def sweep_thresholds(current: float, step: float = 0.05) -> list[float]:
    """Thresholds from ``step`` to ``1 - step`` in ``step`` increments, plus ``current``."""
    count = round(1 / step)
    grid = {round(i * step, 4) for i in range(1, count)}
    grid.add(round(current, 4))
    return sorted(grid)


def histogram(scores: Iterable[float], bins: int = 20) -> list[int]:
    """Counts of scores in ``bins`` equal-width bins over [0, 1]. The last bin
    includes 1.0."""
    counts = [0] * bins
    for score in scores:
        # Rounding first keeps 0.45 * 20 from landing in bin 8 via float error.
        index = min(int(round(score * bins, 9)), bins - 1)
        counts[max(index, 0)] += 1
    return counts

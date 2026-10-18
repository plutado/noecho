"""Metric math for the gate evaluation harness."""

from __future__ import annotations

import pytest

from noecho.core.gate import UniquenessGate
from noecho.eval.metrics import (
    Confusion,
    ScoredPair,
    confusion,
    histogram,
    score_pairs,
    scores_by_label,
    summarize,
    sweep_thresholds,
)
from noecho.eval.pairs import Label, LabeledPair


def _scored(pid: str, label: str, score: float) -> ScoredPair:
    pair = LabeledPair(id=pid, thread=("x",), candidate="y", label=Label(label))
    return ScoredPair(pair, score, 0)


# Four duplicates and four new points with hand-picked scores.
SCORED = [
    _scored("d1", "duplicate", 0.90),
    _scored("d2", "duplicate", 0.60),
    _scored("d3", "duplicate", 0.45),  # exactly at the threshold: blocked
    _scored("d4", "duplicate", 0.20),
    _scored("n1", "new", 0.50),
    _scored("n2", "new", 0.30),
    _scored("n3", "new", 0.10),
    _scored("n4", "new", 0.00),
]


def test_confusion_counts_and_boundary():
    c = confusion(SCORED, 0.45)
    assert (c.tp, c.fp, c.fn, c.tn) == (3, 1, 1, 3)
    assert c.total == 8


def test_precision_recall_f1():
    c = confusion(SCORED, 0.45)
    assert c.precision == pytest.approx(3 / 4)
    assert c.recall == pytest.approx(3 / 4)
    assert c.f1 == pytest.approx(0.75)

    c = confusion(SCORED, 0.55)  # d1, d2 blocked; n1 now passes
    assert (c.tp, c.fp, c.fn, c.tn) == (2, 0, 2, 4)
    assert c.precision == 1.0
    assert c.recall == 0.5
    assert c.f1 == pytest.approx(2 * 1.0 * 0.5 / 1.5)


def test_undefined_metrics_are_none_not_zero():
    nothing_blocked = Confusion(tp=0, fp=0, fn=3, tn=2)
    assert nothing_blocked.precision is None
    assert nothing_blocked.recall == 0.0
    assert nothing_blocked.f1 == 0.0

    no_duplicates = Confusion(tp=0, fp=0, fn=0, tn=5)
    assert no_duplicates.precision is None
    assert no_duplicates.recall is None
    assert no_duplicates.f1 is None


def test_summarize():
    s = summarize([0.1, 0.4, 0.2, 0.9])
    assert s is not None
    assert (s.n, s.minimum, s.maximum) == (4, 0.1, 0.9)
    assert s.mean == pytest.approx(0.4)
    assert s.median == pytest.approx(0.3)
    assert summarize([]) is None


def test_scores_by_label_keeps_both_labels():
    by_label = scores_by_label(SCORED[:1])
    assert by_label == {Label.DUPLICATE: [0.90], Label.NEW: []}


def test_histogram_bins():
    counts = histogram([0.0, 0.049, 0.05, 0.45, 0.4499, 0.999, 1.0], bins=20)
    assert len(counts) == 20
    assert counts[0] == 2
    assert counts[1] == 1
    assert counts[8] == 1
    assert counts[9] == 1  # 0.45 lands in [0.45, 0.50), matching the gate's >=
    assert counts[19] == 2  # 1.0 is included in the last bin
    assert sum(counts) == 7


def test_sweep_thresholds_include_current():
    grid = sweep_thresholds(0.45)
    assert grid[0] == 0.05 and grid[-1] == 0.95
    assert len(grid) == 19
    assert 0.42 in sweep_thresholds(0.42)
    assert grid == sorted(grid)


def test_score_pairs_uses_the_gate_and_reports_nearest():
    pair = LabeledPair(
        id="p",
        thread=("Rain barrels need lids.", "The tram stop is two blocks away."),
        candidate="The tram stop is two blocks away.",
        label=Label.DUPLICATE,
    )
    [s] = score_pairs([pair], UniquenessGate())
    assert s.score == 1.0
    assert s.nearest_index == 1

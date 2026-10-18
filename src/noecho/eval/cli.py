"""``noecho-eval``: measure the uniqueness gate against a labeled pair corpus.

    uv run noecho-eval                          # evals/pairs.jsonl at the configured threshold
    uv run noecho-eval path/to/pairs.jsonl --threshold 0.4
    uv run noecho-eval --sweep                  # add a threshold table and score histograms

The threshold defaults to ``NOECHO_GATE_THRESHOLD`` (or the built-in default).
Output is plain text on stdout. Exit status is 2 if the corpus cannot be read.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from noecho.config import load_settings
from noecho.core.gate import UniquenessGate
from noecho.eval.metrics import (
    Confusion,
    ScoredPair,
    confusion,
    histogram,
    is_blocked,
    score_pairs,
    scores_by_label,
    summarize,
    sweep_thresholds,
)
from noecho.eval.pairs import Label, PairFormatError, load_pairs

DEFAULT_CORPUS = "evals/pairs.jsonl"
HISTOGRAM_BINS = 20
BAR_WIDTH = 30


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _metrics_line(c: Confusion) -> str:
    return f"precision {_fmt(c.precision)}  recall {_fmt(c.recall)}  F1 {_fmt(c.f1)}"


def format_report(scored: Sequence[ScoredPair], threshold: float, backend: str, source: str) -> str:
    by_label = scores_by_label(scored)
    topics = sorted({s.pair.topic for s in scored if s.pair.topic})
    c = confusion(scored, threshold)
    lines = [
        f"corpus     {source}",
        f"pairs      {len(scored)} ({len(by_label[Label.DUPLICATE])} duplicate, "
        f"{len(by_label[Label.NEW])} new) across {len(topics)} topic(s)",
        f"backend    {backend}",
        f"threshold  {threshold:g}  (blocked when score >= threshold; positive class: duplicate)",
        "",
        f"TP {c.tp}  FP {c.fp}  FN {c.fn}  TN {c.tn}",
        _metrics_line(c),
        "",
        "scores by label      n     min    mean  median     max",
    ]
    for label in Label:
        summary = summarize(by_label[label])
        if summary is None:
            lines.append(f"  {label.value:<14} {0:>4}       -       -       -       -")
            continue
        lines.append(
            f"  {label.value:<14} {summary.n:>4}  {summary.minimum:.4f}  {summary.mean:.4f}  "
            f"{summary.median:.4f}  {summary.maximum:.4f}"
        )

    if topics:
        lines += ["", "by topic                        n  precision  recall      F1"]
        for topic in topics:
            tc = confusion([s for s in scored if s.pair.topic == topic], threshold)
            lines.append(
                f"  {topic:<28} {tc.total:>3}  {_fmt(tc.precision):>9}  {_fmt(tc.recall):>6}  "
                f"{_fmt(tc.f1):>6}"
            )

    errors = [
        s for s in scored if is_blocked(s.score, threshold) != (s.pair.label is Label.DUPLICATE)
    ]
    lines += ["", f"misclassified at {threshold:g}: {len(errors)}"]
    for s in sorted(errors, key=lambda s: (s.pair.label, -s.score, s.pair.id)):
        kind = "FN" if s.pair.label is Label.DUPLICATE else "FP"
        note = f"  {s.pair.note}" if s.pair.note else ""
        lines.append(f"  {kind} {s.pair.id:<14} {s.score:.4f}{note}")
    return "\n".join(lines)


def format_sweep(scored: Sequence[ScoredPair], threshold: float) -> str:
    lines = [
        "threshold sweep ('*' marks the current threshold)",
        "  threshold   TP   FP   FN   TN  precision  recall      F1",
    ]
    for t in sweep_thresholds(threshold):
        c = confusion(scored, t)
        mark = "*" if abs(t - threshold) < 1e-9 else " "
        lines.append(
            f"  {mark}{t:>8.2f}  {c.tp:>3}  {c.fp:>3}  {c.fn:>3}  {c.tn:>3}  "
            f"{_fmt(c.precision):>9}  {_fmt(c.recall):>6}  {_fmt(c.f1):>6}"
        )

    by_label = scores_by_label(scored)
    counts = {label: histogram(by_label[label], HISTOGRAM_BINS) for label in Label}
    peak = max(max(v) for v in counts.values()) or 1
    scale = min(1.0, BAR_WIDTH / peak)
    width = 1 / HISTOGRAM_BINS
    threshold_bin = min(int(round(threshold * HISTOGRAM_BINS, 9)), HISTOGRAM_BINS - 1)

    def cell(n: int) -> str:
        bar = "#" * (round(n * scale) if n else 0)
        if n and not bar:
            bar = "#"
        return f"{n:>3} {bar:<{BAR_WIDTH}}"

    lines += [
        "",
        f"score histogram (bin width {width:g}; '>' marks the bin containing the threshold"
        + ("" if scale == 1.0 else f"; one '#' is about {1 / scale:.1f} pairs")
        + ")",
        f"  {'bin':<11}  {'duplicate':<{BAR_WIDTH + 4}}  new",
    ]
    for i in range(HISTOGRAM_BINS):
        lo, hi = i * width, (i + 1) * width
        mark = ">" if i == threshold_bin else " "
        row = f" {mark}{lo:.2f}-{hi:.2f}    {cell(counts[Label.DUPLICATE][i])}  "
        lines.append((row + cell(counts[Label.NEW][i])).rstrip())
    return "\n".join(lines)


def _threshold(value: str) -> float:
    t = float(value)
    if not 0.0 < t <= 1.0:
        raise argparse.ArgumentTypeError("threshold must be in (0, 1]")
    return t


def main(argv: list[str] | None = None) -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(
        prog="noecho-eval",
        description="Evaluate the uniqueness gate against a labeled pair corpus (JSONL).",
    )
    parser.add_argument(
        "corpus", nargs="?", default=DEFAULT_CORPUS, help=f"default: {DEFAULT_CORPUS}"
    )
    parser.add_argument(
        "--threshold",
        type=_threshold,
        default=settings.gate_threshold,
        help=f"gate threshold (default from config: {settings.gate_threshold:g})",
    )
    parser.add_argument(
        "--sweep", action="store_true", help="also print a threshold table and score histograms"
    )
    args = parser.parse_args(argv)

    try:
        pairs = load_pairs(args.corpus)
    except FileNotFoundError:
        print(f"noecho-eval: corpus not found: {args.corpus}", file=sys.stderr)
        return 2
    except PairFormatError as exc:
        print(f"noecho-eval: {exc}", file=sys.stderr)
        return 2

    gate = UniquenessGate(threshold=args.threshold)
    scored = score_pairs(pairs, gate)
    print(format_report(scored, args.threshold, gate.backend.name, args.corpus))
    if args.sweep:
        print()
        print(format_sweep(scored, args.threshold))
    return 0


def entrypoint() -> None:
    sys.exit(main())


if __name__ == "__main__":
    entrypoint()

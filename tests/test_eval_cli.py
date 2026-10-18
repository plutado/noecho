"""The noecho-eval command and the shipped starter corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from noecho.eval.cli import main
from noecho.eval.pairs import Label, load_pairs

ROOT = Path(__file__).resolve().parent.parent
STARTER = ROOT / "evals" / "pairs.jsonl"

THREAD = ["The tram stop is two blocks from the garage.", "Rain barrels need lids."]


@pytest.fixture
def corpus(tmp_path) -> Path:
    records = [
        {
            "id": "echo",
            "topic": "a",
            "thread": THREAD,
            "candidate": THREAD[0],
            "label": "duplicate",
        },
        {
            "id": "missed",
            "topic": "a",
            "thread": THREAD,
            "candidate": "Transit is a short walk away.",
            "label": "duplicate",
            "note": "reworded echo",
        },
        {
            "id": "fresh",
            "topic": "b",
            "thread": THREAD,
            "candidate": "The market could move to Fenwick Road.",
            "label": "new",
        },
    ]
    path = tmp_path / "pairs.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def test_report_at_threshold(corpus, capsys):
    assert main([str(corpus), "--threshold", "0.45"]) == 0
    out = capsys.readouterr().out
    assert "pairs      3 (2 duplicate, 1 new) across 2 topic(s)" in out
    assert "backend    tfidf-local" in out
    assert "threshold  0.45" in out
    assert "TP 1  FP 0  FN 1  TN 1" in out
    assert "precision 1.000  recall 0.500  F1 0.667" in out
    assert "  duplicate         2  " in out
    assert "  new               1  " in out
    assert "misclassified at 0.45: 1" in out
    assert "FN missed" in out and "reworded echo" in out
    assert "threshold sweep" not in out


def test_threshold_defaults_to_config(corpus, capsys, monkeypatch):
    monkeypatch.setenv("NOECHO_GATE_THRESHOLD", "0.3")
    assert main([str(corpus)]) == 0
    assert "threshold  0.3 " in capsys.readouterr().out


def test_sweep_prints_table_and_histogram(corpus, capsys):
    assert main([str(corpus), "--sweep"]) == 0
    out = capsys.readouterr().out
    assert "threshold sweep" in out
    star = [line for line in out.splitlines() if line.startswith("  *")]
    assert len(star) == 1 and "0.45" in star[0]
    assert "score histogram (bin width 0.05" in out
    assert " >0.45-0.50" in out
    last_bin = next(line for line in out.splitlines() if "0.95-1.00" in line)
    assert "  1 #" in last_bin  # the exact echo scores 1.0


@pytest.mark.parametrize("bad", ["0", "1.5", "abc"])
def test_bad_threshold_is_rejected(corpus, bad):
    with pytest.raises(SystemExit) as info:
        main([str(corpus), "--threshold", bad])
    assert info.value.code == 2


def test_missing_corpus_exits_2(tmp_path, capsys):
    assert main([str(tmp_path / "nope.jsonl")]) == 2
    assert "corpus not found" in capsys.readouterr().err


def test_malformed_corpus_exits_2_with_location(tmp_path, capsys):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"thread": ["x"], "candidate": "y", "label": "maybe"}\n', encoding="utf-8")
    assert main([str(path)]) == 2
    err = capsys.readouterr().err
    assert f"{path}:1:" in err and "'label' must be one of" in err


def test_starter_corpus_is_valid_and_covers_the_hard_cases():
    pairs = load_pairs(STARTER)
    assert 40 <= len(pairs) <= 60
    assert len({p.topic for p in pairs}) >= 3
    assert {p.label for p in pairs} == set(Label)
    notes = [(p.label, p.note or "") for p in pairs]
    assert any(label is Label.DUPLICATE and "convergence" in n for label, n in notes)
    assert any(label is Label.NEW and "new implication" in n for label, n in notes)
    text = STARTER.read_text(encoding="utf-8")
    assert "http" not in text or "example.org" in text


def test_starter_corpus_runs(capsys):
    assert main([str(STARTER), "--sweep"]) == 0
    assert "pairs      " in capsys.readouterr().out

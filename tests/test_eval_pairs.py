"""Labeled pair format and loader."""

from __future__ import annotations

import json

import pytest

from noecho.eval.pairs import Label, LabeledPair, PairFormatError, load_pairs, parse_pairs


def _line(**fields) -> str:
    base = {"thread": ["An existing comment."], "candidate": "A submission.", "label": "new"}
    base.update(fields)
    return json.dumps({k: v for k, v in base.items() if v is not ...})


def test_parses_a_full_record():
    text = _line(id="p1", topic="t", note="why", label="duplicate")
    [pair] = parse_pairs(text)
    assert pair == LabeledPair(
        id="p1",
        thread=("An existing comment.",),
        candidate="A submission.",
        label=Label.DUPLICATE,
        topic="t",
        note="why",
    )


def test_optional_fields_default():
    [pair] = parse_pairs("\n" + _line())
    assert pair.id == "line-2"
    assert pair.topic is None
    assert pair.note is None
    assert pair.label is Label.NEW


def test_blank_and_comment_lines_are_skipped():
    text = "# header\n\n" + _line(id="a") + "\n   \n" + _line(id="b") + "\n"
    assert [p.id for p in parse_pairs(text)] == ["a", "b"]


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("{not json", "invalid JSON"),
        ("[1, 2]", "expected a JSON object, got list"),
        (_line(thread=...), "missing required field(s): thread"),
        (_line(label=...), "missing required field(s): label"),
        (_line(thread=[]), "'thread' must be a non-empty list"),
        (_line(thread="one comment"), "'thread' must be a non-empty list"),
        (_line(thread=["ok", ""]), "'thread[1]' must be a non-empty string"),
        (_line(thread=["ok", 3]), "'thread[1]' must be a non-empty string"),
        (_line(candidate="   "), "'candidate' must be a non-empty string"),
        (_line(label="dup"), "'label' must be one of 'duplicate', 'new', got 'dup'"),
        (_line(id=7), "'id' must be a non-empty string"),
        (_line(topic=["x"]), "'topic' must be a string or null"),
        (_line(notes="typo"), "unknown field(s): notes"),
    ],
)
def test_invalid_records_raise_with_location(line, message):
    with pytest.raises(PairFormatError) as info:
        parse_pairs("# comment\n" + line, source="corpus.jsonl")
    assert str(info.value).startswith("corpus.jsonl:2: ")
    assert message in str(info.value)
    assert info.value.line == 2


def test_duplicate_ids_are_rejected():
    text = _line(id="same") + "\n" + _line(id="same")
    with pytest.raises(PairFormatError, match=r":2: duplicate id 'same' \(first used on line 1\)"):
        parse_pairs(text)


def test_load_pairs_reads_a_file(tmp_path):
    path = tmp_path / "pairs.jsonl"
    path.write_text(_line(id="x") + "\n", encoding="utf-8")
    assert [p.id for p in load_pairs(path)] == ["x"]


def test_load_pairs_rejects_an_empty_corpus(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("# nothing here\n", encoding="utf-8")
    with pytest.raises(PairFormatError, match="no records"):
        load_pairs(path)

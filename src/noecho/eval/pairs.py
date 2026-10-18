"""Labeled pair format for evaluating the uniqueness gate.

A corpus is a JSONL file: one JSON object per line. Blank lines and lines whose
first non-space character is ``#`` are ignored. Each record looks like::

    {"id": "bike-01",
     "topic": "ostmere-bike-lane",
     "thread": ["existing comment one", "existing comment two"],
     "candidate": "the submission being judged",
     "label": "duplicate",
     "note": "paraphrase of thread[0]"}

Fields:

* ``thread`` (required): the bodies of the comments already in the thread, as
  a non-empty list of non-empty strings.
* ``candidate`` (required): the submission, a non-empty string.
* ``label`` (required): ``"duplicate"`` if the candidate makes a point the
  thread already contains (the gate should block it), ``"new"`` otherwise.
* ``id`` (optional): a unique string; defaults to ``"line-N"``.
* ``topic`` (optional): a string used to group results.
* ``note`` (optional): free text explaining the label.

Unknown fields are rejected so that a misspelt key is not silently ignored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class Label(StrEnum):
    DUPLICATE = "duplicate"
    NEW = "new"


@dataclass(frozen=True, slots=True)
class LabeledPair:
    id: str
    thread: tuple[str, ...]
    candidate: str
    label: Label
    topic: str | None = None
    note: str | None = None


class PairFormatError(ValueError):
    """A corpus record is malformed. The message names the file and line."""

    def __init__(self, source: str, line: int, message: str) -> None:
        super().__init__(f"{source}:{line}: {message}")
        self.source = source
        self.line = line


_REQUIRED = ("thread", "candidate", "label")
_ALLOWED = frozenset({*_REQUIRED, "id", "topic", "note"})


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def parse_pair(record: Any, *, source: str = "<record>", line: int = 1) -> LabeledPair:
    """Validate one decoded JSON value and return a ``LabeledPair``, or raise."""

    def fail(message: str) -> PairFormatError:
        return PairFormatError(source, line, message)

    if not isinstance(record, dict):
        raise fail(f"expected a JSON object, got {type(record).__name__}")
    unknown = sorted(set(record) - _ALLOWED)
    if unknown:
        raise fail(f"unknown field(s): {', '.join(unknown)}")
    missing = [k for k in _REQUIRED if k not in record]
    if missing:
        raise fail(f"missing required field(s): {', '.join(missing)}")

    thread = record["thread"]
    if not isinstance(thread, list) or not thread:
        raise fail("'thread' must be a non-empty list of comment bodies")
    for i, body in enumerate(thread):
        if not _nonempty_str(body):
            raise fail(f"'thread[{i}]' must be a non-empty string")

    candidate = record["candidate"]
    if not _nonempty_str(candidate):
        raise fail("'candidate' must be a non-empty string")

    raw_label = record["label"]
    try:
        label = Label(raw_label)
    except ValueError:
        allowed = ", ".join(repr(v.value) for v in Label)
        raise fail(f"'label' must be one of {allowed}, got {raw_label!r}") from None

    pair_id = record.get("id", f"line-{line}")
    if not _nonempty_str(pair_id):
        raise fail("'id' must be a non-empty string")
    for key in ("topic", "note"):
        value = record.get(key)
        if value is not None and not isinstance(value, str):
            raise fail(f"'{key}' must be a string or null")

    return LabeledPair(
        id=pair_id,
        thread=tuple(thread),
        candidate=candidate,
        label=label,
        topic=record.get("topic") or None,
        note=record.get("note") or None,
    )


def parse_pairs(text: str, *, source: str = "<string>") -> list[LabeledPair]:
    """Parse JSONL text into pairs. Ids must be unique across the corpus."""
    pairs: list[LabeledPair] = []
    seen: dict[str, int] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise PairFormatError(source, lineno, f"invalid JSON: {exc.msg}") from None
        pair = parse_pair(record, source=source, line=lineno)
        if pair.id in seen:
            raise PairFormatError(
                source, lineno, f"duplicate id {pair.id!r} (first used on line {seen[pair.id]})"
            )
        seen[pair.id] = lineno
        pairs.append(pair)
    return pairs


def load_pairs(path: str | Path) -> list[LabeledPair]:
    """Read and validate a JSONL corpus file. Raises ``PairFormatError`` if it
    is malformed or contains no records."""
    path = Path(path)
    pairs = parse_pairs(path.read_text(encoding="utf-8"), source=str(path))
    if not pairs:
        raise PairFormatError(str(path), 0, "corpus contains no records")
    return pairs

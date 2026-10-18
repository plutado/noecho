"""Load invented sample data.

Every place, person, organization, and URL below is made up. Source links use
the reserved example.org domain. Usage:

    uv run noecho-seed            # writes to NOECHO_DB_PATH (default ./noecho.db)
    uv run noecho-seed --db x.db
"""

from __future__ import annotations

import argparse

from noecho.config import load_settings
from noecho.core.gate import UniquenessGate
from noecho.core.models import ClaimKind, Stance
from noecho.service import Engine
from noecho.storage.sqlite import SQLiteStore

SAMPLE_THREADS: list[dict] = [
    {
        "title": "Brackenford council proposal: convert the Halvern Street garage to housing",
        "source_url": "https://example.org/brackenford/halvern-garage-proposal",
        "comments": [
            (
                "sample-user-01",
                "The garage sits two blocks from the tram stop, so residents there could "
                "plausibly live without a car.",
            ),
            (
                "sample-user-02",
                "Parking structures have low ceilings and sloped floors; the conversion cost "
                "per unit may exceed new construction.",
            ),
            (
                "sample-user-03",
                "Nobody has said what happens to the evening market that uses the ground "
                "floor on weekends.",
            ),
            (
                "sample-user-04",
                "I think the town should keep a small number of accessible spaces for "
                "disabled drivers regardless of the outcome.",
            ),
        ],
        "echo_attempt": (
            "sample-user-05",
            "Since the tram stop is only two blocks from the garage, people living there "
            "could plausibly do without a car.",
        ),
        "claims": [
            {
                "comment_index": 1,
                "text": "Garage conversions cost more per unit than new construction.",
                "kind": ClaimKind.FACTUAL,
                "citations": [
                    ("https://example.org/studies/garage-conversion-costs", Stance.SUPPORTS),
                    ("https://example.net/reports/adaptive-reuse-2025", Stance.REFUTES),
                ],
            },
            {
                "comment_index": 3,
                "text": "Accessible spaces should be retained.",
                "kind": ClaimKind.OPINION,
                "citations": [],
            },
        ],
    },
    {
        "title": "Corriel school district pilots a four-day week",
        "source_url": None,
        "comments": [
            (
                "sample-user-06",
                "The pilot covers only the two smallest schools, so its results may not say "
                "much about the larger campuses.",
            ),
            (
                "sample-user-07",
                "Families who rely on school meals lose one meal a day under this schedule.",
            ),
        ],
        "echo_attempt": None,
        "claims": [
            {
                "comment_index": 0,
                "text": "The pilot covers only the two smallest schools.",
                "kind": ClaimKind.FACTUAL,
                "citations": [],
            },
        ],
    },
]


def seed(engine: Engine) -> None:
    for spec in SAMPLE_THREADS:
        thread = engine.create_thread(spec["title"], spec["source_url"])
        print(f"thread {thread.id}: {thread.title}")
        posted = []
        for author, body in spec["comments"]:
            result = engine.post_comment(thread.id, author, body)
            if result.comment is None:
                raise RuntimeError(f"sample comment unexpectedly blocked: {body!r}")
            posted.append(result.comment)
        if spec["echo_attempt"]:
            author, body = spec["echo_attempt"]
            result = engine.post_comment(thread.id, author, body)
            if result.matched:
                print(
                    f"  echo blocked (score {result.decision.score:.2f}), "
                    f"matched comment {result.matched.id}"
                )
        for c in spec["claims"]:
            claim = engine.add_claim(posted[c["comment_index"]].id, c["text"], c["kind"])
            for url, stance in c["citations"]:
                _, claim = engine.attach_citation(claim.id, url, stance)
            print(f"  claim {claim.id} [{claim.status}]: {claim.text}")


def main(argv: list[str] | None = None) -> None:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Load invented sample threads.")
    parser.add_argument("--db", default=settings.db_path, help="SQLite file path")
    args = parser.parse_args(argv)
    engine = Engine(
        SQLiteStore(args.db),
        UniquenessGate(threshold=settings.gate_threshold),
        min_sources=settings.min_sources,
    )
    seed(engine)


if __name__ == "__main__":
    main()

from __future__ import annotations

from noecho.core.models import ClaimStatus
from noecho.seed import SAMPLE_THREADS, seed


def test_seed_loads_and_blocks_the_echo(engine, capsys):
    seed(engine)
    out = capsys.readouterr().out
    assert "echo blocked" in out
    threads = engine.list_threads()
    assert len(threads) == len(SAMPLE_THREADS)
    first = engine.list_comments(threads[0].id)
    assert len(first) == len(SAMPLE_THREADS[0]["comments"])
    statuses = {c.status for c in engine.list_claims(first[1].id)}
    assert statuses == {ClaimStatus.DISPUTED}

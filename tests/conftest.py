from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from noecho.api.app import create_app
from noecho.config import Settings
from noecho.core.gate import UniquenessGate
from noecho.service import Engine
from noecho.storage.sqlite import SQLiteStore


class TickingClock:
    """Deterministic clock: each call advances one second."""

    def __init__(self) -> None:
        self.t = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.t += timedelta(seconds=1)
        return self.t


@pytest.fixture
def engine() -> Iterator[Engine]:
    store = SQLiteStore(":memory:", clock=TickingClock())
    yield Engine(store, UniquenessGate())
    store.close()


@pytest.fixture
def client(engine: Engine) -> TestClient:
    return TestClient(create_app(Settings(db_path=":memory:"), engine=engine))

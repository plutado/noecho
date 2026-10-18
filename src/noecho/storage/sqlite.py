"""SQLite storage. The only module that knows about SQL.

Uses the standard library ``sqlite3`` driver. One connection per store,
guarded by a lock, which is adequate for a single-process deployment. The
Postgres + pgvector store on the roadmap will implement the same methods.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from noecho.core.models import Citation, Claim, ClaimKind, ClaimStatus, Comment, Stance, Thread

SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    source_url  TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id          INTEGER PRIMARY KEY,
    thread_id   INTEGER NOT NULL REFERENCES threads(id),
    author      TEXT NOT NULL,
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS comments_thread_time ON comments(thread_id, created_at, id);

CREATE TABLE IF NOT EXISTS claims (
    id          INTEGER PRIMARY KEY,
    comment_id  INTEGER NOT NULL REFERENCES comments(id),
    text        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('factual', 'opinion')),
    status      TEXT NOT NULL CHECK (
                    status IN ('verified', 'unverified', 'refuted', 'disputed', 'opinion')),
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS claims_comment ON claims(comment_id);

CREATE TABLE IF NOT EXISTS citations (
    id              INTEGER PRIMARY KEY,
    claim_id        INTEGER NOT NULL REFERENCES claims(id),
    url             TEXT NOT NULL,
    normalized_url  TEXT NOT NULL,
    stance          TEXT NOT NULL CHECK (stance IN ('supports', 'refutes')),
    note            TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE (claim_id, normalized_url)
);
"""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SQLiteStore:
    def __init__(self, path: str = ":memory:", clock: Callable[[], datetime] = _utcnow) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._lock = threading.RLock()
        self._clock = clock

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Serialize a read-then-write sequence (used by the gate's check+insert)."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def _now(self) -> str:
        return self._clock().isoformat()

    def _insert(self, sql: str, params: tuple) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            assert cur.lastrowid is not None
            return cur.lastrowid

    def _one(self, sql: str, params: tuple) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def _all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # Threads

    def create_thread(self, title: str, source_url: str | None = None) -> Thread:
        tid = self._insert(
            "INSERT INTO threads (title, source_url, created_at) VALUES (?, ?, ?)",
            (title, source_url, self._now()),
        )
        thread = self.get_thread(tid)
        assert thread is not None
        return thread

    def get_thread(self, thread_id: int) -> Thread | None:
        row = self._one("SELECT * FROM threads WHERE id = ?", (thread_id,))
        return _thread(row) if row else None

    def list_threads(self) -> list[Thread]:
        return [_thread(r) for r in self._all("SELECT * FROM threads ORDER BY created_at, id")]

    # Comments

    def add_comment(self, thread_id: int, author: str, body: str) -> Comment:
        cid = self._insert(
            "INSERT INTO comments (thread_id, author, body, created_at) VALUES (?, ?, ?, ?)",
            (thread_id, author, body, self._now()),
        )
        comment = self.get_comment(cid)
        assert comment is not None
        return comment

    def get_comment(self, comment_id: int) -> Comment | None:
        row = self._one("SELECT * FROM comments WHERE id = ?", (comment_id,))
        return _comment(row) if row else None

    def list_comments(self, thread_id: int) -> list[Comment]:
        rows = self._all(
            "SELECT * FROM comments WHERE thread_id = ? ORDER BY created_at, id", (thread_id,)
        )
        return [_comment(r) for r in rows]

    # Claims

    def add_claim(self, comment_id: int, text: str, kind: ClaimKind, status: ClaimStatus) -> Claim:
        cid = self._insert(
            "INSERT INTO claims (comment_id, text, kind, status, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (comment_id, text, kind.value, status.value, self._now()),
        )
        claim = self.get_claim(cid)
        assert claim is not None
        return claim

    def get_claim(self, claim_id: int) -> Claim | None:
        row = self._one("SELECT * FROM claims WHERE id = ?", (claim_id,))
        return _claim(row) if row else None

    def list_claims(self, comment_id: int) -> list[Claim]:
        rows = self._all("SELECT * FROM claims WHERE comment_id = ? ORDER BY id", (comment_id,))
        return [_claim(r) for r in rows]

    def set_claim_status(self, claim_id: int, status: ClaimStatus) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE claims SET status = ? WHERE id = ?", (status.value, claim_id)
            )

    # Citations

    def add_citation(
        self, claim_id: int, url: str, normalized_url: str, stance: Stance, note: str | None
    ) -> Citation:
        cid = self._insert(
            "INSERT INTO citations (claim_id, url, normalized_url, stance, note, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (claim_id, url, normalized_url, stance.value, note, self._now()),
        )
        row = self._one("SELECT * FROM citations WHERE id = ?", (cid,))
        assert row is not None
        return _citation(row)

    def list_citations(self, claim_id: int) -> list[Citation]:
        rows = self._all("SELECT * FROM citations WHERE claim_id = ? ORDER BY id", (claim_id,))
        return [_citation(r) for r in rows]


def _thread(r: sqlite3.Row) -> Thread:
    return Thread(r["id"], r["title"], r["source_url"], _ts(r["created_at"]))


def _comment(r: sqlite3.Row) -> Comment:
    return Comment(r["id"], r["thread_id"], r["author"], r["body"], _ts(r["created_at"]))


def _claim(r: sqlite3.Row) -> Claim:
    return Claim(
        r["id"],
        r["comment_id"],
        r["text"],
        ClaimKind(r["kind"]),
        ClaimStatus(r["status"]),
        _ts(r["created_at"]),
    )


def _citation(r: sqlite3.Row) -> Citation:
    return Citation(
        r["id"],
        r["claim_id"],
        r["url"],
        r["normalized_url"],
        Stance(r["stance"]),
        r["note"],
        _ts(r["created_at"]),
    )

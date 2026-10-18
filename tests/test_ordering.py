from __future__ import annotations

from datetime import UTC, datetime

from noecho.core.models import Comment
from noecho.core.ordering import Order, order_comments

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)


def _c(id_: int, when: datetime) -> Comment:
    return Comment(id=id_, thread_id=1, author="a", body=f"b{id_}", created_at=when)


def test_chronological_is_default():
    comments = [_c(2, T1), _c(1, T0)]
    assert [c.id for c in order_comments(comments)] == [1, 2]


def test_reverse():
    comments = [_c(1, T0), _c(2, T1)]
    assert [c.id for c in order_comments(comments, Order.REVERSE)] == [2, 1]


def test_equal_timestamps_break_ties_on_id():
    comments = [_c(3, T0), _c(1, T0), _c(2, T0)]
    assert [c.id for c in order_comments(comments)] == [1, 2, 3]
    assert [c.id for c in order_comments(comments, Order.REVERSE)] == [3, 2, 1]


def test_engine_lists_in_both_orders(engine):
    thread = engine.create_thread("Ordering")
    bodies = ["Bus lanes speed up transit.", "Bike racks are full by noon.", "Fares went up."]
    for b in bodies:
        assert engine.post_comment(thread.id, "x", b).comment is not None
    assert [c.body for c in engine.list_comments(thread.id)] == bodies
    assert [c.body for c in engine.list_comments(thread.id, Order.REVERSE)] == bodies[::-1]

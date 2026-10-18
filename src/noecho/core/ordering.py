"""Thread ordering. Time is the only sort key the engine offers."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from noecho.core.models import Comment


class Order(StrEnum):
    CHRONOLOGICAL = "chronological"
    REVERSE = "reverse"


def order_comments(
    comments: Iterable[Comment], order: Order = Order.CHRONOLOGICAL
) -> list[Comment]:
    """Sort by creation time, with id as a tiebreaker so equal timestamps are stable."""
    return sorted(
        comments,
        key=lambda c: (c.created_at, c.id),
        reverse=order is Order.REVERSE,
    )

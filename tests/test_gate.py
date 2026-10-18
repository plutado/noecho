"""Uniqueness gate behaviour and the fixture set the default threshold was tuned on."""

from __future__ import annotations

import pytest

from noecho.core.gate import DEFAULT_THRESHOLD, Prior, UniquenessGate
from noecho.core.similarity import TfidfSimilarity

THREAD = [
    Prior(
        1,
        "The garage sits two blocks from the tram stop, so residents there could "
        "plausibly live without a car.",
    ),
    Prior(
        2,
        "Parking structures have low ceilings and sloped floors; the conversion cost "
        "per unit may exceed new construction.",
    ),
    Prior(
        3,
        "Nobody has said what happens to the evening market that uses the ground "
        "floor on weekends.",
    ),
    Prior(
        4,
        "I think the town should keep a small number of accessible spaces for "
        "disabled drivers regardless of the outcome.",
    ),
]

# (candidate, id of the comment it echoes)
ECHOES = [
    (
        "The garage sits two blocks from the tram stop, so residents there could plausibly "
        "live without a car!!",
        1,
    ),
    ("the garage sits 2 blocks from the tram stop so residents could live without a car", 1),
    (
        "Since the tram stop is only two blocks from the garage, people living there could "
        "plausibly do without a car.",
        1,
    ),
    (
        "Parking garages have low ceilings and sloped floors, so converting them may cost more "
        "per unit than building new.",
        2,
    ),
    ("What happens to the weekend evening market on the ground floor? Nobody has said.", 3),
]

# Points that share vocabulary with the thread but add something new.
DISTINCT = [
    "The garage is two blocks from the tram stop, but the tram stops running at 9pm, so "
    "residents would still need cars at night.",
    "Converting the garage removes 300 spaces that downtown shops rely on for customers.",
    "The ground floor market could move to the empty lot on Fenwick Road.",
    "Low ceilings in parking structures are about 2.1 meters, below the residential code "
    "minimum of 2.4 meters.",
    "Accessible parking for disabled drivers is already required by state code, so the town "
    "has no choice.",
]


@pytest.fixture
def gate() -> UniquenessGate:
    return UniquenessGate()


@pytest.mark.parametrize(("candidate", "echoes"), ECHOES)
def test_echoes_are_blocked_and_name_the_match(gate, candidate, echoes):
    decision = gate.check(candidate, THREAD)
    assert decision.blocked
    assert decision.matched_id == echoes
    assert decision.score >= decision.threshold


@pytest.mark.parametrize("candidate", DISTINCT)
def test_distinct_points_pass(gate, candidate):
    decision = gate.check(candidate, THREAD)
    assert not decision.blocked
    assert decision.matched_id is None


def test_fixture_margin_is_reported_honestly(gate):
    """The lexical backend separates this fixture set, but not by much. If a change
    to text features narrows the margin further, this test makes it visible."""
    lowest_echo = min(gate.check(c, THREAD).score for c, _ in ECHOES)
    highest_distinct = max(gate.check(c, THREAD).score for c in DISTINCT)
    assert lowest_echo > DEFAULT_THRESHOLD > highest_distinct
    assert lowest_echo - highest_distinct >= 0.02


def test_empty_thread_accepts_anything(gate):
    decision = gate.check("Anything at all.", [])
    assert not decision.blocked
    assert decision.score == 0.0
    assert decision.nearest == ()


def test_nearest_is_reported_even_when_accepted(gate):
    decision = gate.check(DISTINCT[0], THREAD)
    assert not decision.blocked
    assert decision.nearest[0].id == 1
    assert len(decision.nearest) == 3
    scores = [m.score for m in decision.nearest]
    assert scores == sorted(scores, reverse=True)


def test_negation_is_not_discarded():
    sim = TfidfSimilarity()
    a = "Rent control works in small cities."
    b = "Rent control never works in small cities."
    assert sim.score(b, [a])[0] < 1.0


def test_exact_echo_after_normalization_scores_one():
    sim = TfidfSimilarity()
    assert sim.score("  THE Tram is LATE. ", ["the tram is late"]) == [1.0]


def test_threshold_controls_strictness():
    strict = UniquenessGate(threshold=0.2)
    assert strict.check(DISTINCT[0], THREAD).blocked


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.5])
def test_threshold_must_be_in_range(bad):
    with pytest.raises(ValueError):
        UniquenessGate(threshold=bad)


def test_custom_backend_is_used():
    class Always:
        name = "always"

        def score(self, candidate, corpus):
            return [0.99 for _ in corpus]

    decision = UniquenessGate(backend=Always()).check("x", THREAD)
    assert decision.blocked
    assert decision.backend == "always"
    assert decision.matched_id == 1  # ties break on lowest id

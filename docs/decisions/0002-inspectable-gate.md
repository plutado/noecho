# 0002. The uniqueness gate must be inspectable

- Status: accepted
- Date: 2026-10-18

## Context

The uniqueness gate decides which comments are allowed into a thread. Its
threshold, its similarity method, and its mistakes determine which points
exist in the discussion at all. Because No Echo has no ranking and no other
way for a blocked point to appear, a wrong block removes that point entirely.
A filter whose decisions cannot be checked by the people they affect works as
a censor, whatever its intent.

## Decision

Every gate decision that blocks a submission must return, to the submitter:

1. the matched comment (id, body, and timestamp; not its author),
2. the similarity score,
3. the threshold in force, and
4. the name of the similarity backend that produced the score.

The gate never blocks silently, never returns a generic "duplicate" error,
and never hides which comment caused the block. Accepted submissions also
receive the nearest existing comments and their scores.

The same gate is available without posting (`POST /threads/{id}/check`) so a
writer can see the nearest existing point before submitting.

Any future similarity backend, provider, or tenant setting must preserve this
contract. A change that cannot report a specific matched comment (for
example, a classifier that only outputs "duplicate: yes") is not acceptable
as a gate.

## Consequences

- The API returns `409` with the full decision for a blocked comment.
  `tests/test_api.py::test_post_and_block_shows_the_matched_comment` enforces
  it.
- Matched comments are shown to people who may disagree with the match. That
  is the point: they can see the decision and rephrase what is actually new,
  or report the threshold as wrong.
- Showing the score exposes how close a probe came, which helps someone
  rewording to evade the gate. This is accepted. The countermeasures are
  stronger similarity, rate limits, and near-miss detection (see the roadmap),
  not secrecy.
- The matched comment's author is not shown, consistent with buried
  attribution. It remains available through the normal click-through.

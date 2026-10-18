# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
intends to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once it reaches 1.0.

## [Unreleased]

## [0.1.0] - 2026-10-18

### Added

- Engine core with no web or storage dependencies: thread, comment, claim and
  citation records; chronological and reverse ordering.
- Uniqueness gate backed by a local TF-IDF cosine similarity over word
  n-grams and character n-grams. Blocked decisions carry the matched comment
  id and score. Default threshold 0.45, tuned on the fixtures in
  `tests/test_gate.py`.
- Claim typing into five statuses (verified, unverified, refuted, disputed,
  opinion), derived only from attached citations. Citation URLs are
  normalized and a repeated source is rejected.
- Provider interfaces for similarity backends and optional LLM features.
  LLM features are disabled; no provider ships yet.
- SQLite storage using the standard library driver.
- FastAPI application: threads, comments with gate check and draft check,
  click-through attribution, claims and citations.
- Seed script with invented sample threads.
- Tests for the gate, ordering, claim status transitions, providers, the
  seed script and the API. CI runs ruff and pytest via uv.
- README, roadmap, system design, and ADRs 0001 (stack) and 0002
  (inspectable gate).

[Unreleased]: https://github.com/plutado/noecho/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/plutado/noecho/releases/tag/v0.1.0

# Contributing

No Echo is in early development. Issues and pull requests are welcome.

## Setup

```sh
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

CI runs the same commands on every push and pull request.

## Ground rules

- **Keep the core pure.** `src/noecho/core/` must not import from `storage`,
  `api`, or any web or database library. Engine rules are tested there without
  I/O.
- **No popularity signals.** Pull requests that add votes, reaction counts,
  "N people said this", popularity sorting, or vote-based claim resolution
  will be declined. `tests/test_api.py::test_no_popularity_fields_anywhere`
  guards the API schema.
- **The gate stays inspectable.** A blocked submission must always be
  returned with the comment it matched and the score. See
  [ADR 0002](docs/decisions/0002-inspectable-gate.md).
- **Gate changes need fixtures.** If you change text features, the similarity
  backend, or the default threshold, add or update cases in
  `tests/test_gate.py` and say in the PR how the echo/distinct margin moved.
- **Invented data only.** Fixtures and seed data must be clearly made up.
  Use `example.org`, `example.net`, or `*.example` for URLs.
- Record significant design decisions as a new ADR in `docs/decisions/`.
- Add a line to the `Unreleased` section of `CHANGELOG.md`.

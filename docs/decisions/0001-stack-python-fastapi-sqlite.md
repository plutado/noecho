# 0001. Python, FastAPI, and SQLite with a pure engine core

- Status: accepted
- Date: 2026-10-18

## Context

No Echo needs an engine that enforces a uniqueness rule, types claims, and
exposes an API that more than one frontend can use. The hard parts are text
similarity, evaluation, and later embeddings and LLM calls. The project must
be easy for one person to self-host, and must run with no external service
or API key.

## Decision

- **Python 3.12+, managed with uv.** The text-processing, evaluation, and
  embedding ecosystems are strongest in Python. uv gives a single lockfile and
  fast, reproducible installs locally and in CI.
- **FastAPI** for the HTTP layer. Typed request and response models, OpenAPI
  output for free, and an in-process test client.
- **SQLite via the standard library** for storage in 0.1. Zero setup for
  self-hosters and for tests (`:memory:`). Postgres with pgvector is planned
  for when embedding search and multiple tenants are needed (Milestone 3 and 7).
- **A pure engine core.** `src/noecho/core/` contains all rules and imports no
  web or database code. `service.Engine` connects it to a store. The API calls
  only the service.
- **A dependency-free similarity baseline.** TF-IDF cosine over word and
  character n-grams, implemented with the standard library, so the gate works
  offline and deterministically.
- **pytest and ruff** for tests, lint, and formatting.

## Consequences

- Rules can be tested without I/O, and a second store (Postgres) or a second
  interface (a CLI, a batch evaluator) can reuse them unchanged.
- SQLite with one locked connection limits a deployment to one process. That
  is acceptable for early use and is documented. Moving to Postgres means
  writing a second store with the same methods, not changing the core.
- The lexical baseline is weaker than embeddings against paraphrase. Keeping
  it as the default means the system never depends on a network call to
  decide whether a comment posts; embeddings will be added behind the same
  `SimilarityBackend` protocol and evaluated before becoming a default.
- No ORM. SQL lives in one file and is small enough to read directly.

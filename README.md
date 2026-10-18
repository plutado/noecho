# No Echo

**Status: early development.** The engine core, gate, claim rules and a
minimal HTTP API work and are tested. There is no frontend, no auth, and no
LLM provider yet. See [ROADMAP.md](ROADMAP.md).

No Echo is an open-source, self-hostable discussion engine in which a thread
only accepts unique contributions. If a point has already been made, a new
comment making the same point does not post, and the person submitting it is
shown the comment it matched.

## What it does

- **Uniqueness gate.** Every submission is compared with the existing
  comments in its thread. Above a similarity threshold, it is blocked. The
  response includes the matched comment and the score, so the decision can be
  checked by the person it affects. Drafts can be checked before posting.
- **No popularity signals.** No votes, likes, reaction counts, "N people
  said this", or popularity sorting. The API has no field for any of them.
- **Buried attribution.** Comment listings do not include the author. The
  author is available from a separate click-through endpoint.
- **Time order only.** Chronological by default, with a reverse toggle.
- **Claims typed into five buckets.** A claim attached to a comment is
  `verified`, `unverified`, `refuted`, `disputed`, or `opinion`. Status is
  computed from attached citations, never from votes. Citing a source that is
  already attached to the claim is rejected: repeating evidence adds nothing.
- **Optional LLM features, off by default.** Pre-submit coaching and thread
  Q&A (cited synthesis kept separate from labeled gap analysis) are defined as
  a provider interface. The core needs no API key: similarity is computed
  locally.

## Who it is for

People who run a site, publication, community, or research group and want a
discussion space where reading the thread is worth the time, and who are
willing to host it themselves.

## Why

Most comment sections are shaped by their incentives. When agreement is
counted and displayed, repeating a popular point is rewarded, and provocation
is the cheapest way to get a reaction. Moderation works on the output of those
incentives and never catches up.

No Echo removes the incentives instead of policing their results. With no
counters and no visible credit, there is nothing to farm. With a uniqueness
rule, a thread grows only by adding points it does not already contain, so
each distinct position appears once regardless of how many people hold it.
The thread becomes a map of the arguments rather than a tally of the crowd.
This is a hypothesis; the project exists partly to test it.

## Built with

- Python 3.12+, managed with [uv](https://docs.astral.sh/uv/)
- [FastAPI](https://fastapi.tiangolo.com/) for the HTTP API
- SQLite via the standard library (Postgres with pgvector is on the roadmap)
- A dependency-free TF-IDF similarity backend (word and character n-grams)
- pytest and ruff

## Running it

```sh
uv sync                                   # create .venv and install dependencies
cp .env.example .env                      # optional; defaults work without it
uv run noecho-seed                        # load invented sample threads into ./noecho.db
uv run uvicorn noecho.api.app:create_app --factory --reload
```

The server reads settings from environment variables (see `.env.example`); it
does not load `.env` by itself, so export the variables or use your process
manager. Interactive API docs are at <http://127.0.0.1:8000/docs>.

Try the gate against the seeded thread:

```sh
curl -s -X POST localhost:8000/threads/1/check \
  -H 'content-type: application/json' \
  -d '{"body": "The tram stop is two blocks away, so residents could live without a car."}'
```

## Tests and lint

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Layout

```
src/noecho/core/      engine rules: text features, similarity, gate, claims, ordering, providers
src/noecho/storage/   SQLite store
src/noecho/service.py wires core to storage; the API calls only this
src/noecho/api/       FastAPI app and schemas
src/noecho/seed.py    invented sample data
docs/                 system design and architecture decision records
```

## Documentation

- [ROADMAP.md](ROADMAP.md): milestones and estimates
- [docs/system-design.md](docs/system-design.md): architecture, data model,
  API, gate design, risks
- [docs/decisions/](docs/decisions/): architecture decision records
- [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT. See [LICENSE](LICENSE).

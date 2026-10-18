# System design

This describes the engine as built in 0.1.0 and the direction it is meant to
grow. Sections marked *planned* describe roadmap work, not current code.

## Goals and constraints

- A thread accepts a comment only if it is not a repeat of a point already in
  that thread.
- Every blocking decision is inspectable by the person it affects.
- No popularity signal exists anywhere in the data model or API.
- Claim status comes from evidence, never from counting people.
- The core works offline with no API key. LLM features are optional.
- Self-hostable by one person on one machine; able to grow to Postgres and
  multiple tenants without rewriting the core.

## Architecture

```
            HTTP clients (curl, future widget, future first-party site)
                                   |
                         +--------------------+
                         |  api/  (FastAPI)   |   request/response shapes only
                         +--------------------+
                                   |
                         +--------------------+
                         |  service.Engine    |   transactions, invariants
                         +--------------------+
                          /                  \
          +-----------------------+    +------------------------+
          |  core/  (pure)        |    |  storage/  (SQLite)    |
          |  text, similarity,    |    |  SQL, row mapping      |
          |  gate, claims,        |    +------------------------+
          |  ordering, providers  |
          +-----------------------+
                     |
          SimilarityBackend / LLMProvider protocols
          (TfidfSimilarity today; embeddings and LLMs planned)
```

**Engine core (`src/noecho/core/`).** Plain Python with no I/O. It defines
the records, the gate, the claim rules, ordering, and the provider protocols.
It imports nothing from `storage` or `api`, so every rule can be tested
directly and reused by a different web layer or a batch job.

**Storage (`src/noecho/storage/sqlite.py`).** The only module that contains
SQL. One connection per store, guarded by a re-entrant lock;
`transaction()` opens `BEGIN IMMEDIATE` so check-then-insert sequences are
serialized. A Postgres store (planned) will expose the same methods.

**Service (`src/noecho/service.py`).** Holds the invariants that span core
and storage:

1. A comment is inserted only inside the same transaction in which the gate
   saw every earlier comment in the thread. Two concurrent near-identical
   submissions cannot both pass.
2. A claim's stored status always equals `derive_status` over its stored
   citations. Status is never written directly by a client.

**Provider interface (`core/providers.py`).**

- `SimilarityBackend`: `score(candidate, corpus) -> list[float]`, values in
  [0, 1]. `TfidfSimilarity` is the default. An embedding backend (planned)
  implements the same protocol.
- `LLMProvider`: `coach(draft, thread)` and `answer(question, thread)`. The
  default `DisabledLLMProvider` returns no coaching and raises
  `FeatureDisabledError` for Q&A. The app refuses to start if a provider name
  other than `none` is configured, because none ships yet.
- `ThreadAnswer` separates `cited` (synthesis; every statement must list the
  comment ids it rests on) from `gaps` (inference about what has not been
  said; cites nothing). `validate_answer` rejects uncited synthesis and
  citations of comments outside the thread, and is meant to run on every
  provider's output before it reaches a client.

**API (`src/noecho/api/`).** Translates HTTP to engine calls. Response models
are written by hand so that a field cannot leak by accident: comment
listings do not include `author`.

## Data model

```
threads    id, title, source_url, created_at
comments   id, thread_id -> threads, author, body, created_at
claims     id, comment_id -> comments, text, kind, status, created_at
           kind   in (factual, opinion)
           status in (verified, unverified, refuted, disputed, opinion)
citations  id, claim_id -> claims, url, normalized_url, stance, note, created_at
           stance in (supports, refutes)
           UNIQUE (claim_id, normalized_url)
```

There is no column for votes, reactions, view counts, or rank, and there will
not be. Timestamps are ISO 8601 UTC strings. Ordering uses
`(created_at, id)` so equal timestamps are stable.

`author` is a free-text handle until auth exists (Milestone 6). It is stored
so attribution can be shown on click-through; it is not used by any engine
rule.

*Planned:* `tenant_id` on every table (Milestone 7), an `embedding` column on
comments (Milestone 3), a claim status history table and citation withdrawal
(Milestone 5).

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness, active similarity backend, LLM provider |
| POST | `/threads` | Create a thread (`title`, optional `source_url`) |
| GET | `/threads` | List threads, oldest first |
| GET | `/threads/{id}` | One thread |
| GET | `/threads/{id}/comments?order=chronological\|reverse` | Comments without authors |
| POST | `/threads/{id}/check` | Run the gate on a draft; nothing is stored |
| POST | `/threads/{id}/comments` | Submit. `201` with the comment and gate result, or `409` with the gate result and the matched comment |
| GET | `/comments/{id}` | One comment, without author |
| GET | `/comments/{id}/attribution` | The author, on explicit request |
| POST | `/comments/{id}/claims` | Attach a claim (`text`, `kind`) |
| GET | `/comments/{id}/claims` | Claims with citations |
| GET | `/claims/{id}` | One claim with citations |
| POST | `/claims/{id}/citations` | Attach a citation (`url`, `stance`, `note`). `409` if the source is already attached; `422` for opinion claims or bad URLs |

A blocked submission returns:

```json
{
  "blocked": true,
  "score": 0.7129,
  "threshold": 0.45,
  "backend": "tfidf-local",
  "nearest": [{"comment_id": 1, "score": 0.7129}, {"comment_id": 4, "score": 0.0079}],
  "matched": {"id": 1, "thread_id": 1, "body": "...", "created_at": "..."}
}
```

## The uniqueness gate

### Scoring

`TfidfSimilarity` builds two sparse vectors per text:

- **Word features:** normalized (NFKC, casefolded, curly quotes and dashes
  unified, "n't" expanded to "not"), a short stopword list removed, a light
  suffix stripper applied, then unigrams and bigrams.
- **Character features:** 3- to 5-grams inside space-padded words, which
  absorb typos, inflection, and small spelling changes.

Negations and limiters (`not`, `no`, `never`, `only`, `without`, ...) are
deliberately not stopwords: "X works" and "X never works" are different
points.

IDF is computed over the thread plus the candidate, with sublinear term
frequency and L2 normalization. Using the thread as the corpus means words
every comment shares (usually the topic) weigh less than words specific to
one point. The final score is `0.5 * word_cosine + 0.5 * char_cosine`. If the
candidate's content tokens equal an existing comment's in order, the score is
1.0.

The gate blocks when the best score is `>= threshold`, and always returns the
three nearest comments with scores, whether or not it blocks.

Cost is linear in thread length per submission. That is fine for threads of
hundreds of comments; the pgvector index in Milestone 3 replaces the scan.

### Threshold tuning

The default threshold is **0.45**. It was chosen against the fixture set in
`tests/test_gate.py`: five echoes (exact, punctuation, paraphrase,
reordered paraphrase, question form) and five distinct points that share
vocabulary with the thread. On that set the lowest echo scores about 0.47 and
the highest distinct point about 0.43.

That margin is narrow, and it is the honest state of a lexical method. The
closest distinct case is a comment that restates an existing point and adds
a new consequence ("the tram stop is two blocks away, *but the tram stops at
9pm*"). Lexical similarity sees mostly the restatement. A fixture this small
cannot justify the value beyond "it separates these cases"; the evaluation
harness (Milestone 1) is the prerequisite for changing it with confidence.
`test_fixture_margin_is_reported_honestly` fails if a change pushes either
side across the threshold or shrinks the margin below 0.02, so regressions
are visible.

`noecho-eval` (see the README) now measures the gate against labeled pairs.
On the 46-pair starter corpus in `evals/pairs.jsonl`, 0.45 gives precision
0.875 and recall 0.636. Five of the six honest-convergence duplicates are
missed (they share few words with the original), and two "same fact, new
implication" points score within 0.01 of the threshold. The corpus is too
small to justify moving the threshold; the 300-pair corpus is still to do.

Tuning principles:

- **Prefer false accepts to false blocks.** A missed echo costs readers a few
  seconds. A wrongly blocked distinct point is suppressed speech, and in a
  system with no other ranking it removes the point entirely.
- **Measure against labeled pairs, per topic.** Thresholds drift with
  comment length and topic vocabulary.
- **Report score distributions, not just a single F1.** The overlap region is
  where the editorial decisions are being made.
- **Log every decision** (planned): score, threshold, backend, matched id.
  This makes threshold audits possible after the fact.

### Composition-time check

`POST /threads/{id}/check` runs the same gate without storing anything, so a
composer can show the nearest existing comment before the user submits.
Pre-submit LLM coaching (planned) adds phrasing on top of this; it does not
replace the deterministic gate.

## Claims and verification

Claims are attached to a comment by its author (manually for now; parsing is
Milestone 4). `kind` is `factual` or `opinion`.

Status is a pure function of kind and citations (`core/claims.py`):

| Kind | Evidence | Status |
| --- | --- | --- |
| opinion | any (citations are rejected) | `opinion` |
| factual | none qualifying | `unverified` |
| factual | supports only | `verified` |
| factual | refutes only | `refuted` |
| factual | both sides | `disputed` |

"Qualifying" means at least `min_sources` distinct source domains on that
side (default 1, set by `NOECHO_MIN_SOURCES`). Two pages on one domain count
once. Disputed claims stay disputed; adding more supporting sources does not
outweigh the other side, because that would be a vote by another name.

Citations are normalized before comparison: scheme folded to https, host
lowercased, `www.` and default ports dropped, fragment and trailing slash
removed, tracking parameters (`utm_*`, `fbclid`, `gclid`, ...) dropped, query
sorted. A citation whose normalized URL is already on the claim, on either
side, is rejected with `409 duplicate_citation`. The same source may back a
different claim.

Only `http` and `https` URLs are accepted. Nothing fetches the URL yet; link
checking is Milestone 5.

## Risks

**The threshold is editorial power.** Whoever sets it decides which points
count as new. Mitigations: the gate is never silent (the blocked person sees
what they matched and the score, see ADR 0002); the threshold and backend are
returned in every decision; per-tenant thresholds (Milestone 7) will be
bounded to a range so the gate cannot be configured into a censor; decisions
will be logged for audit.

**Rewording probes.** Someone can reword a blocked point until it passes.
Lexical similarity is weak against synonym substitution and restructuring.
Mitigations, in order: embedding similarity (Milestone 3), an adversarial
evaluation suite that measures evasion rate per attack (Milestone 2), and
near-miss detection with rate limits so repeated probing from one account is
visible and slowed. A probe that succeeds produces a comment that reads as
different, which limits its value to the prober; the goal is to make it
costly, not impossible.

**Honest convergence.** Two people independently reaching the same point is
not an echo in intent, but the engine treats it as one. The second person is
shown the first comment, which is the intended behaviour: the point is
already in the thread. The cost falls on people who arrive late, which is why
the gate errs toward accepting.

**Restatement plus extension.** A comment that repeats a point and then adds
a new one is the hardest case (see Threshold tuning). The blocked-response
design lets the composer prompt "this part is covered; what is new?", and the
evaluation corpus must include many such cases.

**Uniqueness is not civility.** The gate enforces novelty, not courtesy. A
novel insult passes. Hosts still need basic conduct rules and a removal path,
which is out of scope for the engine core.

**Bogus citations.** A citation can point to a page that does not support the
claim. `min_sources` raises the cost; the verifier-trust decision in
Milestone 5 addresses it properly.

**Smaller participation.** Removing validation loops will likely reduce how
many people post. That is accepted.

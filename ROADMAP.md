# Roadmap

Estimates are rough working hours for one developer, including tests and
docs. They will be revised as milestones land. Order reflects dependency, not
priority: the evaluation harness comes early because every later change to
the gate needs it.

Total estimate: **about 112 hours** across milestones 1 to 10.

## Milestone 0: Foundation (done)

- [x] Pure engine core: records, ordering, claim status rules
- [x] Local TF-IDF uniqueness gate returning matched comment and score
- [x] Citation normalization and duplicate-source rejection
- [x] SQLite store and engine service
- [x] FastAPI app: threads, comments, draft check, attribution, claims, citations
- [x] Seed script with invented data
- [x] Tests, ruff, CI
- [x] README, system design, ADRs 0001 and 0002

## Milestone 1: Dedup evaluation harness (~12 h)

The threshold is the most consequential setting in the system. It needs
measurement before it is changed again.

- [ ] Labeled pair format (JSONL: thread context, candidate, label, note) and loader (2 h)
- [ ] Invented corpus of at least 300 labeled pairs across three or more topics,
      including honest convergence and "same fact, new implication" cases (4 h)
- [ ] `noecho-eval` command: precision, recall, F1, and the score
      distributions for each label at a given threshold (3 h)
- [ ] Threshold sweep report (table and ASCII histogram) written to stdout (2 h)
- [ ] CI job that fails if F1 on the corpus drops by more than a set margin (1 h)

## Milestone 2: Adversarial rewording probes (~8 h)

- [ ] Generators for rewording attacks: synonym substitution, clause
      reordering, padding with filler, character noise, translation round trip
      (behind an optional extra) (4 h)
- [ ] Report the evasion rate per attack at the current threshold (2 h)
- [ ] Per-thread submission rate limit and repeated-near-miss detection
      (several blocked attempts in a row from one account) (2 h)

## Milestone 3: Embedding provider and pgvector (~16 h)

- [ ] `EmbeddingSimilarity` backend implementing `SimilarityBackend`, with a
      provider interface for hosted or local embedding models (3 h)
- [ ] Hybrid scorer combining lexical and embedding scores, evaluated with the
      Milestone 1 harness before it becomes the default (3 h)
- [ ] Postgres store with the same interface as `SQLiteStore`; migrations (4 h)
- [ ] pgvector column and index for comment embeddings; nearest-neighbour
      query replaces the full-thread scan (3 h)
- [ ] Background indexing so posting does not wait on an embedding call when
      a cached vector exists; consistency rules for the gate (3 h)

## Milestone 4: Claim parsing (~10 h)

- [ ] `ClaimParser` interface: comment text to atomic claims with a proposed
      kind (2 h)
- [ ] Rule-based fallback parser (sentence split plus opinion markers) so the
      feature works without an LLM (3 h)
- [ ] LLM-backed parser behind the provider interface; the author confirms or
      edits proposed claims before they are stored (3 h)
- [ ] Composer hint when a factual claim has no source: "link a source or it
      posts as unverified" (2 h)

## Milestone 5: Verification workflow (~12 h)

- [ ] Decide the verifier-trust rule (independent multi-source corroboration
      vs. earned trust tier); record as an ADR (2 h)
- [ ] Withdraw a citation (by its submitter) with status recomputation and an
      audit log entry (3 h)
- [ ] Dead-link and redirect checks on citations, run in the background (3 h)
- [ ] Verification queue endpoint: unverified and disputed claims for a
      thread, oldest first (2 h)
- [ ] Status history per claim, so readers can see how a status was reached (2 h)

## Milestone 6: Auth and accounts (~12 h)

- [ ] Email magic-link sign-in (5 h)
- [ ] Pseudonymous display handles; real identity never in the stream (2 h)
- [ ] Delegated identity for embedding sites: signed host tokens so a host's
      users can post without a separate account (4 h)
- [ ] Ownership checks on citation withdrawal and claim edits (1 h)

## Milestone 7: Multi-tenant isolation (~10 h)

- [ ] Tenant id on every record; all store queries scoped by tenant (3 h)
- [ ] Gate and future embedding index never compare across tenants, with a
      test that tries to (2 h)
- [ ] Per-tenant API keys and rate limits (3 h)
- [ ] Per-tenant settings with a fixed allow-list (threshold within a bounded
      range, Q&A on or off); no setting can enable popularity features (2 h)

## Milestone 8: Embeddable widget (~16 h)

- [ ] Framework-free script that renders a thread into a host page (5 h)
- [ ] Composer with live draft check showing the nearest existing comment as
      the user types (debounced) (4 h)
- [ ] Blocked-submission view: the matched comment, the score, and a prompt to
      add what is new (2 h)
- [ ] Claim badges with source links; click-through attribution (3 h)
- [ ] Accessibility pass and a demo page with invented content (2 h)

## Milestone 9: Thread Q&A (~12 h)

- [ ] First `LLMProvider` implementation, configured by environment, off by
      default (3 h)
- [ ] "What has been said" synthesis: retrieval over the thread, every
      sentence cites comment ids, enforced by `validate_answer` (4 h)
- [ ] "What has not been said" gap analysis, returned in a separate field and
      labeled as inference (2 h)
- [ ] Cost and latency controls: caching per thread version, token budget (3 h)

## Milestone 10: Operations (~4 h)

- [ ] Dockerfile and compose file (SQLite and Postgres variants) (2 h)
- [ ] Structured logging and a gate decision log for threshold audits (2 h)

## Not planned

These are excluded by design and will not be added: votes, reactions,
popularity or "hot" sorting, counts of how many people made a point, karma or
status badges, and vote-based resolution of disputed claims.

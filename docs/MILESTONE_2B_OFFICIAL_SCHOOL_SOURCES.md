# Milestone 2B — 2026 Official School Source Verification

**Checkpoint:** 2026-10-24 (America/New_York)  
**Status:** DISCOVERY INFRASTRUCTURE VERIFIED; DOCUMENT-LEVEL SOURCE-TYPE VERIFICATION OPEN  
**Scope:** Nationwide official source discovery and verification for 2026 FBS personnel information. This **Milestone 2B** is distinct from the older *v0.4 Step 2B* optional private AWS-archive discussion in the README. **No AWS or paid service is required for this milestone.**

## Source of truth and safety rules

- Source directory: `data/archive/2026_team_aliases.csv` (138 teams, including North Dakota State and Sacramento State), plus `config/official_athletics_sites_2026.json`.
- The school-source audit does **not** establish starting QB1, injuries, player replacements, or historical player availability. Missing sources/statuses remain `UNKNOWN` or `NOT_YET_VERIFIED`, never healthy/unavailable by inference.
- Candidate URL, reachable page, or filename is not a document-level verification or confirmed game-specific player claim.
- Before any person/game evidence can influence predictions or walk-forward evaluation, require verified team, 2026 football season, precise game/opponent, source provenance, publication and observation times before decision/kickoff, and audit trail. Never backfill modern knowledge into a prior decision.
- The research model remains `PASS_UNVALIDATED`. Do not represent subjective choices as model-produced picks; do not promote betting readiness based on successful CI alone.

## Implemented and verified through October 24, 2026

| Area | Evidence / state |
| --- | --- |
| 138-school inventory and reviewed candidate athletics domains | Implemented in `config/official_athletics_sites_2026.json`, `scripts/official_school_source_registry.py` |
| Public site/RSS reachability | `scripts/official_source_connectivity.py` probes 138 school athletics homepages and 8 reviewed official RSS feeds. RSS is optional, not a 138-feed target. |
| Official school page discovery | `scripts/official_personnel_source_discovery.py` crawls athletics homepage, football page and bounded secondary pages; verifies school-domain links, preserves failed probes, records candidate game notes/depth charts/injury sources, does not promote player evidence |
| Explicit per-school unresolved source types | `scripts/official_personnel_source_coverage.py` exports JSON/CSV and review backlog; distinguishes `NO_CANDIDATE_LOCATED` from `NOT_PUBLISHED` |
| Latest successful source audit | [Run 40066306748](https://github.com/The-Caves/cfb-model/actions/runs/40066306748), at [main commit 438505947cb3f9d4f7d1cd50d08c8cecb823b7e2](https://github.com/The-Caves/cfb-model/commit/438505947cb3f9d4f7d1cd50d08c8cecb823b7e2): 138/138 football pages audited; game-note link candidates for 80 schools, separate depth-chart candidates for 12, school-site injury-report candidates for 1. **Those are candidate-link counts, not verified documents or players.** |
| Same-commit Data Intake | [Run 40066306686](https://github.com/The-Caves/cfb-model/actions/runs/40066306686): both validate and ingest jobs succeeded |
| Same-commit scheduled context refresh | [Run 40087648886](https://github.com/The-Caves/cfb-model/actions/runs/40087648886): refresh job succeeded. Successful run does not imply complete QB/injury coverage. |

Previous failed runs 40065228822, 40065228838, 40065238026, and 40065238074 came from an incorrect fallback-URL test fixture and were followed by successful runs. Do not count historic failed runs as current failing HEAD without checking the latest run.

The dedicated workflow is `.github/workflows/cfb-school-source-audit.yml`; its acceptance guard checks all 138 football pages were audited **and** that unreviewed player evidence has not been promoted.

## Outstanding work — 2B is not yet closed

1. **Verify real documents:** fetch candidate game-note PDFs/HTML and separate depth charts; confirm authorship, football relevance, season, opponent/game, source URL, publication timestamp and the existence of any *embedded* depth chart. Reject or quarantine stale, generic or mismatched documents.
2. **Expand gaps:** for each canonical school and each source type, record `VERIFIED_DOCUMENT`, `CANDIDATE_REVIEW_REQUIRED`, `SEARCH_INCOMPLETE`, or defensible `NOT_PUBLISHED_OR_NOT_AVAILABLE` with dated audit details. No discovered link must **not** be treated as no published document.
3. **Official conference availability mapping:** map verified SEC, Big Ten, ACC and Big 12 reporting publishers via `scripts/official_availability.py` to canonical eligible schools and games. Check publication/collection timestamps and freshness. Official `AVAILABLE`, `OUT`, etc. are *availability reports*, not inferred diagnoses, player participation or starting-QB statements.
4. **Keep source types separate from player assertions:** verified game notes or a verified depth chart are only evidence of document availability. Promote `CONFIRMED_REVIEWED_PREKICKOFF` QB1 or player status exclusively through the independently reviewed game-specific evidence gate.
5. **Test and verify end-to-end:** add fixture/acceptance coverage for misleading candidate links, outdated notes, embedded depth charts, ambiguous conference matches, missing time metadata, and pre-kickoff as-of rules. Run unit tests and inspect actual latest-head GitHub workflow outputs/artifacts.

**Exit condition:** An auditable 138-school, per-source-type inventory of verified official 2026 documents or explicitly justified status, with provenance and timestamp evidence; conference-report school coverage mapped; safety gates passing. **Not** merely 138 reachable football pages, **not** 138 RSS feeds, and **not** automatic nationwide QB1 confirmations.

## Roadmap following this milestone

- **Milestone 1:** QB-confirmation acceptance infrastructure existed before 2B; verify its current acceptance report rather than assuming every game-specific QB was confirmed. `scripts/qb_milestone_acceptance.py` explicitly distinguishes infrastructure checks from verified-starter coverage.
- **2C:** verified game-specific starting QB1 records.
- **2D:** reviewed game-specific player availability.
- **2E:** statistically tested player replacement value (no unvalidated manual point penalties).
- **2F:** strict, timestamp-safe prospective / walk-forward SU, ATS and O/U evaluation, including market provenance and ablations.

## Documentation maintenance convention

Update **this file** alongside each material 2B code change, acceptance result or verified source-coverage change. Record:
- UTC timestamp, affected scripts/config/tests;
- precise numerator/denominator by team/source type and explicit `UNKNOWN`/missingness;
- commit SHA, GitHub Actions run URLs, pass/fail and relevant artifact names;
- discovered blockers, verified resolutions, remaining work, and whether research-model status changed.

Keep broader status aligned with `README.md`, `docs/CONTEXT_DELTA.md`, and applicable `docs/V04_*.md` documents. Never replace observed results with fixture-only claims. Preserve historical checkpoints; append dated updates instead of silently rewriting past evidence.

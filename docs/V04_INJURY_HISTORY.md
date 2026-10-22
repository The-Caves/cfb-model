# v0.4 Step 3B — Timestamped 2026 player availability history

**Scope:** 2026 research-only reported availability observations, **not medical diagnoses, participation confirmations, replacement-point penalties, or bets**. Status remains `PASS_UNVALIDATED`.

## Evidence, timestamps and defaults

`scripts/availability_context.py` consumes publicly sourced, reviewed / structured-official conference player designations. The per-game builder in `scripts/game_context.py` now preserves `injury_coverage_by_team` using the upstream `coverage_by_team` result. The existing `injury_reports` / `availability_reports` arrays contain the same upstream designation data, **not two independent reports**.

`python -m scripts.injury_history --context data/context_refresh/upcoming_game_context_2026.json --output data/context_refresh/injury_history.json` creates one game/team slot for each pre-kickoff matchup. Slots include ESPN game ID, team/opponent, kickoff UTC, report coverage, observation UTC, accepted individual source-backed reported statuses, quarantined evidence reason codes, and explicit `UNKNOWN` for every unlisted player. `published_at_utc` and `captured_at_utc` remain on each accepted player designation. The parent snapshot retains original context `asof_utc` and `captured_at_utc`. The required ordering is **published <= captured <= context-asof <= context-capture <= observed < kickoff**. Invalid, contradictory or late evidence cannot silently produce a usable status.

`lookup(snapshots, game_id, team, decision_utc, player=None)` validates the snapshots and reconstructs only the latest observation at or before the decision, never at/after kickoff. A player missing from the latest snapshot stays UNKNOWN; an explicitly reported OUT followed by a later newly published AVAILABLE can only be described as **a reported designation change**, not recovery or proof that the person played. Same-publication contradictory reported designations are quarantined, including across observations. No prior game starter or player health can be inferred.

**Limits:** Player identity is currently source-reported name text, not a globally verified 2026 roster ID; ambiguous name collisions are a limitation. Public official availability currently has incomplete nationwide FBS coverage. Captures made in October do not validate historical September source-time assertions. Stored Git history is not independently immutable or third-party time-attested.

## Persistence / verification

The existing free `CFB Pregame Context Delta` GitHub Actions pipeline produces `injury_history.json`, validates it via `scripts.context_archive`, and saves:
- `context-state/state/injury_history_latest.json`
- `context-state/injury_history/YYYY/MM/DD/YYYYMMDDTHHMMSSZ.json.gz`
- `context-state/state/summary.json` -> `injury_history` counts

`tests/test_injury_history.py` covers missing team and player reports; future/leaked, late and post-kickoff sources; conflicting publications; same-publication contradictions across snapshots; OUT to AVAILABLE as a *reported transition only*; loss of coverage; after-kickoff lookup; duplicate/invalid/mutated snapshot integrity; and exclusive creation. The complete test suite must pass in GitHub Actions. The Context Delta workflow must also finish its ingestion and archive steps and have the stored latest record read back before declaring Step 3B verified.

**Next:** v0.4 Step 3C. Join point-in-time QB/injury observations to dated profiles with provenance and missingness flags, then run leakage-safe walk-forward ablation tests. Do not invent QB starter IDs or hand-tuned injury points.

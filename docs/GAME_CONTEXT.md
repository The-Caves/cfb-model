# Step 4 — Pregame game context and personnel source integrity

This is a context collection layer, NOT a trained betting model.

Automated with each scheduled intake:
- Read timestamped, completed ESPN scoreboard events and infer school home-base city only from two or more consistent non-neutral home fixtures.
- Collect next 10 days of upcoming ESPN fixtures and preserve retrieval time.
- Calculate days since last observed completed kickoff; unavailable prior fixtures remain missing.
- Use Open-Meteo geocoding with exact city and state, and compute great-circle CITY CENTROID separation. This is an approximate geographic proxy, NOT miles actually traveled.
- Fetch hourly Open-Meteo live forecasts for upcoming outdoor fixtures; record temperature, wind, gusts, precipitation probability, retrieval time and missing-weather status. Indoor games do not receive outdoor weather claims.
- Optionally load manually verified injury and QB starter reports from data/manual/availability_2026.csv, requiring game ID, school, kickoff, publication and capture timestamps, HTTPS source and reviewer identity.
- In the absence of current, reviewed full-team injury-report attestations, coverage stays UNKNOWN and no presumed-healthy claims or replacement-value adjustments are made.

Outputs: data/context/upcoming_game_context_2026.json, data/context/upcoming_game_context_2026.csv, data/context/context_manifest.json, and date-stamped raw upcoming-scoreboard payloads. Each is stored as a GitHub Actions artifact.

The CSV schema is initially empty. No national source for consistent 2026 injury and QB-starting information has been integrated yet. SEC availability reports are published at https://www.secsports.com/fbreports but automated source parsing and full coverage are still pending.

Historical backtest safety: Retrospectively collected schedules, weather observations, or injury news cannot establish what was available before a past kickoff. Current Open-Meteo forecasts apply to future fixtures only; they are not historical weather backfills. No changes to prediction weights are implied by data availability alone.

All output remains PASS_UNVALIDATED and safe_for_betting=false.

Run: python scripts/ingest_game_context.py --raw-dir data/raw --availability-csv data/manual/availability_2026.csv --output data/context --horizon-days 10

Sources: https://open-meteo.com/en/docs/geocoding-api ; https://open-meteo.com/en/docs .

## First live run — October 21, 2026

GitHub Actions run: https://github.com/The-Caves/cfb-model/actions/runs/39547645209
(Commit `2fd099b`; date and forecast availability change on each scheduled run.)

- 11/11 upcoming schedule dates fetched with no ESPN schedule errors
- **109 upcoming game records** generated
- Both teams' recent rest intervals: 109 games
- Exact geocoded venue locations: 54 games
- Weather forecast available: 38 games; four indoor games need no outdoor forecast
- Both teams' geographic travel proxy available: 34 games
- Verified player availability/starting quarterback coverage: **0 games** (CSV schema empty)
- Geocoding requests: 76; forecast requests: 33
- Geocoder SSL timeouts: 12 logged; provider time budget skipped 76 additional location/forecast lookups
- Status: `CONTEXT_RESEARCH_PARTIAL_COVERAGE`; safe_for_betting: false

These are explicitly **partial** coverage results. The collector is operating, but neither weather nor travel coverage nor verified national personnel status is complete. Next engineering priorities: reliable venue coordinates / geocoding cache and a timestamped official injury-QB source process. Do not enable personnel or weather-based predictive adjustments until their reliability and walk-forward value are validated.

## Automated official SEC and Big Ten player-level availability (added October 21, 2026)

The collector now calls the same **public structured availability publisher** embedded on the official conference pages:
- SEC: https://www.secsports.com/fbreports
- Big Ten: https://bigten.org/sports/2026/9/10/FB_Availability_Reports.aspx

It ingests `/api/get-publish-public` for each conference, but **not historical archived reports as if they had been known pregame**. For every publisher card, it requires: a report with non-pending publication status, non-future publication timestamp in the reported conference timezone, the exact two publisher teams matched through the 138-team school alias map to **one** ESPN game on the same local date, kickoff still in the future, both teams' player rows successfully parsed, and publication/capture timestamps before the context cutoff. A partially parsed, stale, ambiguous, or unsupported card is quarantined and explicitly identified in `official_availability_manifest.json`.

When accepted, the source produces both team-level report attestations and individual `INJURY` designations with position when the official display row includes it. These are fed through the preexisting `availability_context.evaluate` and persist in timestamped context snapshots/deltas. Source capture is performed **before** the context issue cutoff; a later missing report never means a player recovered. Reports can cover only games in the conferences' official reporting programs, not all FBS teams. The current conference feed was tested while all upcoming cards displayed **Report Pending**, so no player-level claims were fabricated.

**Starting QB limitation:** A QB listed `OUT` or `QUESTIONABLE` is a sourced availability signal, **not** a sourced confirmation of who starts. This feed never emits `QB_STARTER` records and no backup or replacement-value score adjustment is inferred. Confirmed game-day starting QB reports still require a separate verified official source or manually reviewed and timestamped assertion. This is automated published **availability**, not automatic starting-lineup verification. No bets are enabled (`PASS_UNVALIDATED`).

## Exact-game starting quarterback review gate (October 21, 2026)

Official team news and directly attributed coach statements sometimes explicitly name the starter for a specific game; rankings on a depth chart, season-opener plans, retrospective box scores, speculative reports and official QB availability do **not** independently confirm a starter for the next fixture. Game-specific starter evidence must be reviewed and dated. NCAA teams do not have a validated nationwide programmatic pregame starter-confirmation provider in this repo.

`data/manual/qb_starter_evidence_2026.csv` (initially header-only) provides a **separate** claim path. A record needs the ESPN game ID, exact reporting team/opponent and kickoff, player, HTTPS published source, `source_type` of `OFFICIAL_TEAM_RELEASE` or `ON_RECORD_COACH_CONFIRMATION`, `evidence_scope=EXPLICIT_THIS_GAME`, a short start assertion naming the player, `review_status=APPROVED`, reviewer label, source-published/captured/review timestamps and an as-of cutoff preceding kickoff. Evidence more than 14 days before kickoff, missing/mismatched game identity, or different player statements about the same game/team are quarantined. These are **workflow rules**, not automated proof of the source site's authenticity or truth.

`scripts/qb_starter_review.py` validates and transforms approved rows into `QB_STARTER` claims. `scripts/availability_context.py` independently applies the review fields and blocks claimed starters contradicted by accepted `OUT`, `DOUBTFUL`, `LIMITED` or `SUSPENDED` QB availability. The source counts and rejection codes appear under `qb_starter_evidence` in the context manifest. No real evidence is seeded by default and no injuries or QB replacement-value adjustments are inferred. **National automated source discovery, substantive source authentication, and validated point effects remain unfinished.**

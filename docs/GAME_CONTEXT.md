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

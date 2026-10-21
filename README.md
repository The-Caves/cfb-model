# 2026 College Football Prediction Model — Development

**Status:** experimental research; no validated betting recommendations. All unvalidated predictions are explicitly `PASS_UNVALIDATED`.

## Deployed and tested
- ESPN 2026 completed-game scoreboard intake with dated raw snapshots and QA manifest.
- Timestamp-cutoff 2026 score-based team profiles, per-team record, scoring, last three games and opponents.
- Experimental ridge score projection engine; no verified sportsbook integration.
- CI on pushes and pull requests. Scheduled 3-times-daily ingestion plus manual dispatch.
- Each intake run publishes `data/games_2026.csv`, `data/team_profiles_2026.csv`, source JSON and diagnostics as a 30-day GitHub Actions artifact.

## Commands
```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/ingest_espn.py --start 2026-08-01 --output data
python scripts/build_profiles.py --games data/games_2026.csv --output data
```

## Limitations and next steps
- Score data alone cannot prove opponent-adjusted EPA, quarterback response to pressure, special teams or injury availability. Those fields are explicitly empty.
- 2025 historical training seasons and complete v0.9 archived research modules are not deployed in this repository yet.
- The v0.9 local archive contains retrospective 2026 score data for 388 games and 138 score-derived profiles but flags incomplete independent score verification, ESPN/sportsdataverse downloads and lack of prospective odds/injury coverage.
- A game ledger fetched today is not evidence that *pregame* lines or injury status were historically observable. Walk-forward backtests must strictly cut off at each historical kickoff.
- Pending: archived prior seasons with provenance, advanced 2026 play-by-play EPA, drive statistics, injury verification, weather/rest/travel, timestamped sportsbook odds and out-of-sample calibrated evaluations.

Workflow: [CFB Data Intake](https://github.com/The-Caves/cfb-model/actions/workflows/cfb-data-intake.yml)

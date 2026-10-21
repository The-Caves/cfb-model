# 2026 College Football Prediction Model — Development

**Status:** experimental research; no validated betting recommendations. All unvalidated predictions are explicitly `PASS_UNVALIDATED`.

## Deployed and tested
- ESPN 2026 completed-game scoreboard intake with dated raw snapshots and QA manifest.
- Timestamp-cutoff 2026 score-based team profiles for the 138-school registry, per-team record, scoring, last three games and opponents; FCS opponents still count toward their FBS opponent's games.
- Experimental ridge score projection engine; no verified sportsbook integration.
- Frozen 2026 archive and **Eastern Time-corrected** ESPN snapshot reconciliation. Archive conflicts are quarantined (see `docs/RECONCILIATION_2026.md`).
- CI on pushes and pull requests. Scheduled 3-times-daily ingestion plus manual dispatch.
- Each intake run publishes `data/games_2026.csv`, `data/team_profiles_2026.csv`, source JSON and diagnostics as a 30-day GitHub Actions artifact.

## Commands
```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/ingest_espn.py --start 2026-08-01 --output data
python scripts/build_profiles.py --games data/games_2026.csv --output data --registry data/archive/2026_team_aliases.csv
python scripts/reconcile_scores.py --archive data/archive/2026_v09_scores_unverified.csv --live data/games_2026.csv --aliases data/archive/2026_team_aliases.csv
```

## Limitations and next steps
- Score data alone cannot prove opponent-adjusted EPA, quarterback response to pressure, special teams or injury availability. Those fields are explicitly empty.
- The archived **2026 score ledger** is now committed with explicit team-name mapping and audit automation. The complete v0.9 research code and prior-season historical training sets are **not yet deployed**.
- The v0.9 local archive contains retrospective 2026 score data for 388 games and 138 score-derived profiles but flags incomplete independent score verification, ESPN/sportsdataverse downloads and lack of prospective odds/injury coverage.
- A game ledger fetched today is not evidence that *pregame* lines or injury status were historically observable. Walk-forward backtests must strictly cut off at each historical kickoff.
- Pending: archived prior seasons with provenance, advanced 2026 play-by-play EPA, drive statistics, injury verification, weather/rest/travel, timestamped sportsbook odds and out-of-sample calibrated evaluations.

Workflow: [CFB Data Intake](https://github.com/The-Caves/cfb-model/actions/workflows/cfb-data-intake.yml)

## Advanced statistics integration (Step 3)
- 2026 SportsDataverse play-by-play ingestion, game-ID and final-score checks, research-only EPA/success/explosive rates and defensive splits are available in `scripts/ingest_advanced.py`.
- Advanced drive release is reconciled by ESPN game ID and exact team ID/name; actual 2026 files contain team names despite numeric-ID documentation. Both sides must pass; verified games contribute drives, yards/drive, and plays/drive. Points/drive remains unavailable.
- Source timestamps and SHA256 are reported in the advanced manifest. Source snapshots retrieved now are not retrospective proof of historical pregame availability.
- Advanced ingestion runs as an optional, clearly reported research stage; score ingestion continues if the advanced source is missing or inconsistent. The first live advanced run is pending verification.

### Unified 2026 research feature store

On each full intake, `scripts/combine_profiles.py` builds `data/enriched/team_profiles_2026_enriched.csv` with score-derived plus provider-observed EPA, rushing/passing, success and drive metrics, and an as-of cutoff. Team, season and as-of joins are strict. It remains `PASS_UNVALIDATED` and is not yet wired to a betting-prediction model.

## Step 4: Upcoming-game context and personnel gating
- Live ESPN future fixtures and kickoff-aware rest are extracted from completed-game and upcoming scoreboard snapshots.
- Approximate straight-line travel uses **city-centroid** geocoding and schools with at least two verified home venue observations. Uncertain venues remain missing, not inferred.
- Open-Meteo future forecast (temperature, wind, gusts, precipitation probability) retains capture times. No historical backfill is misrepresented as pregame weather.
- Optional reviewed, timestamped QB starter and injury reports are ingested with strict pregame cutoffs. The initial report CSV has **no records**; injury and QB-start statuses are UNKNOWN until genuine verified sources are added.
- Context is published with the other workflow artifacts: data/context/upcoming_game_context_2026.csv, .json, and context_manifest.json.
- See docs/GAME_CONTEXT.md for limitations. No adjustments to projection weights or betting selections are activated by Step 4.

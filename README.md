# CFB Model (2026)

## Deployment
Experimental score-only CFB model and scheduled ingestion, maintained through GitHub commits.

- **Continuous integration:** tests run on pushes and pull requests.
- **Data collection:** ESPN public scoreboard fetch runs on manual dispatch and three times daily (10:17, 16:17, 23:17 UTC).
- **Audit trail:** raw dated ESPN responses, completed game CSV and manifest are uploaded as 30-day GitHub Actions artifacts.
- **No secrets required** for public ESPN scoreboard endpoint.
- **Data completeness is not guaranteed:** the provider may omit games or change schemas; ingest fails visibly if downloads error or produce zero completed games.
- **Betting predictions are disabled:** score-only baseline has not been validated with prospective market odds, comprehensive QB/injury data, opponent-adjusted play-by-play EPA or walk-forward testing. Outputs carry PASS_UNVALIDATED.

## Commands
```sh
pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/ingest_espn.py --start 2026-08-01 --output data
python scripts/predict.py --games data/games_2026.csv --away "Ohio State Buckeyes" --home "Michigan Wolverines" --asof 2026-10-20
```

## Operations
Open [Actions](https://github.com/The-Caves/cfb-model/actions/workflows/cfb-data-intake.yml) and select **Run workflow** to collect the first dataset. Inspect the `cfb-2026-data-<run_id>` artifact and `manifest.json`; only `SUCCESS` means all requested daily calls returned without errors. GitHub Actions scheduled jobs can be delayed or disabled by repository settings.

## Next work
The existing v0.9 research ZIP contains richer intake components and retrospective data but has **not** yet been migrated to this repository. The deployed model is an initial research baseline. Prioritize timestamped advanced play-by-play, verified injuries and odds, and strictly prospective evaluation before releasing any picks.

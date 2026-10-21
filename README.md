# College Football Prediction Model (2026 season)

**Project status: Research / not validated for betting.** Predictions must remain `PASS_UNVALIDATED` until timestamp-safe walk-forward evaluation demonstrates credible performance. Successful code tests or ingestion jobs do **not** establish prediction accuracy.

This public repository holds a reproducible 2026 college football data and model-development pipeline. It ingests scoreboard results and play-by-play features, archives audited pregame context, and will eventually evaluate straight-up (SU), against-the-spread (ATS) and totals (O/U) forecasts. Do not report subjective picks as generated model outputs.

## Implementation status — updated October 21, 2026

| Component | Status / evidence |
| --- | --- |
| ESPN 2026 completed results, raw snapshots and QA | Implemented and tested; 138-team FBS registry |
| Historical 2026 v0.9 score reconciliation | Implemented; disputed rows quarantined (see `docs/RECONCILIATION_2026.md`) |
| SportsDataverse 2026 PBP, EPA and advanced drive joins | Cloud-verified: 510 accepted games, 1,020 team-game and drive sides in a prior run |
| Unified 2026 enriched profiles | Cloud-verified: 138 schools and roughly 44 fields per profile in a prior run |
| Upcoming games, kickoff/rest, forecast and approximate travel | Implemented with provenance; incomplete coverage is explicit |
| Kickoff-aware incremental context refresh, persistent deltas, freezes | Implemented; state in `context-state` branch |
| Public official player availability | SEC, Big Ten, ACC and Big 12 implemented; latest live run succeeded with 0 misleading personnel-change alerts |
| Official athletics QB news discovery pilot | Five public team football RSS feeds, read-only review candidates; no player/starter inference |\n| Game-specific QB starter evidence gate | Implemented for explicitly reviewed official team/coach statements; **no automated nationwide confirmations** |
| Confirmed starting QBs and replacement-value effects | Actual upcoming game coverage still **UNKNOWN** until audited source records exist; replacement weights unvalidated |
| Timestamped opening/closing/live sportsbook markets | **Not implemented/validated** |
| Historical as-of training features, opponent-adjusted calibrated model, SU/ATS/O-U walk-forward tests | **Not completed** |

**Known cloud verification:** [PBP/drives ingestion](https://github.com/The-Caves/cfb-model/actions/runs/39544628568), [enriched profiles](https://github.com/The-Caves/cfb-model/actions/runs/39544914397), and [earlier availability refresh](https://github.com/The-Caves/cfb-model/actions/runs/39618526300). An earlier availability run reported 2 accepted ACC reports containing 458 availability designations, many ordinary AVAILABLE roster entries (**not** 458 injuries). The corrected full context run [39640130795](https://github.com/The-Caves/cfb-model/actions/runs/39640130795) and subsequent [QB news pilot run 39643068262](https://github.com/The-Caves/cfb-model/actions/runs/39643068262) succeeded with zero invented personnel status-change alerts. In the latter run, 109 upcoming games were observed, 89 had weather forecasts, and 91 had both approximate travel estimates. The five-official-feed pilot had 0 publisher errors, surfaced 1 unreviewed QB news article (an award, not a starter announcement), and made 0 confirmed-starter claims. A subsequent stricter filter was added to suppress this award noise; its live effect must be checked on the next run.

## Development and operating workflows

- [CFB Data Intake](https://github.com/The-Caves/cfb-model/actions/workflows/cfb-data-intake.yml): scheduled three times daily, manual dispatch, and push/PR validation. ESPN results, advanced ingestion, research feature store and artifacts with checksums/manifests.
- [CFB Pregame Context Delta](https://github.com/The-Caves/cfb-model/actions/workflows/cfb-context-refresh.yml): hourly GitHub Actions eligibility gate; three baseline refreshes/day, three-hourly inside 48h of kickoff and hourly inside 12h. Saves context, source health, material deltas and pre-kickoff observations to [`context-state`](https://github.com/The-Caves/cfb-model/tree/context-state).
- Diagnostic public-report workflows: `.github/workflows/cfb-report-probe.yml` and `.github/workflows/cfb-api-probe.yml`.

The pregame collector uses ESPN upcoming schedule/results, Open-Meteo weather, approximate **city-centroid straight-line miles** (not actual team travel), and `scripts/official_availability.py` for verified public conference publisher cards. Only published, two-team/game-matched, source-timestamped, pre-kickoff records can be accepted. A missing or pending report is **UNKNOWN**, never proof of a healthy player. Official `AVAILABILITY` does **not** establish an injury diagnosis, and does not identify a backup QB starter. Report provenance and failures are preserved.

Data collected or revised retrospectively must **not** be used as though available at the original pregame decision time. Freezes preserve the last observed pregame snapshot, not any postgame source. Workflow scheduling is not automatic model retraining or phone notifications.

## Resume development / public project handoff

1. Inspect current `main` HEAD, recent Actions results and `context-state/state/summary.json`; do not rely on stale documentation as proof of current run results.
2. Finish Step 4: verify the corrected availability deltas on a **real live context refresh**, examine `official_availability_manifest.json`, check that routine AVAILABLE roster rows do not create false personnel alerts, and preserve warnings for missing publisher coverage.
3. Populate independently reviewed game-specific starting-QB evidence through `data/manual/qb_starter_evidence_2026.csv`, including opponent, exact player, official-source statement, evidence scope, publication/capture/review timestamps. `scripts/qb_starter_review.py` gates these claims and quarantines contradictions; **no automated nationwide starter discovery/confirmation exists yet**. Do not infer a starter from an OUT designation, depth chart or previous box score.
4. Then integrate provenance-bearing historical and live sportsbook lines, earlier-season training priors and a complete opponent-adjusted prediction engine.
5. Evaluate chronological out-of-sample SU, ATS and O/U forecasts with true historical as-of sources, market baselines, calibration and ablations. Only graduate beyond `PASS_UNVALIDATED` on verified results.

**Model priorities:** opponent-adjusted offensive/defensive EPA, passing/rushing efficiency, QB play versus pressure, special teams, drive efficiency, explosives/volatility, red zone/4th down, pace, luck, garbage time, weather, rest/travel, injuries, dated market odds and line movement. Use recency and prior seasons only with leakage-free controls; previous research used a 28-point blowout cap, which must be independently validated rather than assumed optimal.

**Key source files:** `scripts/ingest_espn.py`, `scripts/ingest_advanced.py`, `scripts/build_profiles.py`, `scripts/combine_profiles.py`, `scripts/ingest_game_context.py`, `scripts/official_availability.py`, `scripts/availability_context.py`, `scripts/context_delta.py`, `scripts/context_archive.py`, `scripts/predict.py`. More detail: [advanced data](docs/ADVANCED_INTAKE.md), [reconciliation](docs/RECONCILIATION_2026.md), [game context](docs/GAME_CONTEXT.md), and [context deltas](docs/CONTEXT_DELTA.md).

## Local validation

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/ingest_espn.py --start 2026-08-01 --output data
python scripts/build_profiles.py --games data/games_2026.csv --output data --registry data/archive/2026_team_aliases.csv
```

A complete ingestion run requires external networks and is best verified in GitHub Actions. Full outputs are commonly **workflow artifacts**, not files committed to `main`. Logs and data manifests should be checked rather than inferring successful ingestion from a green unit-test badge.

## Public-repository safety

Only publish reproducible project code, non-sensitive configuration, public-source citations, validated metrics, tests and generic operational documentation. **Do not commit access tokens, API keys, personal contact information, private messages/conversation transcripts, passwords, unpublished privileged data, or user-specific account details.** Use GitHub Actions secrets for any future credentials; never print credentials in logs. Public player-availability reports are **not** private medical records. Avoid inferring medical conditions from roster status.


### Starting quarterback evidence protocol

The separate `data/manual/qb_starter_evidence_2026.csv` is intentionally header-only until someone reviews genuine public official game-specific claims. An entry must match the current upcoming ESPN game ID, home/away opponent, kickoff, name, official team release or on-record coach confirmation, explicit this-game starting statement, source URL, publication/capture/review timestamps before kickoff, and an APPROVED review. Statements more than 14 days before kickoff, projected starters, depth charts, competing claims and official QB availability contradictions cannot produce `confirmed_qb_starters`. `context_manifest.json` records accepted/rejected counts and reason codes; a verified evidence record does not validate model weights or override `PASS_UNVALIDATED`. The local protocol cannot independently prove a source page is authentic or unchanged; reviewers must inspect the actual source. See `docs/GAME_CONTEXT.md`.

### Official-source QB news pilot

`scripts/qb_official_news_watch.py` checks **only five explicitly verified public team athletics football RSS feeds** (NC State, Iowa State, James Madison, Navy, FIU) when those schools have upcoming games in the context slate. Headlines and excerpts mentioning both a QB term and a starter/depth/injury term are archived as `UNREVIEWED_NEWS_CANDIDATE` with source URL and publication/capture timestamps in the workflow's `qb_news_candidates.json` artifact. **No candidate is automatically promoted to a QB starter claim.** RSS feed outages are reported explicitly; this pilot does not cover other FBS schools or prove that any headline names a starter. Full reviewed starter provenance remains a separate manual evidence workflow.

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
| Official athletics QB news discovery pilot | Seven public football RSS feeds; 7/7 fetched successfully in verified full cloud run; no automatic starter inference |
| Per-game QB source coverage queue | Implemented with timestamped game/team records, review priorities, fetch health, and cloud-verified context-state persistence |
| Game-specific QB starter evidence gate | Implemented for explicitly reviewed official team/coach statements; **no automated nationwide confirmations** |
| Confirmed starting QBs and replacement-value effects | Actual upcoming game coverage still **UNKNOWN** until audited source records exist; replacement weights unvalidated |
| FanDuel-first market parser, event identity, local vault and as-of market-feature board | Implemented and **synthetically tested**, not connected to authenticated real FanDuel API; true opening/closing prices not verified |
| Historical as-of training features, opponent-adjusted calibrated model, SU/ATS/O-U walk-forward tests | **Not completed** |

**Known cloud verification:** [PBP/drives ingestion](https://github.com/The-Caves/cfb-model/actions/runs/39544628568), [enriched profiles](https://github.com/The-Caves/cfb-model/actions/runs/39544914397), and [earlier availability refresh](https://github.com/The-Caves/cfb-model/actions/runs/39618526300). An earlier availability run reported 2 accepted ACC reports containing 458 availability designations, many ordinary AVAILABLE roster entries (**not** 458 injuries). The corrected full context run [39640130795](https://github.com/The-Caves/cfb-model/actions/runs/39640130795) and subsequent [QB news pilot run 39643068262](https://github.com/The-Caves/cfb-model/actions/runs/39643068262) succeeded with zero invented personnel status-change alerts. In the latter run, 109 upcoming games were observed, 89 had weather forecasts, and 91 had both approximate travel estimates. The five-feed initial pilot had 0 publisher errors, surfaced 1 unreviewed QB news article (an award, not a starter announcement), and made 0 confirmed-starter claims. A subsequent stricter filter was added to suppress this award noise; its live effect must be checked on the next run.

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

`scripts/qb_official_news_watch.py` checks **seven listed public team athletics football RSS feeds** (NC State, Iowa State, James Madison, Navy, FIU, Texas, North Carolina) when those schools have upcoming games in the context slate. Headlines and excerpts mentioning both a QB term and a starter/depth/injury term are archived as `UNREVIEWED_NEWS_CANDIDATE` with source URL and publication/capture timestamps in the workflow's `qb_news_candidates.json` artifact. **No candidate is automatically promoted to a QB starter claim.** RSS feed outages are reported explicitly; this pilot does not cover other FBS schools or prove that any headline names a starter. Full reviewed starter provenance remains a separate manual evidence workflow.

### Resuming Step 4 — source-coverage review queue

The scheduled context workflow now runs `scripts/qb_review_queue.py` after official-news collection. Each upcoming team-game slot carries a source coverage state (`FETCHED`, `FETCH_FAILED`, `NOT_CONFIGURED` or unknown), a separately supported starter status, public QB availability signals, and unreviewed news candidate links. The generated `qb_review_queue.json` is included in Actions artifacts. It does **not** perform nationwide starter confirmation, and a fetched feed is not proof that a player is starting.

`scripts/qb_review_archive.py` enforces that queue capture preceded the final context cutoff, compares game and team identity, and refuses unsupported confirmed-starter labels or promoted news. The context archiver writes `context-state/state/qb_review_latest.json`, dated compressed `qb_review/YYYY/MM/DD/` snapshots and aggregate queue coverage in `state/summary.json`. Games that crossed kickoff during collection are removed. Unit tests and complete context-state archive writes passed in [run 39657256288](https://github.com/The-Caves/cfb-model/actions/runs/39657256288).

Remaining Step 4 limitations: only seven official athletics news feeds are registered, starting-QB evidence still requires manual review, four-conference official player availability is incomplete for national FBS coverage, and QB replacement-point adjustments remain untrained. Continue to Step 5 market integration only with these uncertainty flags preserved; don't confuse source-pipeline completeness with betting-model validation.

### Step 4 exit gate for beginning Step 5

- [x] Game-specific rest, venue, partial forecasts and approximate travel collected and audited
- [x] 2026 official player availability ingested conservatively with publisher and kickoff provenance
- [x] Routine AVAILABLE listings filtered from injury/change alerts
- [x] Official QB claim gate blocks unsupported, speculative, contradictory and post-cutoff evidence
- [x] Two-sided per-game QB source coverage queue and snapshot persistence validated by [cloud run 39651180891](https://github.com/The-Caves/cfb-model/actions/runs/39651180891)
- [x] Expanded seven-school RSS registry live-tested with 7/7 fetched and zero provider errors ([run 39657256288](https://github.com/The-Caves/cfb-model/actions/runs/39657256288))
- [ ] National confirmed-QB discovery: intentionally incomplete; must retain UNKNOWN by team/game
- [ ] QB-specific scoring effects: intentionally deferred to trained, walk-forward model evaluation

**Step 4 infrastructure is now verified complete with explicitly partial source coverage.** Lack of verified starters remains a model-input uncertainty; do not block implementation of Step 5 market data, and do not fabricate starter identities or arbitrary replacement-point penalties.

### Current handoff to Step 5

Step 4's dated [exit verification](docs/STEP4_EXIT_VERIFIED.md) confirms that seven official school feeds were retrieved in live Actions run 39657256288, and that its saved QB review queue contains 218 team-game slots (13 with fetched sources, 205 not configured), four with published QB availability signals and zero independently confirmed starters. Missing data stays `UNKNOWN` and betting output stays `PASS_UNVALIDATED`. The market-source requirements and leakage safeguards for the next stage are in [Step 5 market readiness](docs/STEP5_MARKET_READINESS.md). This repository includes no private personal information or secret credentials.

### Step 5 started — FanDuel-first market data (October 21, 2026)

**FanDuel is the default book**, but quote records retain an explicit bookmaker ID for future comparisons. See [Step 5 FanDuel market plan](docs/STEP5_FANDUEL_MARKET_PLAN.md) for opening vs first-seen prices, same-book line movements, decision-time fresh quotes, implied probabilities and parlay correlation limitations. [Step 5 market readiness](docs/STEP5_MARKET_READINESS.md) retains event identity, evidence and walk-forward requirements.

Implemented research-only code: `scripts/market_quotes.py` normalizes NCAAF moneyline, spread and total quotes from The Odds API v4; `scripts/market_client.py` optionally fetches `fanduel` using an environment-held `ODDS_API_KEY` and quarantines unsafe input. CI tests cover book-specific quote parsing, historical timestamp checks, first-observed movement and masked provider errors. **No API key is connected, no actual market snapshots are being collected, no historical FanDuel coverage has been authenticated and no scheduled betting-market polling has been activated.** The current prediction model remains `PASS_UNVALIDATED`.

### Step 5A progress — event identity audit

The FanDuel-first provider-neutral parser (`scripts/market_quotes.py`) and opt-in API client (`scripts/market_client.py`) are joined by an offline, **strict timestamp-aware event crosswalk** (`scripts/market_event_crosswalk.py`). It matches curated school aliases, opposing teams, kickoff time and ESPN IDs; quarantines reversed sites, aliases with multiple meanings, duplicate events and historical ESPN snapshots that were not available before the quote. `scripts/market_coverage_audit.py` summarizes permitted local provider sample coverage and rejection reasons **without writing market prices**. See [Step 5A event crosswalk and audit runbook](docs/STEP5A_EVENT_CROSSWALK.md).

These components are fixture-tested in CI. **Real FanDuel quotes, an authenticated historical feed and provider-specific opening/closing coverage have not yet been accessed.** A small legitimately accessible test sample and provider terms/usage evaluation are required before live collection, scheduled polling or betting-model market joins. Opening line vs first observed, decision-time FanDuel price and multi-leg correlation handling are documented in the [FanDuel market plan](docs/STEP5_FANDUEL_MARKET_PLAN.md). Predictions remain `PASS_UNVALIDATED`.

### Step 5B — private FanDuel market history (2026-10-21)

The FanDuel-first Step 5B implementation now includes **append-only, idempotent local SQLite market snapshots** in `scripts/market_vault.py` and **manual, opt-in collection** through `scripts/market_capture.py`. The vault refuses to write into the public repo, requires private local file/directory permissions, stores source/retrieval timestamps, source hashes, full market-side quotes and provider credit counters, and identifies stale, retrospectively fetched and post-kickoff quotes. Public Actions runners cannot initiate private provider fetching. Previously available normalized-JSON exports are similarly blocked from writing inside this checkout. See [Step 5B private storage runbook](docs/STEP5B_PRIVATE_MARKET_STORAGE.md).

**No actual FanDuel data or paid historical snapshot has been fetched, no API credentials have been connected, no market polling is scheduled and the SQLite store is not encrypted or remotely hosted.** A properly licensed sample and a durable **private encrypted** host are the next dependencies. No market-backed model picks exist; research output remains `PASS_UNVALIDATED`.

### Step 5B validation checkpoint — successful synthetic end-to-end test

[CI run 39678475173](https://github.com/The-Caves/cfb-model/actions/runs/39678475173) completed **178 passing tests**, including [synthetic end-to-end validation](docs/STEP5B_VALIDATION.md) of mock FanDuel-format quotes -> strict ESPN game crosswalk -> private append-only market vault -> as-of price lookup and movement. The test saved three synthetic snapshots / 18 two-sided quote rows, quarantined a reversed matchup, rejected duplicates, suppressed post-kickoff prices and stopped retrospectively downloaded quotes from overriding genuinely available live prices. **Zero actual provider API requests and zero credits** were involved.

For cost planning, `python -m scripts.market_preflight --historical --requests 10` estimates an upper bound of 300 provider credits at one book and three featured markets, **without contacting the API**. Explicit manual network collection now has a default 3-credit preflight ceiling; a paid one-snapshot historical request also requires an acknowledgement and consciously raising the ceiling (e.g., `--max-estimated-credits 30`). See [private market storage guide](docs/STEP5B_PRIVATE_MARKET_STORAGE.md).

**Real FanDuel odds validation remains pending.** We have not connected an API key, downloaded actual line history or activated unattended polling. Model output is still `PASS_UNVALIDATED`; nothing here establishes a profitable or live-executable parlay recommendation.

### Step 5B real-source smoke test — partial (2026-10-21)

A [public, timestamped third-party FanDuel NCAAF page](https://agentbets.ai/odds/fanduel/ncaaf) was checked against the saved ESPN upcoming-game slate. Initial exact-name matching found 7/10 fixture identities; after three **explicit and source-supported** alias additions, all 10/10 matched unique opponents and kickoff times. The aliases live in `data/archive/2026_market_provider_aliases.csv`; `scripts/market_event_crosswalk.py:load_market_registry` refuses ambiguity and silent overrides. Full details and limitations: [Step 5B real-data smoke report](docs/STEP5B_REAL_DATA_SMOKE.md).

**This is not a real API-acceptance pass.** The third-party odds page snapshot was labeled 2026-10-21 20:00 UTC and the available ESPN context snapshot was collected at 20:39 UTC; the latter is **not** valid as-of context for a 20:00 UTC decision. No original Odds API event IDs or JSON, genuine price imports, credit headers, historical line series or API credentials were available. Production accepts no such quote until authenticated and time-matched. `PASS_UNVALIDATED` remains in effect.

### Step 5C — point-in-time FanDuel market feature board (October 21, 2026)

`scripts/market_features.py` now joins **privately stored** market selections to a pre-existing timestamped ESPN matchup, produces same-book first-observed-to-latest movement, both selection prices, implied bookmaker probabilities, two-way no-vig normalization, quote/source-update ages, and explicit missing-market indicators. It rejects post-kickoff quotes, future ESPN context, prices downloaded retrospectively after the decision cutoff, contradictory simultaneous market quotes, and duplicate provider game IDs. Quotes never become verified opening/closing lines or executable FanDuel slip prices, and the resulting board is **research-only**.

See [Step 5C market feature board](docs/STEP5C_MARKET_FEATURE_BOARD.md) and [Step 5B real-source smoke](docs/STEP5B_REAL_DATA_SMOKE.md). Code/fixture CI passes, but **no real API key or authenticated FanDuel odds data exists in this project**. Do not put generated private bookmaker prices in the public repo or workflow artifacts. Matchup-model training, historical walk-forward tests and betting validation remain unfinished; `PASS_UNVALIDATED` stays mandatory.

### Step 5D foundation — pregame/postgame separation and research-only evaluation

The synthetic market-data evaluation foundation is now in code:

- `scripts/market_settlement.py` grades selection-side FanDuel-format moneylines, spreads and totals against completed final scores (WIN / LOSS / PUSH) **without putting final scores into pregame model features**.
- `scripts/market_walkforward.py` creates game-disjoint, chronological splits. It only allows an old completed game's label into training if that final was published before the fold's training cutoff, and excludes missing/late labels rather than assuming outcomes.
- `scripts/market_evaluation.py` supports timestamped probability diagnostics (Brier and log loss) against a no-vig book-price baseline. It refuses forecast timestamps or declared training cutoffs that would leak future information and excludes PUSHes from binary outcome scoring. These are evaluation *mechanics*, not trained/model-proven probabilities.

The [Step 5D evaluation report](docs/STEP5D_EVALUATION_FOUNDATION.md) records **239 passing CI tests** in [run 39687070388](https://github.com/The-Caves/cfb-model/actions/runs/39687070388). Only fabricated markets and synthetic forecast probabilities were used. **No real FanDuel feed, authentic opening/closing price series, opponent-adjusted calibrated prediction model, or out-of-sample betting performance has been validated.** The 2026 enriched features remain unconnected to a final trained model; no picks or wagering recommendations are authorized. `PASS_UNVALIDATED` stays enforced.


### v0.3 candidate — weekly advanced feature integration and retrospective research

\`scripts/model_v03.py\` now connects prior 2026 play-by-play EPA, pass/rush splits, success, explosive plays, pressure, drive summaries and opponent-adjusted (prior-opponent-rate) features to a separately trained score-margin/total ridge candidate. It rebuilds each matchup's team profile from **games on earlier calendar dates** rather than leaking end-of-season enriched statistics. It benchmarks against a score-only ridge baseline and an opponent-adjustment ablation in weekly held-out windows. The full intake workflow runs it after advanced ingestion and uploads research reports. See [v0.3 research method and limitations](docs/MODEL_V03.md).

**Evidence limitation: SportsDataverse 2026 parquet releases are retrospectively mutable and lack authenticated historical publication snapshots.** These tests prove timing checks in software but are NOT a leakage-free, real-time-known football backtest. No genuine historical FanDuel lines, ATS/O-U performance, SU calibration or player-specific injury weights are validated. Output remains \`PASS_UNVALIDATED\` until actual pregame source history and out-of-sample validation exist.

### v0.3 milestone checkpoint and source-history constraint

All four *research-code* steps are connected through `scripts/model_v03.py`: 2026 game-level advanced stats; prior-calendar-day weekly opponent-aware profiles; score-margin/total ridge fitting; and weekly walk-forward baseline versus advanced versus no-opponent-adjustment comparisons. Regression tests explicitly check that a later same-day game cannot learn an earlier same-day result and that exported pregame features are disjoint from final-score labels. The output artifact stores `weekly_pregame_features.csv`, `weekly_postgame_labels.csv`, `research_backtest.json`, and held-out retrospective predictions, **never private betting prices**.

**No timestamp-authenticated historical release versions exist for the retrospective PBP input**; real-source leakage-free backtests and an actual FanDuel-anchored ATS/O-U comparison remain blocked, even after the research code and first cloud data run pass. `PASS_UNVALIDATED` remains unchanged.

### Corrected v0.3 real 2026 retrospective benchmark — 2026-10-21

[Cloud intake run 39691533017](https://github.com/The-Caves/cfb-model/actions/runs/39691533017) **fully passed**, including 249 tests and actual ingestion of the corrected Eastern-date 2026 v0.3 model. Four expanding calendar-week folds covered **239 held-out games**, using 513 ESPN finals and 510 validated two-sided PBP games. Experimental straight-up accuracy was **60.25% score-only**, **61.92% advanced v0.3**, and **61.51% without opponent-adjustment features**. Margin MAE improved approximately 0.29 points under v0.3; total MAE did not improve. The ablation produced marginally better Brier and total error than full v0.3. Complete week-level results and caveats: [v0.3 research results](docs/MODEL_V03_RESEARCH_RESULTS.md).

**Do not promote v0.3 or use it for betting picks.** The 2026 advanced source was retrieved retrospectively after prior matchups, true historical publication versions and FanDuel prices are missing, and this is not a fully source-time-leakage-free or market-validated test. All outputs remain `PASS_UNVALIDATED`.

### v0.4 Step 1 — historical profile archive

Added scripts/weekly_profiles.py, producing one deterministic, checksummed research profile file for every 2026 game date and weekly Saturday anchor, for all 138 FBS teams. Profiles are built using only earlier football calendar dates and share the same opponent-adjusted history updater with v0.3; changing October results cannot change a September reconstruction. The capture manifest tracks provider retrieval and source checksums; conflicting writes are rejected. The data intake workflow archives outputs as temporary artifacts. See [Step 1 profile method](docs/V04_FROZEN_WEEKLY_PROFILES.md). **These are retrospectively reconstructed, not authentic historic source snapshots, and PASS_UNVALIDATED still applies.**

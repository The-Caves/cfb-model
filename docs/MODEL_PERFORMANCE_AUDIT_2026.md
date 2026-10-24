# 2026 College Football Model Performance and Decision Preservation

**Updated:** October 24, 2026 (America/New_York)  
**Overall model status:** `PASS_UNVALIDATED` — research outputs, not proven profitable or actionable betting recommendations.

## Verified checkpoint: the Rice @ Florida Atlantic discrepancy

The **original frozen 2026-10-24 10:04:58 ET model forecast** (`forecast_run_id=40100613531`) predicted **Florida Atlantic by 26.85197**, with model total **51.69786**, and a home-win research estimate **0.89953** (uncalibrated). It forecast **FAU 39.27492 – Rice 12.42294**.

The website subsequently observed **DraftKings FAU -9.5** at **2026-10-24 10:31:55 ET** and O/U **53.5**. The resulting displayed research choices were **FAU ATS, UNDER**, and the model/market ATS disagreement was **17.35197 points**. The two timestamps are distinct: do **not** backfill the later sportsbook line into the original forecast time.

An early Rice lead is **not a final-score grade**, and does not justify retrospectively altering this recorded projection. This matchup belongs in the **high model–market disagreement** cohort for later final grading and calibration review. Neither the final SU/ATS/O-U outcome nor the mechanism causing potential error is currently established by this snapshot.

## What is genuinely preserved (not just rendered)

1. **Original frozen model outputs**: `context-state/research_2026/forecast_index.json`, `research_2026/forecasts/YYYY/MM/DD/run-*.json.gz`. Write-once SHA-verified forecast records, retaining the code/model identifier, capture time, and all future games at that instant.
2. **Free observed sportsbook quotes**: `context-state/research_2026/free_market/YYYY/MM/DD/*.json.gz`. The collector stores provider, scoreboard ID, home spread, total, *collection time* and uncertainty about upstream publication time. No inferred historical opening or closing odds.
3. **Already synchronized forecast-market comparisons**: `context-state/research_2026/free_market_comparisons/index.json` and corresponding `run-*.json.gz`. Entries can be used in strict predecision backtests only where `market_observed_utc <= forecast_observed_utc < kickoff_utc` and all identity checks pass.
4. **NEW: exact website-visible decision snapshots**: `context-state/research_2026/site_board_snapshots/index.json` and `YYYY/MM/DD/run-<workflow_id>.json.gz`. On each successful website build, after the page payload is produced, a separately authorized `archive` job saves all **not-yet-started games** with frozen projected margin and total, market provider/spread/total, originally observed forecast time, sportsbook collection time and the displayed ATS/O-U side. It records disagreements greater than or equal to **10 points** as **`HIGH_MODEL_MARKET_DISAGREEMENT`**. Records are immutable and checksum indexed; repeated displays of the same game remain separate snapshots for audit but **must not** count as independent games or wagers.
5. **Independently observed final scores**: `context-state/research_2026/market_finals/index.json` and `research_2026/forecast_grades_index.json`, with digest-verified game identity and eventual final-score settlement.
6. **Postgame prospective scoring reports**: `scripts/personnel_forecast_grade.py`, `scripts/free_market_final_match.py`, `scripts/free_market_final_grade.py`, `scripts/free_market_performance.py`, and `scripts/free_market_acceptance.py`. The score-grading system supports SU, ATS and totals, one game per market rather than every provider/forecast duplicate.

**Important:** The website's very latest displayed line can be **newer** than the original frozen model forecast. The additional site board snapshots support honest later prospective grading as of their *display/market* observation, but are **not automatically equivalent** to the older synchronized forecast–market comparisons used in current out-of-sample validation. Until integrated into a separately validated deduplicated scorecard, they are an auditable evidence stream, not additional confirmed performance results. A page refresh by a reader is not a new GitHub forecast or new archived decision; scheduled dashboard builds are the archiving cadence.

## October 24 actual as-of scoring checkpoint

The latest verified intake/grading workflow before today's games ([40100613531](https://github.com/The-Caves/cfb-model/actions/runs/40100613531)) found:

| Outcome type | Wins | Losses | Pushes | Distinct graded games |
| --- | ---: | ---: | ---: | ---: |
| SU | 3 | 2 | 0 | 5 |
| ATS | 3 | 2 | 0 | 5 |
| O/U | 2 | 3 | 0 | 5 |

The original immutable archive contained **35 forecast runs**, **15 synchronized comparison runs**, **five independently verified completed games** and **696 provider–forecast market pairings**. Only **36 provider–forecast pairings** could be matched to these five completed games; duplicates were deduplicated for the final 5-game market performance rates. Data for pending games may not be claimed as wins/losses. Sample size is too small to infer calibrated probabilities or future ROI.

**Site-archive acceptance:** [CFB Research Dashboard run 40113419813](https://github.com/The-Caves/cfb-model/actions/runs/40113419813) produced a verified `research_2026/site_board_snapshots/index.json` entry with **93 future games and 36 paired observed market lines/ATS/O-U directions** at ~12:51 PM ET; noon games already underway were correctly excluded from this *new* website snapshot. Earlier frozen 10:04 AM research and market observations are retained through the independent existing archives. The archive job initially masked a missing dependency behind `tee`; fixed by installing requirements and enabling `set -euo pipefail`, then verifying the committed indexed snapshot on `context-state`. Do not describe the first failed apparent-success run as archived.

## Forward model-evaluation priorities

- Monitor final Rice–FAU *after it is officially completed* and evaluate SU/ATS/total plus signed margin error without hindsight.
- Track 10+ point forecast-to-market disagreements as a prespecified cohort, including how often they predict better or worse than market baseline. Do not use one early upset as grounds to train a new coefficient.
- Evaluate expected calibration of raw win probability and projected scoring margin by buckets; inspect opponent adjustment, small-sample regression, recent-team priors, and QB availability before making feature changes.
- Deduplicate outcomes by ESPN game ID, market side and fixed earliest pregame decision policy; preserve every alternative historical observation separately.
- If we test a new model candidate, fit/validate in chronological splits; compare SU, ATS, O/U, calibration and baselines, and promote only on actual out-of-sample gains.

All artifacts remain research-only, and no AWS charges or paid sports-data service is necessary for the archival mechanism.

# V14 — scored opponent-specific close-game challenger, ATS/total calibration, and player scenarios

**November 13, 2026.** Repository: `The-Caves/cfb-model`. Development branch `research/v14-close-games-ats-totals-player`. This is the first new scored challenger after V13, which previously only added probabilistic uncertainty to the **unchanged V04 points**.

**Important distinction:** V14 now genuinely changes projected home/away scores, while retaining the V04 opponent-strength foundation. It is **not** validated for betting or automatic promotion. A clear distinction is kept between the 377 repeatedly analyzed 2026 historical games and first predictions actually frozen before future games.

## Implemented source-dated stages

1. **Matchup profile** (`scripts/v14_matchup_features.py`): pre-original-week averages of offense and opposing defense pass/rush EPA; pass reliance versus pressure allowed/generated; explosive pass exposure; genuine completed-score turnovers/takeaways; red-zone play success (explicitly **not** actual red-zone-trip TD conversion); and recorded game play volume. 35-day recency weight and minimum three real games per involved team/metric. Partial or missing sources produce an explicit unready feature vector; neither unknown QBs nor missing defense statistics are assigned zeroes.
2. **New actual scoring model** (`scripts/v14_residual_challenger.py`): two separate ridge-penalized adjustments trained on **previously completed V04 forecast weeks' actual margin and total residuals**. Intercept and seven feature weights are regularized to zero, with fixed penalties and optional close-game attenuation. Corrections capped at six points. Original V04 points remain a separately graded control, never overwritten.
3. **Market reliability** (`scripts/v14_market_calibration.py`): independent two-parameter penalized calibration for `P(home cover)` and `P(total over)`. Only genuinely observed historical quoted spreads/totals and completed outcomes before the target week can enter fitting; push outcomes excluded. Fixed 58% research-only PASS gate. Calibration **does not alter game scoring coefficients** or manufacture missing market quotes or prices. Neither 58% model confidence nor historical direction accuracy is equivalent to positive EV or ROI.
4. **Real player-level simulation** (`scripts/v14_player_scenarios.py` and optional `quotes` in `scripts/player_prop_conserved_opportunities.py`): reuses existing conserved, empirically sampled same-game offensive possessions, attempts, completions, receiving/rushing yards, and unmodeled-player buckets. True predecision matched two-sided bookmaker lines can be tested against actual simulated trial distributions for verified athlete-ID/metric pairs. Passing/rushing/receiving TDs and interceptions are **explicitly unsupported and PASS**, not invented as zero or projected from team TD probability. Unknown QB1/WR/RB participation remains conditional; player projection probabilities are not individually calibrated. Model team points and athlete opportunity statistics have **not** been fully jointly fitted; no false claim otherwise.
5. **Website research shadow + future grading** (`scripts/site_v14_shadow.py`, `scripts/site_v14_performance.py`, site workflow and UI): use frozen source 2026 artifact to fit prior-week V14 residuals; use only the current same-run predecision PBP and turnovers for upcoming-game matchup. A stale current as-of date yields **PASS**, leaving V04/V13 intact. The site shows V14 scores in a collapsed research view, never replaces V04 primary projected winner/market decision. `site_decision_archive.py` checks model identity, coherent team scores, six-point adjustment cap, source timing, V13-bound probability math and market quote before freezing a **separate V14 first pre-kickoff receipt**. Later grades compare the first observed V14 versus the original V04 score **on the exact same independently settled future games**. No historical backfills counted.

## Original 377-game, 7-week chronological research performance

The frozen 2026 V13 comparison set and fixed 2026 original team-game PBP / observed turnover source were taken from the exact prior successful GitHub artifacts. All training labels are from whole earlier V04 forecast weeks. No same-week or future results were available to fitted coefficients.

| Metric | V04 / V13 preserved | V14 joint-close challenger |
| --- | ---: | ---: |
| Correct straight-up winners | 246/377 | **248/377** |
| Margin MAE (lower better) | 12.926648 | **12.890082** |
| Total MAE | 13.541367 | **13.459190** |
| Margin CRPS | 9.163757 | **9.138697** |
| Total CRPS | 9.540646 | **9.523420** |
| Home-winner Brier | 0.215008 | 0.215000 |
| ATS directions, observed quotes only | 70/156 | **74/156** |
| O/U directions, observed quotes only | 62/154 | **64/154** |
| Cover-probability Brier on observed quoted games | 0.268787 using V14 calibration with unchanged V13 points | **0.267758** |
| Total-over Brier on observed quoted games | 0.268536 using V14 calibration with unchanged V13 points | **0.266552** |
| Matched games with V14 pre-cutoff matchup feature coverage | 0 modified | 331/377 (46 preserve V04) |

For context: the *original* V13 probability Brier (without V14's separate calibration) was ATS **0.267208**, totals **0.270122**. V14's cover calibration **0.267758 is actually slightly worse than original V13**, despite 4 extra directional covers. Both ATS and totals probability Brier values are above **0.25**, the all-50% trivial forecast's Brier on binary non-push quotes. No bookmaker profitability or price advantage has been demonstrated.

V14 model ablations:
- Margin-only: 248/377 SU, 74/156 ATS, margin MAE 12.890793; no score-total changes.
- Total-only: 246/377 SU, 62/154 O/U, total MAE 13.462427.
- Joint no attenuation: 248/377 SU, 74/156 ATS, 62/154 O/U, margin MAE 12.890793, total MAE 13.462427.
- **Joint-close:** 248/377 SU, 74/156 ATS, 64/154 O/U, margin MAE 12.890082, total MAE 13.459190. This is a slight improvement, **not an independently selected winner**.

## Competitive-game analysis

| Frozen matchup segment | Historical count | V04 correct SU | V14 joint-close correct SU |
| --- | ---: | ---: | ---: |
| V04 predicted margin 0–3 | 85 | 43 | **45** |
| V04 predicted margin 3–7 | 91 | 55 | 55 |
| V04 predicted margin 7–10 | 65 | 43 | 43 |
| V04 predicted margin greater than 10 | 136 | 105 | 105 |
| Authentic archived market quote spread abs <=3.5 | 46 | 16 | **20** |

The improvements in the close quote subset are encouraging but **only 20/46 = 43.5%**. V14 still is not reliable in close sportsbook markets. The market sample begins late in the historical period (40 prior quotes for calibration by Oct 31, 99 by Nov 7). The strongest extra SU result is concentrated in the Oct 31 week: V04 42/59 vs V14 45/59. On Oct 17 V14 lost two SU calls relative to V04.

For transparency, **V14's 58% research PASS gate produced only 24 correct directions in 64 ATS signals and 16 correct directions in 36 totals signals** in the historical trial. These are NOT promising selection strategies. Do not use research signals for wagers, or promote them on the website. A future selective betting system needs authentic, timely book odds, threshold calibration and new independent validation rather than greater assertiveness.

## Additional independent within-cohort calibration cross-check

The separate [V14 cross-check run #43527440626](https://github.com/The-Caves/cfb-model/actions/runs/43527440626) **passed**. It runs the original `v14_backtest.py` and a second `v14_walkforward.py` evaluator using `v14_ats_totals_calibration.py`, which fits margin and total variance from earlier **out-of-fold V14 predictions** rather than from scores seen in the same week. That preserves all 377 original game identities and the 331/377 source-ready opponent matchups (46 lacked complete earlier matchup data).

| Cross-checked model | Correct winners / 377 | Margin MAE ↓ | Total MAE ↓ | ATS Brier ↓ | O/U Brier ↓ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen V04/V13 scores | 246 | 12.92665 | 13.54137 | 0.267208 | 0.270122 |
| V14 joint regularized matchup residuals | **248** | **12.89079** | **13.46243** | **0.266094** | **0.266631** |
| V14 close-gated joint variant | **248** | **12.89008** | **13.45919** | 0.266193 | 0.267591 |

The marginal score improvement is not evidence of an independent sportsbook edge. The underlying 156 spread and 154 total historical quotes have limited market-time authentication; neither observed ATS Brier nor totals Brier is reliably better than an untuned 0.25 constant 50% benchmark. The historical 58% confidence PASS policy performed poorly on selected signals, and we will not promote that policy.

V14 player simulation also passed conservation and exact player/price matching gates: a two-sided, time-stamped bookmaker prop quote may produce **conditional** over/under simulation frequencies, but a missing line, unsupported player metric, unverified source, or unconfirmed starter cannot produce a claimed profitable selection. Touchdown opportunities remain unsupported until source-verified goal-line player usage exists. No player-prop profit metric is claimed.

## Integrity and limits

- GitHub Actions V14 workflow runs stringent date/cutoff, missing-source, score coherence and player-prop quote identity guards, plus the **full repository regression suite**.
- Historical source original first-publication (2026 ESPN PBP and turnover data) is still unauthenticated. Download dates are not past-game decision-time authentication; all reported past metrics are **retrospective research**, not truly live past performance.
- The 377-game cohort has been reused in V04–V14 investigation. Further penalty or weight tweaks based on these outcomes would bias any claim of future improvement.
- V14 model has **not** proved better than V04 on truly new games. The published primary scoring engine is still V04; V13 remains its independent probability layer.
- Player opportunities can be sourced and simulated with preserved team budgets, and two-sided actual prop odds can be evaluated conditionally, but no V14 player prop hit-rate, MAE superiority, expected value or bankroll ROI has been established. The existing PlayerForm research is separately tracked.
- No source-confirmed historical starter QB/injury/weather value adjustments have been fitted; they remain deliberately excluded rather than assigned arbitrary effects.

## Release and next independent gate

Publish **only the optional research V14 shadow and future-grade capture**, not a scored/betting model promotion. Retain the original V04/V13 outputs as baseline. Before future games, freeze candidate `joint_close`, shrinkage penalties and 58% research PASS threshold; do not keep searching this same cohort.

Predeclare success criteria for subsequent unseen source-verified matches: a reasonable number of **independent future football weeks**, paired winner/competitive-game accuracy and margin/total MAE & CRPS vs V04, and ATS/OU Brier/log loss / 80% interval coverage with genuine pregame matched book observations. Player-prop thresholds need first-observed, real two-sided pregame quotes and athlete IDs; performance must compare the exact same confirmed participants, game and stat categories against a frozen simple historical baseline. Remain PASS for unconfirmed starters, unsupported prop categories, stale source or missing sportsbook lines.

**Run:** `.github/workflows/cfb-v14-research.yml`. Full game-level report: `cfb-v14-close-matchup-ats-total-player-research` in the successful V14 action. Do not merge this as a new scoring champion based only on repeated historical research.

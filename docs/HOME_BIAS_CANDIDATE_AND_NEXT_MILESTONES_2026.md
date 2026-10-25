# Home-bias correction candidate and follow-on QB / game-total roadmap

**Date:** October 25, 2026  
**Current public forecast:** `V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1` (unchanged).  
**New shadow model:** `HOME_MARGIN_PRIOR_GAMES_RECENCY14D_CANDIDATE_V1`.  
**Betting clearance:** `PASS_UNVALIDATED`. No selection/score has been retroactively rewritten.

## Why milestone 1 was necessary

The October 24, 2026 44-game retrospective diagnostic found all 44 ATS model recommendations were home teams, **equal to the naïve always-home ATS baseline of 28–16**. Training used 522 reconstructed 2026 scores in the October 24 capture, including many early games where neither team had a prior team performance profile. The full-sample ridge intercept was +13.94 home points, a strongly mismatched pooled baseline. This was an identified input/target problem, not proof of exploitable sportsbook edge.

## Milestone 1: time-aware, dual-profile margin candidate

Code: `scripts/home_bias_candidate.py`, `tests/test_home_bias_candidate.py`. The live pipeline continues to run `scripts/personnel_forecast.py` with the original baseline. The candidate is **isolated** and **does not automatically replace it**.

1. Fit against authentic 2026 completed-game labels only, strictly **before** the first test day of each fold.
2. Keep the exact 14 features and ridge penalty (45), avoiding simultaneous feature-set and target changes.
3. Exclude *candidate training* games where **either** team lacked a prior-2026 completed-game profile (prevents week-zero sparse feature priors dominating learned home intercept).
4. Weight eligible training examples with `2 ** (-age_in_days / 14)`, normalized to mean 1, with fully weighted ridge optimization, zero-penalty fitted intercept, and recomputed weighted training residual spread.
5. Compare three models on **identical eligible test games** per chronological holdout week: original **all-training** ridge, eligible-only ablation, and eligible+recency ridge. Store exact game IDs, date windows, training volume, margin MAE, signed home bias, straight-up correct/accuracy, and home-win selection share.
6. **No odds or player/medical data are synthesized**. The comparison is game-chronological retrospectively reconstructed advanced/PBP research. Historical PBP publication-before-decision is **not independently verified**. There are no authenticated as-of historical market spreads or O/U lines for grading the candidate. All outputs remain research-only.

### Reproduced GitHub Actions evaluation on the original October 24 training artifact
**Authoritative repeat:** [run 40200790213](https://github.com/The-Caves/cfb-model/actions/runs/40200790213) passed the candidate unit tests, retrieved the exact October 24 data-intake archive and produced a downloadable JSON report with all four fold IDs and metrics. The documented numbers below are from this independent cloud run, correcting an earlier local exploratory calculator that did not reproduce the exact CSV missing-data handling.

Using 248 held-out games across weeks beginning Sept 26, Oct 3, Oct 10 and Oct 17, on the same dual-profile-eligible holdout games:

| Variant | Margin MAE | Signed home overprediction | SU accuracy | Predicted home winner |
| --- | ---: | ---: | ---: | ---: |
| Original active (all prior games) | 16.52 | +10.85 | 58.9% | 97.2% |
| Eligible-only | 14.35 | +4.70 | 63.7% | 86.7% |
| Eligible + 14-day recency | **14.06** | **+3.79** | **64.1%** | **82.3%** |

These are exploratory, **not preregistered**, and are influenced by discovering home bias on the Oct 24 slate. Do not label them independently validated market performance or use as evidence of betting profitability. A subsequent clean prospective window and early-season sample composition/coverage audit are required.

### Milestone 1 promotion criteria — not yet met

- Target stays `PASS_UNVALIDATED` until consistent **genuinely prospective** improvement and authenticated pregame data/history are available.
- Candidate must outperform active and trivial home/market baselines on repeated strictly chronological, game-disjoint folds and future captured forecasts; benchmark margin MAE and signed bias alongside SU, ATS/O-U where real predecision lines exist.
- Assess both eligible-only and recency modifications independently. Do not silently drop early-season game predictions: only drop training examples without a reliable historical profile; abstain or use explicit priors in early-season *forecasting*.
- Verify no introduced home/away label inversion, train/test outcome leakage, duplicate games, player-injury lookahead, or changes to historical frozen records.
- Keep the full model identifier per prediction and grade by model version before promoting to public picks.

## Milestone 2: game-specific, verified QB-aware prediction features (open)

Current website card displays (i) prior-game leading passer, (ii) third-party QB1/QB2/QB3 depth rank and (iii) official conference OUT/QUESTIONABLE/AVAILABLE designations. **None independently confirms who will start**. The QB review/observation system is strict and national verified QB1 coverage remains inadequate.

Implementation requirements:
- Collect dated school/coach-confirmed starting QB1 (and any official updates) matching exact ESPN game ID, school/opponent, kickoff and prior-decision publication/capture; never promote a depth chart or season passer automatically.
- Record snap/participation-based actual QB replacement in a distinct **postgame-only** label, without allowing it into the pregame features.
- Create model inputs distinguishing `CONFIRMED`, `PROJECTED_UNCONFIRMED`, `UNKNOWN`, `INJURY_QUESTIONABLE` and `OUT`. Unknown must not be encoded as healthy or no effect.
- Learn any replacement-value effects from sufficiently large, timestamp-safe observations on future games, not manually selected point penalties. Include mobility and run/pass style where credible and available. 
- Run strict chronological ablations and retain a baseline fallback or PASS for missing/contradictory evidence. No active-model point effect without validated evidence.

## Milestone 3: calibrated, uncertainty-aware game totals (open)

Current 2026 ridge total forecast systematically misses both low games and explosive scoring extremes, including Rice–FAU 100 actual vs ~51.7 predicted. Prior-game pace, pressure/explosive rates, QB mobility/availability, red-zone/4th-down, non-offensive touchdowns, weather and matchup styles are candidates where **pregame timestamps and sufficient sample sizes** exist.

Implementation requirements:
- Start by measuring signed total bias and absolute errors by baseline total, team style, weather exposure, and time-of-season; compare market baseline where authentic observed.
- Estimate **score-total distributions/quantiles**, rather than only predicting a mean and pretending every 4-point O/U disagreement is equally reliable. Model heteroskedasticity and explosive scoring tails using training-only past-game residuals.
- Test incremental components separately: recency-corrected total mean; pace/explosive variance; verified weather/context; verified QB replacement/availability; non-offensive scoring volatility.
- Use pinched tail-mass diagnostics, distribution calibration, MAE and strictly source-time-safe market O/U selection performance, paired on identical games. Avoid training from outcomes observed after the target game's decision.
- Do not backfill a weather report, injury designation or revised sportsbook price obtained after the original game into a prior prediction.

## Sequence and operational convention

1. Finish CI evaluation of the isolated Milestone 1 candidate; audit side/per-fold effects, rerun on the latest actual ingestion, publish artifact and report.
2. Build Milestone 2 confirmed QB1 historical-observation dataset and trainability gate. Only then add learned QB effects to a separate candidate.
3. Build Milestone 3 totals distribution candidate and chronological validation. Compare 1+2+3 as one separate version only after individually measured ablations.
4. Promote **only explicitly approved, independently validated versions**. Update the dashboard to show model version and uncertainty; preserve existing immutable predictions, observations, lines and performance records.

**Operational CI note:** The first full intake integration found blank CSV features being interpreted as nonnumeric strings. Fixed `load_combined` to convert blank 2026 feature values to true missingness (`None`) and added regression tests; never substitute zero for an unknown profile. Full CI validation passed at [run 40200546532](https://github.com/The-Caves/cfb-model/actions/runs/40200546532) while the longer ingestion job proceeded independently. The dedicated evaluation [40200790213](https://github.com/The-Caves/cfb-model/actions/runs/40200790213) is the independently verified four-fold result. **The existing production forecast and website picks remain on V03**; this candidate has not been promoted.

# V05 robust CFB score challenger — November 2, 2026

## Why this exists
V03's severe directional home-selection bias led to quarantine; V04 independently fits an opponent-strength margin and offense/defense total but still has unexplained swings, outlier dependence and no explicitly graded recent-form contribution. V05 is **NOT a replacement**. All existing V03 frozen forecasts, V04 research displays, V04 market PASS rules, and independent player-stat projections remain unchanged.

## Implemented, evaluated and frozen
1. **Robust strength**: score-margin labels capped at 28 and weighted with 28-day half-life. Huber IRLS reduces residual outlier leverage. Home advantage stays 0–4.5 for nonneutral matchups and 0 for sourced neutral games.
2. **Independent score total**: two-sided offense/defense scoring model with recency weights, Huber loss and team-level shrinkage. No V03 predicted totals or sportsbook lines are training targets.
3. **Team trajectory**: 4 most recent actual 2026 scores, minimum 3. Mean residual form is shrunk toward zero using five virtual prior games; margin adjustment is bounded +/-4 per team, total +/-5. Missing form is not replaced with imaginary player news.
4. **Ablation contest**: V05 full versus V05 without form, without margin form, without total form, and V04. Fit only games before each Eastern football-day cutoff, then grade same ESPN IDs. Never choose weights based on the held-out results.
5. **Sparse-data warning**: a team with fewer than four past games is explicitly tagged as thin-history. In-sample residual scales are not a calibrated probability, credible interval or betting edge.
6. **Independent research lifecycle**: V05 source-matched scores are attached as shadow data, checked for score arithmetic and source provenance, then frozen in immutable pre-kickoff website archives; after independently observed finals, V05 and V04 are evaluated on the same archived games. No invented older V05 predictions.
7. **Safety checks**: deduplicate game IDs, strictly embargo same-day outcomes, reject future/negative/invalid scores and ambiguous neutral-site identity, preserve unchanged V03, avoid turning missing QB information into fake input.

## Initial retrospective matched benchmark (original October 31 score artifact)
These were **301 matched games, 5 weekly cutoffs**. Historical first-publication timestamps of all sources are not authenticated, so these are research metrics, not a leakage-certified betting backtest.

| Comparison | V04 | V05 full | V05 no form |
|---|---:|---:|---:|
| Correct winner rate | 66.78% | 65.45% | 64.78% |
| Margin MAE | 13.2053 | 13.3458 | 13.4119 |
| Total MAE | 13.4801 | 13.3216 | 13.4272 |
| Signed margin bias | +0.2302 | +0.1056 | +0.0740 |
| Signed total bias | +1.4397 | +0.2164 | +0.0648 |
| Fraction predicting home | 68.11% | 71.43% | 72.76% |

**Interpretation:** V05 reduces average total overprediction and slightly improves total MAE, but worsens winner accuracy and margin MAE. This does **not** justify promotion of V05, any ATS selection, or a betting claim. Even 301 retrospectively inspected games are not a pristine future holdout.

## Minimum promotion gates (predeclared before fresh prospective grades)
- Hold out **at least 250 new, independently finalized, previously frozen paired V04/V05 games across 5+ full weeks** after this version's first production archive. Compare exact same ESPN game IDs.
- Require stable improvement across weeks, not one weekend: at least **0.75-point total MAE reduction and 0.50-point margin MAE reduction** relative to the same-game V04, with no degradation beyond **1 percentage point** in straight-up accuracy.
- Confirm estimated home-selection bias stays controlled, and no one feature effect depends primarily on 1–2 outlier games.
- Demand 80% nominal intervals only if prospectively calibrated; current residual diagnostics are **not** intervals. ATS/O-U needs separately captured time-consistent lines and selective PASS-grade performance against the market baseline.
- No model swaps automatically. Human/code review, independent timestamp audit, test success, and documented rollback plan before any production switch.

These gates are intentionally challenging; the model can remain experimental indefinitely.

## Next experiments requiring evidence
- **QB substitution/transfer effect**: confirmed game-week starter, real QB1/QB2 identity and split, prior team tape, adjusted participation and OL context. No inferred downgrade from a passer-leader label.
- **Player replacement and pressure**: sourced OL/front-seven absence with prior-player snaps and pressure rates; avoid unverified injury news.
- **Opponent-matchup pressure / drive efficiency / red-zone / turnover luck**: paired two-sided PBP and boxscore data with auditable event semantics and past-only timestamps, separate ablations and null baselines.
- **Pace and simulation**: verified possession count, down/distance/field position and explosive rates; calibrate ATS/O-U probabilities against independent future results, not just raw scoring averages.
- **Market chronology**: preserve original opening-to-closing pregame quotes at capture, allow disagreement/PASS at a specific timestamp, and benchmark to favorite/market and no-bet policies.
- **Weather/travel**: verify kickoff-time forecast and actual venue, use small preseason-registered effects, and refuse unsourced backfills.

## Operating notes
All V05 labels must remain `SOURCE_OBSERVED_V05_SHADOW_SCORES` / `V05_ROBUST_RECENCY_FORM_SCORES_RESEARCH_ONLY`. The dashboard uses V04 for its existing visible scores; V05 appears only in an optional expanded research row. Original V03 archives are immutable and its ATS remains quarantined. The paired V05 historical score artifacts and tests run in `.github/workflows/cfb-v05-robust-research.yml`.

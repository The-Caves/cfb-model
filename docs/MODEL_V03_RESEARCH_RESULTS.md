# Model v0.3 corrected retrospective results — October 21, 2026

**Result: PROVISIONAL RESEARCH. NOT a market-validated or source-time-leakage-free backtest. NO model promotion.**

## Sources and reproducibility

- [GitHub Actions full 2026 intake 39691533017](https://github.com/The-Caves/cfb-model/actions/runs/39691533017): **validate = success**, **ingest = success**, including the corrected Eastern-game-date feature builder and the full v0.3 training/reporting stage.
- Game and advanced source manifest: 513 completed 2026 ESPN games, 510 with accepted two-sided 2026 SportsDataverse PBP/drive rows; the others retain explicit missing advanced features. Source advanced release was **retrieved 2026-10-21 at 23:10:09 UTC**, after the historical games used in these tests.
- Research artifact: `cfb-2026-data-39691533017`, containing `model_v03/weekly_pregame_features.csv`, `weekly_postgame_labels.csv`, `research_backtest.json` and `heldout_research_predictions.json`. GitHub artifacts have limited retention; the aggregate results and exact workflow reference are preserved in this document.
- [Unit tests](https://github.com/The-Caves/cfb-model/actions/runs/39691533017): 249 tests passed. Tests cover score and EPA target-game leakage, calendar-date cutoff crossing UTC midnight, complete source manifest schema, and separation of pregame features from postgame labels.
- Training/test methodology: fixed-penalty ridge predicting points **margin and total**; features and imputation fitted only within each weekly training period; 4 expanding walk-forward folds, 239 unique eligible test games. Full-season profile rows were not injected into earlier weeks.

## Four-fold 2026 retrospective comparison

Weighted by the number of games in each held-out fold (239 games in total):

| Metric | Score-only ridge | v0.3 with opponent-adjustment features | v0.3 without those adjustments |
| --- | ---: | ---: | ---: |
| Straight-up winners correct | 144 / 239 | 148 / 239 | 147 / 239 |
| Straight-up accuracy | **60.25%** | **61.92%** | **61.51%** |
| Margin mean absolute error, points (lower better) | 14.881 | **14.590** | 14.577 |
| Total mean absolute error, points (lower better) | 13.345 | 13.348 | **13.330** |
| Exploratory straight-up Brier score (lower better) | 0.23507 | 0.23033 | **0.22803** |

The v0.3 candidate won roughly **four more straight-up games than the score-only model** in this limited retrospective sample, and reduced margin MAE by about **0.29 points**. It **did not improve the total-points MAE**. The no-opponent-adjustment ablation had marginally better total MAE and Brier score than the full v0.3 candidate. The opponent adjustment therefore is **not proven beneficial** and should not be presumed useful.

### Per-fold straight-up accuracy

| Week starting | Train games | Test games | Score-only | v0.3 | No opponent adjustment |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sep 26, 2026 | 127 | 65 | 60.00% | 61.54% | 61.54% |
| Oct 3, 2026 | 192 | 64 | 62.50% | 68.75% | 67.19% |
| Oct 10, 2026 | 256 | 56 | 57.14% | **53.57%** | 55.36% |
| Oct 17, 2026 | 312 | 54 | 61.11% | 62.96% | 61.11% |

v0.3 underperformed the score-only baseline during the October 10 fold, and some margin and total improvements are inconsistent. Four folds are not sufficient to conclude reliable predictive superiority.

## Critical limitations preventing a production model

1. **Data availability is not historically verified.** The SportsDataverse PBP and drive parquet releases were retrieved and could have been revised after the historical games. Chronological splits prevent known game-score target leakage but do NOT establish what stats were genuinely available before an earlier kickoff. The report says `historical_pregame_source_provenance_verified=false`.
2. **No real FanDuel history.** No authenticated market spread/total/moneyline quotes, opening or closing movement, actual ATS or over/under grading, price-specific expected value or joint parlay probabilities were used.
3. **Incomplete feature groups.** No properly validated source-time QB starter changes, injury replacement-value adjustment, forecast-time weather weighting, special teams or 2025 training priors have entered this v0.3 candidate.
4. **Limited model selection evidence.** The fixed model structure is not promoted; comparative metrics are research diagnostics and not a reliable prospective hit-rate guarantee. No statistical uncertainty bands or rigorous external-era validation have been established.
5. **SU probability isn't calibrated.** The Gaussian residual-derived Brier metric is exploratory, not an established calibrated, market-anchored win probability. Even a correct SU direction does not establish a wager with positive expected value.

**Decision: keep `PASS_UNVALIDATED`; do NOT issue v0.3 betting picks or classify it as the promoted model.** Prioritize authenticated pregame source snapshots and a robust out-of-sample evaluation, then validate or reject the advanced feature groups with ablations and explicit PASS conditions.

This report contains only non-personal, aggregate metrics from public research data, not private credentials or sportsbook prices.

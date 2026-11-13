# V10R2 — V04-anchored possession Monte Carlo, November 13, 2026

## Execution and sources

- Reproducible code: `scripts/v10_possession_sim.py`, `scripts/v10_possession_backtest.py`, `scripts/v10_monte_carlo_convergence.py`. Integration/unit tests: `tests/test_v10_possession_sim.py`, `tests/test_possession_drive_ingest.py`.
- Passed full GitHub Actions run: [43491615567](https://github.com/The-Caves/cfb-model/actions/runs/43491615567). Retain research artifacts `v10r2-possession-v04-paired-backtest.json` and `v10r2-precision-convergence.json` from the `cfb-v10-source-verified-drives` upload for that run.
- **Fixed original source cohort** from successful run 43488854033, not repeatedly recollected: 693 completed 2026 games queried; 387 reconciled complete ESPN possession ledgers; 306 rejected. 379 identical V04 and simulated matchups graded; 40 historical matchups lacking appropriate earlier matched drive coverage withheld.
- 2,000 actual stochastic simulations per matchup for each V10 variant. V04 is a deterministic opponent-adjusted weekly-fitted scoring baseline. Historical game/PBP *first publication* timing at earlier dates is **not** authenticated, so this is a retrospective, not source-proven prospective backtest. Each simulated matchup trains only on games with earlier football dates and does not include today's or the target's outcome.
- Genuine archived pregame quotes are available on 156 ATS comparisons and 154 totals comparisons. Quoted lines are **not verified closing lines**. These ATS/OU scores are hypothetical directional selections, not original `PASS`-aware selections or placed bets.

## Which V04 and team-profile information flows into V10R2?

V04 scores come from team-strength and separate opponent-adjusted offense/defense scoring estimated at the historical weekly cutoff, including conservative home-field correction and recency. **V10R2 keeps those expected scores as an explicit, bounded scoring *prior inside each possession's TD and FG probabilities***, not a cosmetic adjustment to the final score.

V10R2 also builds a date-weighted (28-day half-life) *game-date* profile from earlier 2026 opponent game records: overall/pass/rush EPA, offensive pass/rush share, pass/rush success, pressure, sack, explosive-play frequency, third-down conversion, red-zone **play** success, plus offense giveaways and opponent defense takeaways on verified drives. League-smoothed, field-position-conditional drive outcomes and turnover-return TDs remain separate. A conservative optional turnover-regression treatment shrinks the predicted turnover rate toward the league when team-specific exposure is small. **The coefficients and prior scaling are experimental**, not fitted or calibrated to independent prospective results.

**Still missing** from this V10R2 scoring engine: verified expected starting QB and player replacement, injury availability, weather, fourth-down decisions, opponent OL/defensive-front personnel, kickoff/special-team expected fields, and down-and-distance/clock state. V04's older PBP source publication timing is not established. Do not assert all team profile dimensions automatically feed into probabilities; team scouting is broader than the currently scored feature set.

## Same-cohort comparison — 379 held-out games

| Forecast | SU correct | Margin MAE ↓ | Total MAE ↓ | Hypothetical ATS (156) | Hypothetical O/U (154) | Home winner Brier ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Frozen weekly V04 | **248/379 = 65.4%** | **12.9085** | **13.5322** | 70/156 = 44.9% | 62/154 = 40.3% | n/a |
| Empirical drive baseline | 218/379 = 57.5% | 14.5990 | 13.9839 | 72/156 = 46.2% | 60/154 = 39.0% | 0.25031 |
| Full matchup drive interactions | 216/379 = 57.0% | 14.6362 | 14.0443 | 69/156 = 44.2% | 69/154 = 44.8% | 0.25244 |
| Matchup + turnover-rate shrinkage | 219/379 = 57.8% | 14.4821 | 14.0052 | 74/156 = 47.4% | 68/154 = 44.2% | 0.24767 |
| **Matchup + turnover shrinkage + V04 scoring prior** | **230/379 = 60.7%** | **13.9010** | **14.0332** | **78/156 = 50.0%** | **69/154 = 44.8%** | **0.23488** |

Interpretation: V04-anchored possessions are substantially more plausible than unanchored drives, and the ATS directional hit rate increases on the quoted cohort. **V04 remains better at SU, margin MAE, and total MAE**, and 50% hypothetical ATS is not an independently established betting edge. We do not promote. More statistics or more trials alone cannot fix mis-specified conditional outcome probabilities. Brier for original V04 is unavailable because that baseline supplies no independently calibrated home-win probability.

## Monte Carlo count and convergence

The engine's **sampling error** is different from **model error**. Typical near-50% Bernoulli trial precision for an independently drawn win indicator is approximately ±4.4 percentage points at 500 draws, ±2.2 at 2,000, ±1.4 at 5,000, and ±1.0 at 10,000 (rough 95% binomial sampling intervals). If the underlying probability model is biased, 10,000 simulations merely estimate that biased probability more precisely.

In three actual 2026 case comparisons run with the same fixed historical feature cohort, 5,000-to-10,000-trial win-probability changes were:
- Tennessee vs Kentucky (Nov 7): 61.24% → 61.63% for Tennessee (difference 0.39 percentage point); the original V04 point margin was Tennessee +7.05, actual +28, showing the scoring margin remains a serious model miss.
- Kentucky vs LSU (Oct 10): 28.14% → 27.98% home Kentucky (difference 0.16 percentage point).
- Oklahoma vs Kentucky (Oct 17): 57.96% → 57.48% home Oklahoma (difference 0.48 percentage point).

**Operational research recommendation**: 2,000 draws suffice for rapid model-comparison screening, **5,000 default** for routine stable scenario reporting, and **10,000 for final pregame probabilities or close ATS/O-U cutoffs** (when sources and model are otherwise reliable). Measure convergence by independent seeds and decision stability; near-edge picks may still require PASS. Do not infer calibration from a narrower Monte Carlo confidence interval.

## Kentucky and follow-on validation priorities

Kentucky is a turnover-volatility example: its recent defensive takeaways should not be treated as certain future short-field possessions or offensive scoring. Against Tennessee on Nov 7, V04 projected Tennessee by about 7.1, V10's unanchored matchup simulation slightly favored Kentucky, and V10R2's V04-anchored simulation favored Tennessee by about 5.9. Tennessee actually won by 28. **The turnover mechanism and regression help identify conditional downside, but did not solve that matchup**.

Next research milestones, in order: (1) source-verified complete pregame player/QB and injury contexts and real historic event availability timestamps; (2) field-position transition/possession-count/defensive return calibration and actual red-zone TD/trips, not just play success; (3) opponent-specific OL/pass-rush matchup and pace/clock/4th-down decisions; (4) fit and calibrate bounded coefficients only on older weeks; (5) freeze outputs before upcoming kickoffs and compare prospectively on identical game IDs versus V04, market and simple baselines, including Brier/log loss and graded/pass thresholds. **No hindsight-based promotion**; V04 and permanent historical grades remain unchanged.

# V12R3 — source-frozen opponent pace, actual possession starting field and red-zone trip conversion

**Executed November 13, 2026** on research branch `research/v12-opponent-conditioned-possessions` of **The-Caves/cfb-model**, draft PR #63. V04 remains the published, unmodified champion. **No candidate was promoted; no historical picks were rewritten.**

## Method and what changes / does not change

Built `scripts/v12r3_possession_context.py`, which accepts only the fixed 387 source-reconciled 2026 ESPN possession ledgers and computes contexts from prior completed **football game dates strictly earlier than the original V04 weekly cutoff**. No same-week results are used in either team profile. A strict source game/drive-count check ties the context to the unchanged earlier-week V11 game simulation fit, and the reference V11+historical-pace forecast is re-simulated for each of 377 cases with **exact numerical agreement** to the previously archived V12R2 output or the backtest fails. Fixed coefficients and league shrinkage were chosen without searching the held-out scores.

The three independently testable changes are:
1. **Opponent role tempo**: each team's actual earlier offensive possessions and defensive possessions faced, weighted by 28-day recency and shrunk toward prior-league average. Use opponent-specific offense versus defense opportunities in the total per-team possession expectation; sampling variation still comes from **real earlier games**, not a fixed arbitrary jitter.
2. **Field-position transitions**: use **actual** starting-yardlines after prior TD, FG, turnover, non-scoring possession and defensive return TD, plus earlier opening-possession starts, with bounded small receiver-team weights and league fallbacks. Defensive-return touchdowns properly hand kickoff possession back to the original offense. These are observed transition samples; do not claim the simulator independently knows every punt, clock, onside kick, penalty or special teams scenario.
3. **Red-zone trips and conversion**: among real drives that actually reached the red zone (not red-zone *plays*), evaluate offense TD conversion versus the opposing defense's allowed trips and conditional FG rates. League-shrink individual small samples and apply only a deliberately small normalized scoring-odds correction for drives that **start near the opponent end**, keeping turnover risk separate. Avoid claiming this is a full play-by-play or all-field trip-entry model.

All variants use original frozen V04 score strengths and V11 dated EPA, field/matchup source restrictions and 2,000 Monte Carlo draws with identical reproducible seed construction; **no QB/injury/weather effect is backfilled from later observations**. Historical upstream 2026 PBP *first publication* at original decision time remains **unverified**, so dates alone do not establish real-time pregame availability.

## Completed validation

- [V12R3 CI + 377-game, seven-week matched backtest](https://github.com/The-Caves/cfb-model/actions/runs/43511454998): **SUCCESS**, source/cutoff identity gates, V11 no-change tests, and ablation grading.
- [Original V12R2 compatibility on the same research revision](https://github.com/The-Caves/cfb-model/actions/runs/43511454864): **SUCCESS**.
- [Full CFB 2026 Data Intake unit checks](https://github.com/The-Caves/cfb-model/actions/runs/43511466862): **SUCCESS**.
- Fixed, pre-existing 2026 ESPN original source and original 387 verified drives; no historical source re-query or invented betting lines; 377 game IDs matched, 156 spread quotes, 154 totals quotes.

| Same 377 historical games | SU | Margin MAE ↓ | Total MAE ↓ | Total CRPS ↓ | Winner Brier ↓ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Published V04 score champion | **246/377** | **12.9266** | **13.5414** | unavailable | unavailable |
| V11 original scoring and original fixed pace | 234/377 | 13.9234 | 14.1147 | 9.90940 | 0.233916 |
| **V11 + earlier-game learned pace** | 232/377 | **13.9023** | **13.8145** | **9.64680** | **0.233372** |
| V11 + opponent-role pace | 232/377 | 13.9057 | 13.8775 | 9.67753 | 0.233672 |
| V11 + learned pace + event field position | 235/377 | 13.9150 | 13.8232 | 9.65791 | 0.234681 |
| V11 + learned pace + RZ-trip conversion | 233/377 | 13.9020 | 13.8153 | 9.64744 | 0.233329 |
| V11 + learned pace + field + RZ | 235/377 | 13.9134 | 13.8233 | 9.65826 | 0.234706 |
| V11 + opponent pace + field + RZ | 233/377 | 13.9279 | 13.8736 | 9.68197 | 0.234662 |

Values highlighted in the V11+learned-pace row are the best V11-family historical total MAE/CRPS in **this R3 specific ablation**, not the best across all prior V12 experiments: earlier V12 empirical+pace had total CRPS 9.61917 but worse SU/margin calibration.

### Probability diagnostics and directional lines

| Variant | ATS directions on 156 | O/U directions on 154 | Total-over Brier ↓ | Nominal 80% total interval observed coverage |
| --- | ---: | ---: | ---: | ---: |
| V11 + learned pace | 73/156 | 63/154 | 0.271198 | 78.25% |
| V11 + opponent-role pace | 73/156 | 64/154 | 0.272482 | 77.45% |
| V11 + event field positions | 71/156 | 61/154 | 0.271074 | 78.25% |
| V11 + RZ-trip conversion | 73/156 | 63/154 | 0.271260 | 78.25% |
| V11 + event field + RZ | 71/156 | 61/154 | 0.270962 | 78.25% |
| V11 + opponent-role pace + field + RZ | 72/156 | 62/154 | 0.271953 | 77.98% |

The red-zone correction's winner Brier shift (0.233372 -> 0.233329) is **0.000043**: insufficient on seven previously studied cutoffs. Field transitions gained **three directional SU wins** versus V11+pace but worsened margin CRPS, winner Brier and overall ATS decisions; this could be Monte Carlo and cohort-specific noise, **not** demonstrated improvement. Opponent-role tempo worsened total CRPS and total MAE compared with simpler earlier-game learned pace.

### Per-original-week total CRPS (lower is better)

| Frozen 2026 weekly cutoff | Games | V11+learned pace | Opponent-role pace | + field (normal pace) | + red-zone (normal pace) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sep 26 | 43 | 9.3553 | 9.4583 | 9.4204 | 9.3555 |
| Oct 03 | 58 | 10.4727 | 10.5346 | 10.4478 | 10.4727 |
| Oct 10 | 52 | 8.5220 | 8.5695 | 8.5298 | 8.5234 |
| Oct 17 | 59 | 9.4092 | 9.3507 | 9.3755 | 9.4107 |
| Oct 24 | 49 | 10.7602 | 10.7670 | 10.7877 | 10.7603 |
| Oct 31 | 59 | 8.4915 | 8.6517 | 8.4818 | 8.4942 |
| Nov 07 | 57 | 10.5370 | 10.4452 | 10.6010 | 10.5355 |

No new signal consistently beats the V11+learned-pace total distributions. Prior weeks have been *repeatedly examined* across V09–V12R3, so retrospective gains are **not a new independent test**, even though game-time labels are cut off correctly. Score accuracy on the 377-game subset is below V04; sparse historical market quote subsets do **not** establish a profitable betting edge.

## Decision / experiment register

- **Keep V04 unchanged as the champion**, continue keeping full archived decision/performance grades intact.
- **Freeze V11 + historical learned pace** as the most coherent alternate total-score distribution candidate: useful total-score CRPS improvement over V11 original, but not independently validated.
- **Hold opponent-role tempo and event field-position variants for future source-frozen prospective testing**. Do not add them as mandatory production features because current evidence is inconsistent.
- **Hold RZ-trip conversion scoring adjustment**: historical source data allow genuine trip evidence, but this crude effect is close to zero; to learn more, need truly point-in-time opponent-conditioned red-zone *entry* and *conversion* state with down/distance, clock, field position, fourth-down/punt/FG decisions. Do not make bigger heuristic weights from this report.
- **Next independent milestone:** deploy a research shadow alongside V04 for future games, freeze predictions before kickoff and archive their time-stamped external source observations. Accumulate sufficient untouched future weekly cohorts for predeclared winner Brier, margin/total CRPS, ATS/total Brier/log-loss, interval coverage and PASS/edge calibration before considering promotion. Incorporate real source-proven expected starter QB, personnel availability and weather forecast data only after verified first-publication and first-observation times, with missingness preserved.

Full JSON per-game/weekly report is uploaded as `cfb-v12r3-observed-possession-ablation` in the successful run above; reproducible invocation: `python -m scripts.v12r3_possession_backtest --previous [original successful V12R2 report] --drives [fixed source-matched drive ledger] --games [original frozen games CSV] --advanced [original advanced CSV] --manifest [original 2026 source manifest] --output [result path] --trials 2000`.

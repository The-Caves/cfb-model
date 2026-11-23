# V12R2 — chronologically trained opponent drive hazards and learned possession pace

**November 13, 2026 — executed research.** Repo: `The-Caves/cfb-model`, draft PR #63, branch `research/v12-opponent-conditioned-possessions`. **V04 is still the production champion. No V12/V12R2 variant was promoted. No original archived picks or grades were changed.**

## Why this experiment

V12's initial heuristic red-zone-trip and turnover-field-position model was worse than V04/V11 on winners, margins, ATS and winner probabilities. The question was whether genuinely learning conditional touchdown, FG, turnover and red-zone-trip rates would help — without retrospectively introducing future outcomes — and whether observed possession pace should replace fixed simulator jitter.

## Implementation (research only)

- `scripts/v12_regularized_hazards.py`: seven source-observed Bernoulli hazards (reaching red zone; then TD, FG and turnover separately conditional on *reached* vs *did not reach* the red zone) fitted via damped ridge-penalized likelihood. Features include actual drive starting zone, offense and opposing defense team, and optional **original archived earlier-week V04** team score and dated opponent-adjusted EPA. Missing original forecast data are absent, **never replaced with today's historical reconstructed profile**. Fixed shrinkage weights and 18 optimization passes were set before examining this experiment's outcomes; no per-week target optimization or retrospective outcome-feature leakage.
- All fitted labels require drive game dates **strictly before the original 2026 V04 weekly cutoff**; the fit is cached once per week and reused across that week's 377-case evaluation cohort. Same-week labels cannot enter another game's training.
- `pace_profile` derives an earlier-week, shrinkage-adjusted distribution of real drives per team/game from source-verified ledgers. It replaces the simulator's original fixed {-2,-1,0,1,2} variation with observed historical fluctuations, not an assumed number of possession opportunities.
- Ablations isolate (a) trained hazards with legacy pace, (b) trained hazards with observed pace, (c) original empirical V12 hazards with observed pace, and (d) **unchanged V11 drive-scoring hazards plus observed pace**. Seed and source matchups are held fixed; original V11 seeded forecasts are independently replayed and rejected on any mismatch.
- `tests/test_v12_regularized_hazards.py` enforces no future/same-week labels, input identity, probability normalization, deterministic replay, learned-pace evidence, and zero promotion. Existing V04/V10/V11 tests remain in CI.
- Original source first-publication timestamps for past 2026 ESPN game/PBP data are **not authenticated**. Therefore this is retrospective source-date research, *not verified pregame performance*. Original QB/injury/weather statuses are not backfilled or given speculative scored effects.

### Executed source-frozen validation

[GitHub Actions #43507919303](https://github.com/The-Caves/cfb-model/actions/runs/43507919303) **PASSED** both the V12R2 gates and 377-game 2,000-trial matched cohort. [CFB 2026 Data Intake #43507932525](https://github.com/The-Caves/cfb-model/actions/runs/43507932525) **PASSED** the full repository tests on the corrected research branch. The historical source and quoted sportsbook prices are the same original frozen V11 experiment inputs. Both assessments ran on the research branch; `main` is unchanged.

| Variant | Winner correct | Margin MAE ↓ | Total MAE ↓ | ATS directions (156) | O/U directions (154) | Winner Brier ↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Frozen original V04 | **246/377** | **12.9266** | **13.5414** | 70/156 | 62/154 | unavailable |
| V11 dated EPA and original pace | 234/377 | 13.9234 | 14.1147 | 75/156 | 68/154 | 0.23392 |
| **V11 hazards + learned pace** | 232/377 | 13.9023 | 13.8145 | 73/156 | 63/154 | **0.23337** |
| V12 empirical red-zone original pace | 220/377 | 14.1036 | 14.0368 | 74/156 | 66/154 | 0.23842 |
| V12 empirical red-zone + learned pace | 224/377 | 14.0975 | 13.7815 | **77/156** | 65/154 | 0.23866 |
| V12R2 trained red-zone hazards alone | 218/377 | 14.2962 | 14.1597 | 74/156 | **70/154** | 0.24104 |
| V12R2 trained red-zone + learned pace | 220/377 | 14.3022 | 13.7985 | 74/156 | 66/154 | 0.24089 |

These quoted line directions are hypothetical evaluations, **not actual bets or evidence of profitability**. Price samples are only 156 ATS and 154 O/U and are not all verified closing lines.

### Same-cohort probability and distribution calibration

| Version | Total CRPS ↓ | Total P10–P90 interval actual coverage (nominal 80%) | Total-over Brier ↓ | Winner Brier ↓ |
| --- | ---: | ---: | ---: | ---: |
| V11 original | 9.90940 | 72.68% | 0.280446 | 0.233916 |
| **V11 + learned pace** | 9.64680 | **78.25%** | 0.271198 | **0.233372** |
| V12 empirical, original pace | 9.87700 | 73.74% | 0.279063 | 0.238422 |
| V12 empirical + learned pace | **9.61917** | **78.25%** | **0.269597** | 0.238665 |
| V12R2 trained, original pace | 10.02820 | 74.27% | 0.286272 | 0.241044 |
| V12R2 trained + learned pace | 9.71724 | 79.05% | 0.275892 | 0.240893 |

**Interpretation:** empirical pace is the strongest isolated improvement; training the detailed red-zone conversion hazards has not yet helped. The V11+pace ablation improves totals MAE/CRPS, total-over Brier and slightly improves home-win Brier, but loses two winner directions, two ATS directions and five O/U directions. The V12-empirical+pace ablation has even better totals CRPS/Brier but weaker SU/margin accuracy. None is a replacement for V04.

### Weekly stability audit: total MAE

| Original frozen weekly cutoff | Games | V11 original | V11 + learned pace | V12 empirical + learned pace |
| --- | ---: | ---: | ---: | ---: |
| Sep 26 | 43 | 14.1333 | 13.0737 | 13.0210 |
| Oct 03 | 58 | 15.0691 | 15.3155 | 15.0885 |
| Oct 10 | 52 | 12.2584 | 12.0180 | 12.1368 |
| Oct 17 | 59 | 13.8480 | 13.2210 | 13.2824 |
| Oct 24 | 49 | 15.6303 | 15.6072 | 15.6237 |
| Oct 31 | 59 | 12.6306 | 12.4807 | 12.4744 |
| Nov 07 | 57 | 15.3323 | 14.9389 | 14.8113 |

The V11+pace total CRPS improves in **6/7 historical weeks**, and total MAE improves in 6/7 as well. An exploratory 10,000-replicate **seven-week-block bootstrap** on this already-examined historical cohort places its total CRPS mean difference versus V11 near **-0.263** (resampled 95% interval **[-0.455, -0.080]**). This is a measure of observed internal consistency only: **it does not repair repeated model-selection exposure, external source-publication uncertainty, or small effective independent-week sample size**. Do not use this interval as certification of a future edge.

## What to retain / reject

**Retain as nonpromoted challenger:** learned historical possession pace with the proven V11 scoring hazards, especially for total-distribution evaluation. Store the empirical V12+pace alternative for totals-only independent comparisons. **Reject as a scored challenger for now:** newly fitted V12R2 conditional red-zone hazards; they worsened most primary metrics and were not rescued by observed pace.

**Next independent test plan:** freeze both challenger definitions/hyperparameters and original V04/V11 controls **before** later games, then collect actual timestamped pregame source evidence and forecasts. Grade SU, margin/total MAE, CRPS, 80% interval coverage, ATS/O-U Brier/log loss, segment stability and PASS discipline with no post-kick changes. Expand source-verified historical seasons only if genuine point-in-time availability can be established, particularly starter QB, OL/front injuries, real pregame weather forecasts, possession pace, and original opening/closing prices. Do **not** repeatedly tune these weights against the same seven 2026 evaluation weeks and label it independent validation.

Artifacts: `cfb-v12-opponent-rz-turnover-research` on run #43507919303 contains complete per-game scores, model seeds, prior-game IDs, distributions, graded calibration, and weekly tables. Source documentation: `docs/V12_OPPONENT_REDZONE_TURNOVER_2026.md`.

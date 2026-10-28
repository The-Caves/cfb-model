# 2026 CFB — Recency and Opponent-Latent Shadow Model

## Status

Four prospective margin-forecast versions are now wired into the existing Data Intake workflow for research-only testing. The live Step3G V03 forecast, previous archived picks, website and totals are unchanged. Historical 2026 SportsDataverse advanced/PBP source publication time is not independently authenticated. All status remains PASS_UNVALIDATED; no betting recommendation or model promotion is implied.

## Four model versions

| Version | Research hypothesis | Data gate |
| --- | --- | --- |
| active_v03 | The exact frozen production research V03 margin and total | Original archived forecast must pass checksum and timestamp checks |
| recency_14d | Recent dual-prior-profile games deserve higher weights; home bias can be reduced | At least 90 earlier dual-prior-profile games; 14-day half-life |
| latent_only | A time-varying, opponent-conditioned team-strength score adds predictive information | Each target team has at least two previous 2026 games; 90 earlier valid latent training rows |
| recency_plus_latent | The two improvements provide distinct complementary signal | Identical as-of latent evidence plus 14-day weighted past-only model |

The opponent latent filter updates only AFTER an entire Eastern-calendar football date finishes. The filter's variances are heuristic, not validated Bayesian uncertainty. The model's original numeric game total is reused in every candidate; this experiment cannot improve total scoring predictions by construction.

## Matched-training cohort control for incremental latent value

In addition to the four headline versions, each eligible future matchup freezes a research-only recency control trained on the **identical latent-eligible historical game cohort** as recency_plus_latent, but excluding the latent inputs. The resulting shadow report records the paired margin errors and the incremental MAE delta of combined minus matched-cohort recency. This avoids confusing a smaller training set with actual added latent predictive power. The diagnostic is not promoted to a fifth public betting model. Missing latent evidence produces an explicit PASS.

## Prospective operation and archive

* scripts/model_shadow_forecast.py requires the immutable Step3G V03 record produced in the same GitHub run, matches its complete original training IDs and feature SHA, and uses strictly earlier completed football dates for every candidate fit. It runs within 20 minutes of original forecast observation; no postkickoff or invented historical shadow predictions are accepted.
* The exact four-model forecast, explicit missing-evidence PASS reasons and associated original V03 row hash are durably stored at context-state/research_2026/shadow_forecasts/YYYY/MM/DD/run-ID.json.gz with the append-only shadow_forecast_index.json. The workflow also uploads cfb-shadow-forecast-ID JSON artifacts for review.
* scripts/model_shadow_grade.py uses independently archived final-score Step3G grades, joins by exact selected original V03 run, matching game ID, original forecast bundle SHA and individual frozen row SHA, and requires a 24–72-hour original shadow lead. It does not choose a different historical prediction or retrospectively invent one.
* The report contains same-game V03 margin error, candidate margin error, win accuracy, signed home-margin bias, comparable weekly deltas, and a four-way matched cohort. It archives immutable reports at context-state/research_2026/shadow_grade_reports/YYYY/MM/DD/run-ID.json.gz and publishes cfb-shadow-grades-ID artifacts.
* Every report explicitly retains model_promoted false and PASS_UNVALIDATED. The website continues using V03 until independently justified promotion.

## Test and promotion criteria

Validation must verify clean chronology and no same-day label leakage, exact source fingerprint equality, no future or postkickoff forecasts, correct imputation from earlier training only, unknown teams returning PASS rather than zero ratings, strict same-matchup comparison, and immutable grading evidence.

Before promoting a candidate, target 100+ **fresh, genuinely prospective four-way matched games** across multiple weeks; examine paired margin MAE, signed home bias, straight-up winner accuracy, weekly consistency, tail risk and prospective confidence intervals. Compare against authentic predecision market lines separately, not fabricated opening/closing prices. Assess whether the combined candidate adds value beyond recency alone instead of using the same exploratory folds for promotion. This 100-game threshold is an initial target, not proof of statistical significance.

## Source and model limitations

Missing official starting-QB evidence, injuries and player replacement values are NOT inferred or assigned subjective point penalties in these experiments. Historical PBP input snapshots may have been retrospectively revised. The shadow models estimate **margin only**, not improved game totals or validated ATS/O-U probabilities. Do not declare a live promotion based solely on retrospective backtests.

CI instructions: check the CFB 2026 Data Intake run's validation job, then the two steps named 'Freeze four independent pregame margin shadow forecasts' and 'Grade archived shadow forecasts against exact selected V03 grades'. GitHub artifact names and the context-state indexes provide independent audit trails.

## October 28 official-source registry robustness

The first full shadow-intake run 40691904266 passed 679 unit tests and creative-model research, but stopped in the pre-shadow QB worklist on `ValueError: Team missing national source registry`. The upcoming ESPN schedule can contain schools absent from our 138-school FBS official-source registry. The worklist now **retains** both team/game slots, explicitly marks outside-registry schools `NOT_IN_138_REGISTRY_SOURCE_UNKNOWN`, and leaves all publisher URLs, personnel evidence and QB starter confidence **unverified**. It reports their number and still rejects unknown future curated gameweek claims. An outside-registry slot is not automatically classified as FCS, healthy or a confirmed lineup. This repair preserves coverage accountability and lets intake continue to the prospective shadow stages.

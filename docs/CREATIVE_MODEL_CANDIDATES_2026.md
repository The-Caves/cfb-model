# Creative model candidate — all six proposed experiments

**Status: exploratory research, not deployed to live picks.** The baseline remains V03. Scores, observations and market comparisons previously archived are never rewritten.

These research experiments are implemented in `scripts/creative_model_features.py` and `scripts/creative_model_research.py`, and can be rerun via `CFB 2026 Data Intake` with automated unit tests. They use completed 2026 games and date-exclusive histories, but historically released SportsDataverse play-by-play data may have been revised: **the original historical availability instant cannot be authenticated**, so results are NOT prospective betting evidence.

| Proposed idea | Implementation | Important limitation |
| --- | --- | --- |
| Predict possessions before score | Two-sided 2026 drive counts and prior team score/drive generate a direct score proxy. Also test ridge with drive-context features. | Scores per drive include all points, not isolated offense; prior drive counts are mandatory. No independent possession simulation. |
| Deserved vs observed performance | Historical difference of scoreboard scoring per scrimmage play and EPA/play, plus play-weighted field-position differential. | This is a diagnostic residual and **not verified turnover luck**, nor true drive-start field position. |
| Matchup-specific vulnerability | Prior pressure/sack rates multiplied by pass tendency and compared between teams. Optional independently verified OL absences × pressure stress in `verified_injury_pressure_interaction`. | No injury adjustment in forecasts until usable paired evidence passes gates. |
| Drive resilience & explosives | Prior third/fourth-down success, explosion dependence, pressure-vs-conversion rates, with matchup deltas. | Success does not by itself identify recovery from second-and-long; more PBP attribution is needed. |
| Changing team strength | Exponentially decayed prior margin/EPA and season-form deviations, plus an opponent-conditioned latent team-strength Kalman-style filter updated **only after each complete football date**. | Bayesian-style variance is heuristic, not empirically calibrated; official historical release times remain unverified. |
| Predict range of totals/margins | A past-only temporal fit/calibration split produces nominal 10th/90th residual quantiles, optionally stratified by prior explosion/possession proxy. | Coverage is measured on heldout weeks; not a certified calibrated distribution. |
| Ensemble | Predeclared 35% V03, 25% recency-home candidate, 20% creative features, 20% possession score proxy. Unavailable components drop out and remaining weights renormalize. | Weights fixed ahead of testing; **not** learned from or tuned to heldout 2026 results. |

**Validation:** test games and training games disjoint by ESPN game ID and football date, same evaluated games in every comparable variant, 90 minimum past games, missing variables imputed from past training only. Reports include margin MAE, total MAE, signed home bias, winner accuracy, games, and (baseline) nominal 80%-interval empirical coverage. Early/late PBP publication timings and authentic historical market data remain blocked. No candidate automatically promotes.

**Remaining work before any promotion:** (1) source-time-authenticate independent historical observations, (2) acquire enough genuinely observed prospective games and matched market timestamps, (3) fit individual replacement/participation effects once full reports improve, (4) improve turnover, drive-start, and game-state attribution, (5) validate a fully calibrated possession-level simulator/state-space model and market-aware ensemble out of sample.

## Automated execution

`.github/workflows/cfb-data-intake.yml` now runs this research module with real 2026 data on every scheduled or explicitly triggered ingestion, after it completes the normal advanced PBP ingest and earlier matchup ablations. It uploads `cfb-creative-candidates-<run-id>` with every held-out fold's exact train/test ESPN game IDs, skipped components, candidate metrics and baseline comparisons. Failure to load required real data fails the research job (it cannot silently invent a passing result). Unit tests run in the validation job first. This module never reads or rewrites pre-existing immutable model forecasts.

## Game-by-game audit files

Every full intake additionally writes \`creative-candidate-predictions.json\` with the held-out forecast margin and total beside the observed final, keyed by exact ESPN game ID and model version. It is research-only, not historical sportsbook quotes. Unit tests exercise every measured experimental variant and confirm that changing held-out outcomes does not alter pregame forecasts.

## Injury/OL-versus-pressure candidate (strict as-of)

\`scripts/multifactor_walkforward.py\` now has a separate \`plus_injury_pressure_interaction\` variant. It combines verified as-of OL and QB absence differentials from \`personnel_replacement_capture.py\` with the contemporaneous frozen team \`pressure_form\` proxy. It never applies a manual point penalty; coefficients would be fit only on prior observed completed games. If either school's report is missing, both interaction features stay null and the evaluation variant is skipped when there is no training variation. New tests cover verified, partial and post-cutoff evidence.

This connects injury context to a future **model candidate**, not to the live dashboard. The absence of official report coverage still prevents learning any actual injury coefficient.

## October 28 automated-intake time rollover repair

The first overnight scheduled [Data Intake run 40619856776](https://github.com/The-Caves/cfb-model/actions/runs/40619856776) successfully ran the creative research model against completed 2026 games and produced an actual per-game prediction artifact, but **the later QB-source review worklist failed** because it treated the now-completed October 27 games in the curated school-source archive as future unmatched fixtures. The worklist now uses its original `queue.asof_utc` to exclude already-started school/game source rows from the future queue; their provenance remains in the historical source registry, and unmatched **future** fixtures still trigger an error. A regression test covers both cases. No QB starter, injury status or betting clearance is inferred. The candidate research job still does not update live picks.

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

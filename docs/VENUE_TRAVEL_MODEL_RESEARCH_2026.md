# 2026 Opponent-neutral strength, home-field and travel research — October 29

**Status:** Research-only experimental model and real-data evaluation. **No public V03 or saved forecast was changed.** No empirical home/travel adjustment is validated for the website yet. Models keep `PASS_UNVALIDATED`.

## Why we changed the architecture

The active V03 has an intercept learned from an incomplete set of home/away aggregate team features, not a separable home advantage. A previous October 24 audit observed an extreme home lean. We created a distinct model:

```
predicted HOME margin = (regularized opponent-adjusted NEUTRAL home team rating
                         - neutral away team rating)
                      + venue adjustment (0 on neutral fields; regularized
                        around 2.5 points on home fields)
                      + separate learned travel/rest effect IF training
                        evidence is sufficient
```

Opponent ratings are regularized on earlier game-score margins and observed opponents, using a 21-day half-life and no free intercept. Team ratings have a distinct penalty so they are not mistaken for home-field advantage. Home venue is bounded to 0–4.5 points, based on a **2.5-point prior**, not assumed to be exactly worth 3 at every school. This baseline does **not** add another 2.5 points to V03: it replaces the V03 margin mechanism in a separate candidate. Historic venue is score/game-identity checked.

The first experimental penalty (55) forced most neutral-field rating differences near zero, causing nearly every contest to be projected as a home win even after average error bias fell. The research penalty was changed to 6 **after seeing the exploratory error**, and is therefore not an independent/preregistered hyperparameter choice. Further prospective validation is mandatory.

## Distinct travel signals and data provenance

- Location source: ESPN game venue city, state's/country's verified city centroid via Open-Meteo Geocoding/GeoNames, not actual stadium coordinates.
- City IANA time zones are accepted only from exact GeoNames ID/coordinates/country matches. October 29 snapshot enrichment checked 101 old cached cities, accepted 96 and left 5 unresolved; no mapping by state or assuming Pacific/Eastern.
- Daylight-saving-aware travel direction `EAST` / `WEST` / `NO_TIMEZONE_SHIFT`, destination-local body-clock kickoff for origin team, absolute time-zone shift, approximate great-circle distance (NOT flight itinerary), rest days and neutral-site flag.
- Historical travel home base uses **at least two previously observed nonneutral home games** per school before the match; prior games from the current date/future cannot enter. Original historical geocoding lookup timestamps were not verified as pregame, and there are no observations of arrival schedules, circadian acclimation or actual flight miles.
- Missing travel observations remain `UNKNOWN`, never a zero-mile trip, zero time zones or zero travel effect imputation.
- Travel coefficients are fitted separately from team ratings and venue effects with shrinkage and at least **80** earlier fully sourced game observations. A no-travel control is fit on the **identical historical travel-eligible cohort**, so a small training set cannot falsely create a travel lift. Current model is research-only, never the scoring engine on the live site.

## October 29 real-data heldout validation

**Source:** [GitHub Actions Research Evaluation run 40940074005](https://github.com/The-Caves/cfb-model/actions/runs/40940074005), using the frozen `cfb-2026-data-40916372983` research snapshot, 570 completed scoreboard games, 5 Eastern-calendar walk-forward folds, **286 identical evaluated game IDs**.

| Variant | Margin MAE (lower better) | Signed home overprediction | Straight-up accuracy | Home winner selected |
| --- | ---: | ---: | ---: | ---: |
| V03 reference | 15.6922 | +10.6741 | 59.79% | 97.55% |
| Dual-profile recency14d | **13.3559** | +3.8240 | 63.29% | 80.77% |
| Opponent-neutral rating + venue | 13.4746 | **+0.6726** | **63.29%** | **79.37%** |

The neutral-rating candidate improves average home bias and reduces home-winner preference versus V03, while recency still has slightly better margin MAE. It does not yet deserve promotion. This comparison is retrospective; the original PBP release's historical publication timestamp is not authenticated, and the research tuning followed the observed home-bias problem.

The real historical-source builder found **132 complete travel-game observations** among 570 historical games using 96 retrieved city time zones. Only the final two folds had enough earlier travel training examples to evaluate travel: **22 and 19 held-out games** (total 41). In those folds:
- 22 games, 81 training trips: travel MAE 11.7292 vs identical-training no-travel MAE 11.7886.
- 19 games, 109 training trips: travel MAE 10.3109 vs identical-training no-travel MAE 10.8040.

These tiny differences on 41 covered games do NOT prove that eastward trips, long distances or body-clock kickoff have a stable causal effect. They are susceptible to selection bias and were explored after inspecting earlier model problems. No predetermined travel point penalty or winner change is automatically triggered on the public site.

## Implementation and audit paths

- `scripts/game_context.py`, `scripts/ingest_game_context.py`: destination zone, origin zone, time-zone shifts, direction, body-clock kickoff and rest context (source and missingness retained).
- `scripts/city_timezone_refresh.py`: optional bounded and exact-ID timezone evidence refresh; never guesses a zone.
- `scripts/venue_travel_history.py`: reconstructs historical venue/travel from archived ESPN event identities with strictly past-only school home-base inference; results tagged research-only.
- `scripts/venue_travel_candidate.py`: fits neutral opponent ratings and venue effect, optional evidence-gated travel regression, exact paired same-week V03 and recency tests, source checks, and trained-on-identical-cohort travel ablation.
- `tests/test_game_context.py`, `tests/test_city_timezone_refresh.py`, `tests/test_venue_travel_history.py`, `tests/test_venue_travel_candidate.py`: deterministic and missingness/leakage/venue checks.
- `.github/workflows/cfb-venue-travel-eval.yml` publishes complete paired forecasts and QC data. `.github/workflows/cfb-data-intake.yml` runs the venue/travel research alongside scheduled ingestion (only after context collection).

## Gate before live usage

1. Verify actual travel city/time-zone coverage in **current** pregame forecast snapshots for the upcoming weeks.
2. Freeze the new venue and travel predictions prospectively before kickoff and grade on the **same exact future games** as V03 and recency, including effect direction and uncertainty, with no postgame rebuilding.
3. Require repeated and sufficiently sized independent prospective improvements in margin MAE, straight-up winner accuracy, signed home bias, ATS against timestamped predecision market lines, and no unacceptable tail regressions. Compare a neutral-only rating, venue-only, distance-only, zone-only and full model separately.
4. Study air travel direction, weekend kickoff body-clock time, acclimation/rest and neutral sites. Do not assume long travel always costs points.
5. Only then consider incorporating a robust venue component or selected travel coefficients into the live score predictions. Preserve model versions, all previous frozen results, and site V03 until the gate passes.

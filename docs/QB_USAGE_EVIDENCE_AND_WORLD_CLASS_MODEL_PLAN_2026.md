# CFB 2026: QB identity recovery and long-run model development

## Problem and operational meaning

The product needs to *model the quarterback who is likely to play*, not falsely claim an official confirmation. The actual live V03 scoring model still has only 14 aggregate team features. A separate QB-conditional forecasting pipeline already reads actual named-player pass EPA, treats QB1/QB2/QB3 as independent scenarios and has no automatic negative rank penalty. As of the last full capture, 206 of 230 upcoming team-game slots had a projected player, while zero met the strict game-specific reviewed official-starter standard. Model projection and official confirmation are separate fields.

## October 29 proposed-starter refinement (this branch)

1. **Repeated observed QB usage:** derive `recent_two_game_leading_passer_proxy` if the same named QB dominated passing-play use in both of the two most recent distinct football dates. Keep these dated, before-cutoff and source-observed; no confirmation is inferred.
2. **Incomplete player attribution:** refuse to identify a dominant player when fewer than 70% of known pass plays have a named passer. Do not trust a 100% share of a tiny *named* subset as a complete QB game.
3. **Outdated chart conflicts:** when chart QB1 and last-game passer differ, accept a *low-confidence* expected replacement only with two consecutive dominant passer games and an undated chart, or a *medium-confidence* projection if the dated depth chart demonstrably predates the newer actual game. A clearly newer chart conflict remains unresolved, not silently overwritten. Explicit pre-decision OUT/CONFLICT evidence blocks choosing an inactive recent QB.
4. **Verified QB1 out, no recent passer:** use the first other charted QB not listed OUT as a **low-confidence candidate**, never a confirmed starter. Preserve the alternate scenario list and any missing player sample.
5. **No phantom player downgrade:** the existing `qb_conditional_forecast.py` uses the prospective candidate's actual prior passing EPA, sample-size shrinkage, and a fitted team-scoring coefficient. It does not penalize a player simply for a QB2/QB3 depth rank. If there is no trustworthy sample, emit PASS/no adjustment and retain uncertainty.

This improves inference, not source attestations or historical betting validation. Unit tests cover consecutive usage, chart conflict, injury overrides, low named-pass coverage, and intact strict confirmation boundaries. Run the entire CI suite before merging and an actual `[run-intake]` workflow to measure the change against the previous 206/230 expected-starter checkpoint.

## Starter-evidence tiers

- **Confirmed for this game:** independently reviewed, explicitly dated official team / on-record coach statement naming who starts the **specific** upcoming fixture. Source, capture, publication and review timestamps must all precede the forecast. Contradictions quarantine the claim.
- **Likely/projection:** timestamped ESPN game-specific historical participation, team-athletics reports describing recent health or role, Ourlads third-party depth chart, pregame availability records and multiple-game QB usage evidence. Do not call this confirmed.
- **Unresolved:** missing/contradictory/time-invalid data; preserve plausible player-conditioned scenarios and the unmodified V03 fallback.
- **Postgame evidence:** independently verify the actual first QB/snap share and offensive output, but never leak a postgame starting identity back to a frozen pregame forecast.

## Next development milestones, in testable order

1. **National QB source coverage:** expand verified official football preview/article and direct game-note PDF sources beyond the few currently readable feeds. Capture dated full text and exact fixture, not just an RSS homepage or metadata. Add a separate official availability update pipeline with conflict/review signals. Measure confirmation coverage by game week and report source failures.
2. **QB state estimator:** train an as-of, game-specific, probabilistic starting-player forecast using chart ranking, observed game usage, dated practice/coach/availability, transfer and known replacement/return events; retain calibrated `P(QB starts)`, reliability, contradictions and a genuine UNKNOWN mass. Learn weights from prospectively saved predictions and independently verified postgame labels; do not invent calibrated values while training data are absent. High-impact uncertainty should return scenario ranges or PASS.
3. **QB performance conditional on opposition:** for each credible QB compute opponent- and pressure-adjusted pass EPA, accuracy/completion over expectation where measurable, explosive rates, sack avoidance, scramble efficiency, red-zone performance, and recent form; estimate a hierarchical/shrunken player plus offensive-support contribution. Players with no prior play-by-play are assessed using explicit transfer or historical prior with large uncertainty, not automatically “0-point effect.”
4. **Run/pass matchup engine:** candidate features should quantify offense style against opponent defense and environment, including fronts/OL mismatches, pressured dropbacks, pressure response, opponent-adjusted rushing success, red zone, explosive-play suppression and verified turnovers. Use time-versioned features and missingness indicators. Test new features *one family at a time* against the recency-corrected and active reference model before combining.
5. **Generative scoring distribution:** model possessions, plays/drive, field position, drive points and non-offensive scoring; simulate joint team-score distributions with pace and explosive-play uncertainty. Derive SU, margin, ATS and totals distributions consistently from that joint model. Test against a simple calibrated ridge and market consensus.
6. **Calibration and markets:** archive real predecision sportsbook prices with observed timestamps and provider identity, use market spread/total as an explicit baseline, measure MAE, log loss/Brier, reliability, interval coverage, ATS/O-U performance and vig-adjusted ROI only when price-side evidence exists. Keep opening/closing attribution honest; never fabricate.
7. **Walk-forward challenger gate:** freeze forecasts 24–72h or chosen fixed lead before kickoff, sample one decision per game/version, use game-disjoint weekly evaluation with predecision snapshots, independent final scores, uncertainty intervals and minimum coverage. Track performance by conference, QB status, week, home/away, market-disagreement band, weather and source-missing cohort. Correct the known original V03 home-team bias; avoid post hoc winner selection.
8. **Operations:** monitor intake schedules, fixture and publisher changes, data latency/failures, forecast/grade archives and alerting. No scheduled run should silently promote candidate features or erase prior picks.

## Explicit completion criteria

- Verification pipeline passes unit/regression tests and live intake.
- A starter expectation is emitted for every source-supported fixture; unsupported cases remain unresolved and each model forecast retains plausible conditional alternatives. Official confirmations are **only** reported when genuinely documented.
- Player/QB effects and new game-level features beat the recency-controlled baseline on *independent prospective* matched games, with no worsening of key calibration / home-bias diagnostics. Historical retrospectively mutable PBP alone never qualifies.
- Model promotion remains a separate reviewed change, never a side effect of changing labels, dashboard cards or an impressive in-sample comparison.

**Current released model:** `V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1`, status `PASS_UNVALIDATED`. This branch changes the QB *research projection inputs* and supporting tests, not the released score/ATS/total predictions.

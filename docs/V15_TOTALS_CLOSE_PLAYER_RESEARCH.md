# V15 — chronological totals, pace, competitive-matchup and player-opportunity research

**Status: complete experimental implementation and tests; NOT a production promotion.** Working branch: `research/v15-totals-close-player-ablation`, repository `The-Caves/cfb-model`. Date: November 17, 2026.

## Goal and constraints

Preserve original V04 and V14 forecast scores and market quotes. Use previously frozen scoring strengths as the baseline, then experiment with narrow, regularized effects that could improve totals and close-game matchups. No same-week game outcome, no current bookmaker line, and no postgame QB/injury/weather data enter fitting. Historical ESPN 2026 PBP originally retrieved after its game week does **not** have independently verified first-publication times: do not claim authentic earlier-week source availability or future performance. The exact 377 games have repeatedly been inspected since V04, so cannot establish an independent discovery regardless of chronological labeling.

## Implemented

- `scripts/v15_residual_challengers.py`: independent scored ablations atop original **frozen V14 joint_close**: (A) league totals bias, (B) totals bias plus earlier-week observed pace feature, (C) limited close-game margin interaction with historical pass EPA, pressure and turnover matchup vectors, and (D) combined. Both totals and margins use ridge coefficients constrained toward zero and capped at **±4 points totals, ±3 points margin**. Close-game effect only for V14 margin within 10 points. Missing dated matchup profile means no inferred feature effect.
- `scripts/v15_walkforward.py`: source-frozen identical V04/V14 377-game control pairs; every whole football week must finish before its results can train the next week's V15 correction or forecast-variance calibration. Replays original V14 scored margin and total plus Brier/CRPS before allowing comparison. Grades winner SU, margin/total MAE, margin/total CRPS, 80% intervals, observed-line ATS and totals directional accuracy and probability calibration. The quote subsets remain only 156 spread and 154 totals; no fabricated odds.
- `scripts/v15_player_opportunities.py`: separate prospective-only, confirmed-athlete conditional yard-error diagnostic. It can only learn from *individual*, first-frozen pregame forecasts paired with independently observed postgame player-stat outcomes **known before** the next decision, with source identity/timing hashes, confirmed-active player at forecast time and explicit stat availability. Minimum 30 category samples in 10 separate games, 70-observation shrinkage and bounded adjustments. This does **not** invent missing starters, player participation, player-stat categories, touchdown attribution or prop lines. It does **not** modify the original conserved team attempts/yards or existing player scenario Monte Carlo outcomes; adjusted category means are separately labeled **non-conserved diagnostic research**, not sportsbook plays. **The existing prospective PlayerForm aggregate contains 622 recorded observations but does not retain the individual verified paired input records required here. Therefore the newly implemented player calibrator has not been trained on those observations.**
- Tests `tests/test_v15_residual_challengers.py` and `tests/test_v15_player_opportunities.py` verify full-week source embargo, target-outcome exclusion, score identity, model caps, player pregame status, independently verified finals, unknown-player preservation and no existing lineup/budget mutation.
- Reproducible workflow: `.github/workflows/cfb-v15-research.yml` downloads **the exact archived V14 cross-check JSON from successful research run 43527440626**, tests V15 and every existing repository test, runs full 377-game walk-forward, uploads a game-level/weekly result artifact. **[Successful CI/backtest #44035992548](https://github.com/The-Caves/cfb-model/actions/runs/44035992548).**

## Same-original-377 historical research results

| Model | SU winners | Margin MAE ↓ | Total MAE ↓ | Margin CRPS ↓ | Total CRPS ↓ | ATS direction (156) | O/U direction (154) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V04 unchanged | 246 | 12.92665 | 13.54137 | 9.163757 | 9.540646 | 70 | 62 |
| V14 frozen | **248** | 12.89008 | 13.45919 | 9.138000 | **9.523529** | 74 | 64 |
| V15 totals bias only | 248 | 12.89008 | **13.45034** | 9.138000 | 9.525449 | 74 | 64 |
| V15 bias + pace | 248 | 12.89008 | 13.45220 | 9.138000 | 9.528092 | 74 | 64 |
| V15 close-margin only | 248 | **12.88672** | 13.45919 | **9.134442** | 9.523529 | **75** | 64 |
| V15 combined | 248 | **12.88672** | 13.45220 | **9.134442** | 9.528092 | **75** | 64 |

**Key observation:** no additional winner directions; total MAE improvement is under 0.01 point, and total CRPS worsens slightly relative to frozen V14. Close-game margin improvement is about 0.0034 MAE, ATS +1 direction on a small observed quote subset. All are too small to promote. Total-over Brier: V14 **0.267591**, V15 bias **0.266993**, V15 combined **0.266959**, all worse than a 0.25 constant 50% reference on the quoted historical subset.

**Close/competitive game subsets:**

| Subset | N | Frozen V14 SU | V15 combined SU | V14 margin MAE | V15 margin MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| V04 predicted margin ≤3 | 85 | 45 | 45 | 11.93898 | 11.93273 |
| V04 predicted margin ≤7 | 176 | 100 | 100 | 12.51908 | 12.52236 |
| V04 predicted margin ≤10 | 241 | 143 | 143 | 12.59520 | 12.59220 |
| Observed market spread ≤3.5 | 46 | 20 | 20 | 13.84062 | 13.82577 |

All original scored V04 and V14 mean projections and historical outcomes matched the saved artifact exactly. Weekly cutoff history (training games from previous fully completed original weeks): Sep26 **0**, Oct03 **43**, Oct10 **101**, Oct17 **153**, Oct24 **212**, Oct31 **261**, Nov07 **320**.

## What was actually learned (and what we still do not know)

- There is **no evidence** that adding another general tempo multiplier, small totals bias or further weak pass/pressure interaction meaningfully beats V14. The score model appears adequately regularized; more post-hoc knobs would create selection overfit.
- The original **49 source-frozen games from Nov14–15**: V14 and V04 both 33/49 SU; V14 26/48 ATS vs V04 25/48; V14 23/49 O/U vs V04 21/49; V14 total MAE 12.30045 vs V04 12.82708. Useful confirmation of slight improvement, but not yet a reliable market edge. Neither these results nor repeated 377-case research justifies modifying the published scoring engine.
- Current missing high-impact data should be **source-verified starting QB at a genuinely archived decision timestamp, offensive line/front injuries, player snap/route/target shares, weather forecasts and special teams/clock/drive state**. In prior work these were incomplete or retrospectively sourced. Do not substitute postgame observations for old pregame facts.
- Historical player-stat aggregate **622** observations is NOT an input dataset for V15 player's estimator; the source does not persist per-athlete signed residual evidence, and a player unlisted or DNP is not zero. Capture individual authenticated first-pre-kickoff score, athlete role, result-known timestamp, subsequent observed stat and bookmaker quote before fitting a real player betting challenger.

## Decision / next milestones

1. **No new scoring promotion:** V04 remains the website's baseline scoring model; V14 remains a separate research challenger, V13 remains a probability display. Keep V15 ablations on research branch and do not claim profitability.
2. **Protect prospective evaluation:** ensure the final-settlement and player-stat grading workflows consistently finish (prior HTTP 403 GitHub rate limits and archive tree timeout remain concerns). Freeze upcoming games' first pre-kickoff V14 and V15 experimental forecasts with signed input source provenance and read-only ledger. No future grades may backfill a missing pregame forecast.
3. **Close-game QB/lineup and source fidelity:** collect timestamped official starter announcements, OL availability, pressure and turnover opportunity with explicit UNKNOWN states. Fit narrow effect only after sufficient pregame-source rows; compare on future untouched games.
4. **Totals/game state:** seek actual drive count, first downs, fourth-down decision, pace under game script and nonoffensive scores, with strict historical first-seen dates. Avoid global fixed score shifts based on a single low-scoring Saturday.
5. **Player calibration:** add the individual pregame signed player-stat receipt ledger and paired actuals, then evaluate the V15 category correction separately from the conserved V14 Monte Carlo, with genuine two-sided timestamped prop quotes. Track per-stat MAE, conditional coverage, and simulated probabilities—never assumed EV.
6. **Future promotion gate:** require several untouched later football weeks showing consistent paired lower MAE and CRPS, improved ATS/O-U Brier/log-loss/coverage versus both V04 and V14, and robust QB/team/personnel segments. PASS whenever source is incomplete.

**Final model action:** retain original production scoring and real published picks; store V15 as an explicitly nonpromoted challenger and prioritize getting real prospective player/personnel inputs before adding more weights.

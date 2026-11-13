# V12 research — opponent-conditioned red-zone trips, turnover position and calibration

**November 13, 2026.** Research branch `research/v12-opponent-conditioned-possessions` of `The-Caves/cfb-model`. The existing `main` V04-based production decision remains untouched. The experiment is **not promoted**, and **not eligible to drive wagering picks**.

## What actually changed

- Preserve *original* V04's historical weekly opponent-strength, separate offense/defense fitted scoring scores as the in-possession prior; preserve V11's dated, opponent-adjusted EPA replacement and other scored V10 hazards. Do **not** claim the separate 17-field scouting profile or SOS/SOR/SOV automatically enters fitted probability equations.
- From the **existing fixed 387 accepted 2026 drive ledgers**, fit a real empirical two-stage conditional mixture for each offense versus opponent defense and five opening field-position zones: `P(entered_red_zone | start_zone)`, then `P(TD,FG,TURNOVER,EMPTY | red_zone_visited,start_zone)`. Unobserved team-zone combinations shrink to earlier league outcomes. A drive that **starts** in the red zone is already an observed red-zone opportunity. Red-zone *play* success is no longer claimed to equal actual TD conversion per trip. The model still simulates end-of-drive outcomes, **not** every play, each fourth-down decision or every down-and-distance state.
- Continue to shrink turnovers, distinguish defensive-return touchdowns from ordinary takeaways, and sample next possession's start from actual turnovers versus scores and non-scoring exchanges. Add prior offense giveaways and opponent-defense takeaways as additional low-weight sources for real short-field placement. Do not create hypothetical yardline training examples.
- Produce Monte Carlo *margin and total score distributions* as well as red-zone trips/TDs and win probabilities. On archived real pregame sportsbook quotes compute hypothetical P(home cover) and P(over), Brier, log loss, reliability bins, CRPS, 10th–90th percentile coverage/width, and weekly breakdowns. All evaluation remains retrospective.
- New `scripts/v12_availability_gate.py` refuses retrospective QB/injury/weather records missing BOTH first-publication and independent first-observation timestamps **before** an actually archived forecast cutoff. Weather must be a contemporaneous **forecast**, not postgame realized weather. Missing records stay unknown, and **no historical player/weather scoring effects** are activated or guessed. Adding this gate does not claim full verified 2026 QB/injury/weather coverage.

## Executed initial same-cohort V12 result

[GitHub Actions #43503671183](https://github.com/The-Caves/cfb-model/actions/runs/43503671183) passed V12 simulator/unit tests, source input downloads and 377-game 2,000-draw paired backtest. Files: `v12-opponent-rz-turnover-paired-backtest.json` and `v12-calibration-summary.txt` in artifact `cfb-v12-opponent-rz-turnover-research`.

All 377 examples are the *same* complete source-matched, strict original V04 weekly cutoff cohort from V11, with original V04 score, previous V11 result and genuine observed (not assumed closing) market lines. There were **0 additional excluded games**, though historical upstream ESPN PBP/publication timestamps were not independently verified at each original forecast date.

| Same 377-game cohort | V04 | V11 | V12 first experiment |
| --- | ---: | ---: | ---: |
| SU winner directions | **246/377 (65.25%)** | 234/377 (62.07%) | 220/377 (58.36%) |
| Margin MAE | **12.9266** | 13.9234 | 14.1036 |
| Total MAE | **13.5414** | 14.1147 | 14.0368 |
| Hypothetical ATS directions (156 authentic pregame quote matchups) | 70/156 | **75/156** | 74/156 |
| Hypothetical O/U directions (154 authentic pregame quote matchups) | 62/154 | **68/154** | 66/154 |
| Home winner Brier (smaller better) | unavailable | **0.23392** | 0.23486 |

Additional V12 diagnostics:
- **Margin** empirical 10–90 interval coverage = **75.86%** (nominal 80%); mean width = 39.67 points; CRPS = 10.05976.
- **Total** empirical 10–90 interval coverage = **73.74%** (nominal 80%); mean width = 39.22 points; CRPS = 9.87700.
- Hypothetical **ATS cover** probability Brier = **0.282359**, log loss = 0.768581, expected calibration error = 0.142821 (n=156).
- Hypothetical **total-over** probability Brier = **0.279063**, log loss = 0.755714, expected calibration error = 0.159660 (n=154).
- Winner probability Brier = **0.234863**, log loss = 0.662124, expected calibration error = 0.067486 (n=377). The first two Brier scores exceed the naive 0.25 all-50% benchmark; this is a warning, not evidence of betting advantage.

**Result: reject V12's current heuristic probability transfer for promotion.** It improves total MAE slightly over V11, but weakens SU, margin, ATS, O/U and winner Brier. The under-coverage of 80% margin/total forecast intervals further indicates miscalibrated uncertainty. This comparison is retrospective and on a repeatedly examined season, so it is **not** an independent prospective test.

## Next V12R2 experiment, not yet proven

1. Diagnose the failure at the drive level on earlier-week held-out folds: actual red-zone trips and scores per trip by start zone; field-position transitions after turnover, kickoff and punt; source coverage by offense and opponent; scoring-prior behavior versus original V04.
2. Replace hand-set multipliers with **bounded, regularized** offense-defense interaction parameters trained on strictly older weeks, with league priors for small sample sizes and dated opponent strength. Separate probability of reaching the red zone, TD once there, FG and turnover. Do not post-hoc tune against the same 377-game results and call it a fresh validation win.
3. Use chronological walk-forward with train-only calibration (Brier/log loss/CRPS/80% interval coverage and independent later-week evaluation). Test V11 vs V12R2 *and* champion V04 on exactly the same eligible games, then compare by month, conference/strength disparity, red-zone volume and QB-availability source quality.
4. Accumulate truly first-observed archived QB/injury/weather forecasts for future games; unknowns must not be coded as healthy or as unchanged starters. Test personnel/weather ablations only after pregame published/observed evidence exists, and only on a sufficiently large independent future cohort.
5. Keep published picks, performance archive, and all original betting lines unchanged. No claim of positive expected value or profitability is supported. Monte Carlo trial count reduces sampling error, **not** model misspecification.

## Reproduce

CI workflow: `.github/workflows/cfb-v12-possession-research.yml`. Runs strict V12 + V11 + V10 unit tests, downloads the *same* fixed input artifacts, rebuilds the original V04 weekly profile bridge and evaluates V12 using `scripts/v12_possession_backtest.py`. The current branch is experiment-only.

**Integrity limitations:** Retrospective ESPN source data have no proved first-publication timestamp at past cutoffs. Verified football *game dates* are not equivalent to verified *source availability dates*. Existing prospectively archived forecasts and genuinely observed bookmaker quotes are distinct from historical reconstruction. Continue to treat the entire result as research, not authenticated historical trading performance.

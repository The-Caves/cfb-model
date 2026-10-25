# October 24, 2026 — 44-game frozen model audit

**Audit performed:** October 25, 2026, after reported final scores.  
**Original unmodified model:** `V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1`.  
**Model snapshot:** `research_2026/forecasts/2026/10/24/run-40100613531.json.gz` in the `context-state` branch, 10:04:58 AM Eastern.  
**Exact published website comparison inspected:** `CFB-2026-QB1-QB2-QB3-Dashboard` preview associated with the October 24 ~11:35 AM ET workflow, with the original frozen predictions and 44 separately collected sportsbook observations, all before respective noon-or-later kickoffs.  
**Final score cross-check:** [FOX Sports October 24 scores](https://www.foxsports.com/college-football/scores?groupId=2), [Football Database scores](https://www.footballdb.com/college-football/scores.html?conf=10&yr=2026) and [The Odds Gap October 24 finished games](https://theoddsgap.com/games/past?date=2026-10-24&league=college-football).

This document reports an **explicit retrospective audit** of the preserved 44-game pregame snapshot. It is **not yet an automatically accepted grade in the prospective database**, and it must not be added to the old five-game verified scorecard without deduplication, snapshot-as-of policy selection, immutable authenticated final evidence, and pipeline acceptance.

## Observed results

| Metric | Model | Baseline |
| --- | --- | --- |
| Straight-up winners | **32–12 / 44 (72.7%)** | Always pick home to win: **31–13** |
| Against the spread | **28–16 / 44 (63.6%)** | Always pick the home team ATS: **28–16** |
| Totals O/U | **19–25 / 44 (43.2%)** | No home-side baseline; 28 predicted overs went 13–15, 16 unders went 6–10 |
| Absolute home margin error | **11.17 points/game** | Saved sportsbook signed home spread: **10.76 points/game** |
| Absolute combined total error | **15.95 points/game** | Saved sportsbook total: **14.86 points/game** |

No pushes occurred. Grades use `home_score - away_score + observed_home_spread` for home covers and `away_score + home_score` against the saved over/under, with exact model side as originally displayed. Game IDs are unique.

### Critical imbalance — do NOT promote this version based on its ATS rate

- **44/44 model ATS choices were HOME.** They were **not** a diversified selection process: a naive always-home system achieved the exact 28–16 result.
- **43/44 predicted straight-up winners were HOME.** On this day 31 home teams won outright, so always-home would have delivered 31 wins versus the model's 32.
- For all **102 upcoming games** represented in the same archived snapshot, the fitted model predicted **98 home winners**, four away winners. Bias thus extends beyond October 24.
- Average model projected home margin **+12.33 points**, average saved market implied home margin **+3.56**, and actual final average home margin **+5.61**. The model exceeded the actual margin by **+6.72 points per game** on average.
- **15** games had model-versus-market ATS differences ≥10 points: 10 home ATS wins, 5 losses. That is not evidence of model-specific edge when *every* choice is HOME.
- Freeze and test this issue; inspect training sample home/away labels, site neutral flags, missingness/centering, home-field intercept and feature direction before any prospective model promotion. Compare against always-home and market baselines in chronological held-out folds.

### Rice vs Florida Atlantic: the trigger example

- Actual final: **Florida Atlantic 51, Rice 49**.
- Frozen pregame model projected **FAU 39.27, Rice 12.42** (FAU +26.85 home margin), over/under model total **51.70**.
- Saved market **FAU -9.5 / O-U 54.5**. Model ATS choice **FAU -9.5: LOSS**; totals **UNDER 54.5: LOSS**; outright FAU win: **CORRECT**.
- Actual 100 points versus forecast 51.70 gives **48.30 points absolute totals error**; actual FAU margin 2 versus model 26.85 gives **24.85 points margin error**. Final result is evidence of calibration miss, but one game does not identify its root cause.

### Other significant misses

- **Hawai'i at Northern Illinois:** model projected Northern Illinois +7.96, Hawai'i won by 35; **42.96-point margin error**, ATS LOSS.
- **Boston College at Georgia Tech:** model projected Georgia Tech +12.24; Boston College won by 22, **34.24-point margin error**, ATS LOSS.
- **UTSA at Tulane:** model projected Tulane +6.27; UTSA won by 23, **29.27-point margin error**, ATS LOSS.
- **LSU at Auburn:** model projected Auburn +3.54; LSU won by 21, **24.54-point margin error**, ATS LOSS.
- **Oklahoma at Mississippi State:** model projected Mississippi State +12.14; Oklahoma won by 8, **20.14-point margin error**, ATS LOSS. The user specifically identified pregame Mississippi State quarterback uncertainty; **no causal QB impact has been established**, and the frozen forecast did not include verified QB-aware replacements.

### Six selections explicitly recommended later in the October 24 conversation

These use the **exact lines previously supplied to the user**, not later closing odds.

| Selection | Final | Grade |
| --- | --- | --- |
| Colorado State +1.5 vs San Diego State | CSU 56–49 SDSU | W |
| Clemson -3 vs Virginia Tech | Clemson 16–20 VT | L |
| Georgia State at Arkansas State UNDER 58.5 | Arkansas State 38–32 Georgia State (70) | L |
| Wisconsin +2.5 vs USC | Wisconsin 24–7 USC | W |
| Vanderbilt at Kentucky OVER 50.5 | Kentucky 34–17 Vanderbilt (51) | W |
| Utah -6.5 vs Houston | Utah 21–13 Houston | W |

**Evening shortlist: 4–2 (66.7%).** The four highlighted priority selections (Wisconsin, Colorado State, Clemson, Georgia State Under) went **2–2**. No staking, odds/juice, or realized return is documented; do not claim ROI.

### Evidence and grading status

The website already archives immutable score/margin/total research predictions and later observed sportsbook providers and lines, including exact separate observation clocks, under `context-state/research_2026/site_board_snapshots/index.json`. The initial live archive began after noon games started; that is why a **separate earlier preserved preview** was used for this complete October 24 audit. The current automated grade pipeline contains its prior five-game prospectively accepted ledger; **this newly computed 44-game audit has not been integrated as 44 verified prospective results**. Manual matching against published results is not automatic official ESPN final ingestion.

Source **upstream line publication times are not independently attested**. Lines were observed before kickoff but later than the 10:04 AM frozen research forecast. Do not backdate their availability to the model's forecast time or call them synchronized market-calibration training data.

## Recommended next steps

1. **Priority P0:** Test and explain the home-team selection pathology on prior strictly held-out weeks and current team profiles. Check whether training home/away distributions or feature production differs from future data. Apply no retroactive correction to this record.
2. Implement isolated versioned candidate model(s): home-field intercept calibration, travel/rest and neutral-site controls, market-anchored predictions, and honest historical replay with authentic as-of prices.
3. Grade all 44 with the same immutable final-score matching system used for accepted prospective performance; choose one prespecified snapshot per game and count it once for SU, ATS and total.
4. Add market baseline MAEs, blanket home-side benchmark, count of away picks, signed margin bias, calibration buckets, provider and kickoff capture times as permanent dashboard metrics.
5. Promote only after improvement on fresh out-of-sample data; keep `PASS_UNVALIDATED` until validated.

**Conclusion:** one-day ATS percentage appears promising **only without controlling for the trivial all-home baseline**. In fact, model margin and total error exceeded the saved market's error on October 24. Fix the bias and establish prospective skill before recommending the current model as a betting system.


## October 25 full 44-game root-cause diagnostic — exact archived model reproduced

A complete game-by-game numerical diagnostic was recomputed from **frozen forecast run 40100613531**, the before-noon **dashboard artifact from run 40108010413** (11:40 AM ET sportsbook observations), and final scores. Thirty of the game's official scoreboard IDs existed in the persistent `context-state/research_2026/market_finals/index.json` for the Saturday slate; the other fourteen final scores were cross-checked against October 24 published [FOX Sports](https://www.foxsports.com/college-football/scores?groupId=2), [Football Database](https://www.footballdb.com/college-football/scores.html?lg=FBS&type=reg&wk=8&yr=2026) and [WarrenNolan](https://www.warrennolan.com/fbs/2026/scores-live?date=2026-10-24&type=All+FBS+Games) scoreboards. No final outcomes were taken as model inputs.

**Reproduction:** [original training artifact](https://github.com/The-Caves/cfb-model/actions/runs/40100613531) includes 522 rows of `model_v03/weekly_pregame_features.csv` and `weekly_postgame_labels.csv`. Refit the actual 14-feature ridge regression (`scripts.model_v03.fit_ridge`, penalty 45; feature-wise imputation at means, standardized on the imputed distribution). The refitted model reproduced the saved 102 forecasted home margins and totals within **0.000005 points**. It yielded a **home-margin intercept of +13.9444444** and total intercept **53.3888889**. This is a **demonstrated mathematical feature of the active trained model**, not an anecdotal home-bias guess.

Training-period mean home margins were **August +11.88 across 8 games**, **September +19.21 across 323**, and **October through the October 24 capture +5.13 across 191**; the held-out 44 Saturday actuals averaged **+5.61**. The 44 forecasts averaged **+12.33**, so the mean signed home-margin bias was **+6.72 points**. Game features in the 44 add an average ~**-1.62** to the pooled home +13.94 intercept. Those 14 active features do **not** include a neutral-site flag, explicitly modeled home field, QB starter changes, official player availability, weather or market odds. The evidence strongly implicates a mismatched pooled home-margin baseline; determining how much stems from opponent mix, early-season mismatches, or inadequate opponent adjustment still requires a point-in-time ablation.

**Per-game audit summary:** SU **32–12**, ATS **28–16**, totals **19–25**, all on saved 11:40 lines with 44 distinct ESPN IDs, no pushes. Exactly **44/44 ATS predictions were home**, versus always-home ATS **28–16**; 43/44 SU projected home, always-home SU **31–13**. Model margin MAE **11.17**, market spread-implied margin MAE **10.76**; model total MAE **15.95**, market total MAE **14.86**. Model had smaller absolute margin error than sportsbook for only **20/44** games and smaller total error for **18/44**. Of 15 pregame spread disagreements at least 10 points, ATS **10–5**, again simply the home-team result. Large totals errors (>=20 pts) occurred on both low and high sides. Research home win probabilities averaged **70.8%** versus **70.5% observed**, with one-day Brier **0.182**; a single-day mean match does *not* establish calibration (game-level probability bins vary widely).

**Verified postgame mechanisms, not causal coefficients:**
- FAU 51–Rice 49: Rice replacement QB **Gael Ochoa's first start** replacing injured Jacurri Brown, **259 rushing yards and four rushing TDs**; Rice 499 rushing yards, FAU an 82-yard punt return TD. This helps explain the huge missed scoring and margin, but the model had no verified QB replacement impact. [Rice athletics](https://riceowls.com/news/2026/10/24/football-rice-falls-short-at-florida-atlantic-despite-ochoas-big-day).
- Oklahoma 23–Mississippi State 15: **Kamario Taylor actually started but exited in the first quarter**, and Parker Puckett took over; there was a critical near-goal-line fumble. The earlier official QUESTIONABLE status was informative but did not definitively forecast the in-game exit. [SEC recap](https://www.secsports.com/news/2026/10/owen-heinecke-anchors-oklahoma-defense-in-win-over-ms-state) and [Mississippi State box score](https://hailstate.com/sports/football/stats/2026/oklahoma/boxscore/27569).
- Hawaiʻi 56–Northern Illinois 21: five gains of >=30 yards and five defensive takeaways; the road offense achieved a season-high 504 yards. [Hawaiʻi athletics](https://hawaiiathletics.com/news/2026/10/24/football-hawai-i-snaps-skid-with-56-21-blowout-over-northern-illinois.aspx).
- Boston College 49–Georgia Tech 27: BC rushed for 399 yards and scored five rushing TDs, including a turnover-return score. [BC athletics](https://bceagles.com/news/2026/10/24/football-eagles-power-past-georgia-tech).
- UTSA 42–Tulane 19: Tulane committed six turnovers; UTSA scored six rushing TDs. [Tulane athletics](https://tulanegreenwave.com/news/2026/10/24/football-falls-42-19-to-utsa).
- Virginia Tech 20–Clemson 16: Clemson held the visitor to only 234 yards and led late; Virginia Tech scored the winner with 1:44 left. A loss here does not itself imply the defensive matchup profile was bad. [Clemson athletics](https://clemsontigers.com/news/2026/10/24/virginia-tech-defeats-clemson-late-20-16).

**Next experiments:** Compare the exact original model to an isolated, time-aware home-margin intercept, opponent-mix controls and market-anchored forecast candidate in *chronologically unseen* weeks; analyze true prospective QB replacement and passing/rushing volatility as independent features; evaluate quantitative error and baselines by model version. Do not tune on this one October 24 day and claim an out-of-sample win.

**Important line correction:** The archived 11:40 AM game-board snapshot lists Florida Atlantic **-10.0** versus Rice; a previously discussed **-9.5** quote came from a different market snapshot. Both would grade the original FAU ATS pick as a loss, but performance records must keep the exact quoted line and timestamp paired rather than silently combine them.

# V09 Archived 2026 score simulation

The new workflow runs a chronological Monte Carlo research comparison against actual pre-kickoff V04 score receipts. Source snapshots are SHA-256 verified and matched by team, ESPN game ID and kickoff. Actual result clocks must precede any use in a future simulation. No current team profile is used for an earlier game.

Four paired score methods: original frozen V04, uncorrected paired-error bootstrap, a fixed strongly shrunken global scoring-bias challenger, and a limited opponent-aware team-form residual challenger. Results include weekly winner accuracy, margin/total MAE, ATS and over-under grading where a real archived pregame sportsbook line exists, and simulation home-win Brier. Original decisions and grades are never overwritten.

These are SCORE distributions, not possession-by-possession simulations. The possession simulator and authentic-drive fitting code already exist but require sufficient source-reviewed historical drives. Weekly profile reconstruction exists, but publication timing for retrospectively sourced 2026 EPA/PBP statistics is not fully authenticated. Never apply today's profile to past matchups. Archive authentic game-date profiles and observed drive events before promoting a future challenger.

Research only. No new model is automatically promoted. Small prospective-style cohorts do not demonstrate wagering profitability.

## Executed results — November 13, 2026

**Strict original-pregame test:** GitHub Actions run 43482967393 passed, authenticated 160 immutable original site snapshots and found 90 independently settled V04 forecast games. However zero games met the 24-prior-settled-game and two-prior-football-date rule at their historic prediction time. This is limited coverage, not a model performance finding.

**Separate retrospective weekly simulation:** GitHub Actions run 43484364739 passed using fixed original November 13 source artifact cfb-2026-data-43475676201. There are 693 completed game rows in that source, 419 V04 historical weekly-held-out forecasts from seven weeks, and 354 common V04/Monte Carlo holdouts across six weeks after warm-up. Published underlying historical PBP first-availability dates are unverified; these metrics are NOT independently authenticated pregame decision records. Genuine pre-kickoff sportsbook spreads cover 160 games and totals cover 158 games; these are not authenticated closing odds.

| Model | Margin MAE | Total MAE | SU correct /354 | Hypothetical ATS /160 | Hypothetical O/U /158 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reconstructed V04 | 12.8341 | 13.7651 | 234 | 73-87 | 64-94 |
| Paired residual bootstrap | 12.8352 | 13.7552 | 233 | 71-89 | 61-97 |
| Global bias correction | 12.8835 | 13.6986 | 236 | 77-83 | 65-93 |
| Opponent-aware team form | 12.9347 | 13.5314 | 235 | 77-83 | 70-88 |

Team-form simulation improves total MAE by 0.23 points and hypothetical O/U accuracy by 3.8 percentage points, but its ATS accuracy is only 48.1% and its margin MAE is worse than V04. No challenger has demonstrated a reliable ATS or totals edge. Comparisons are hypothetical raw directional leans, not executed wagers or the original V04 PASS-aware policy. The observed market spread and total reference MAEs on priced subsets were 12.3688 and 13.1329, respectively; they are different cohorts from the full 354-game aggregates. No promotion.

**Prospective accumulation:** scripts/site_v09_shadow.py produces reproducible pre-kickoff V09 global/team-form score distributions only with at least 24 earlier independently settled source-frozen V04 games from two football dates, filtered by their settlement time. PRESSBOX Team Scouting shows this separately from the live V04 prediction. scripts/site_decision_archive.py records it in immutable pregame research receipts (v09_frozen_score_simulation) for future source-linked grading. These are score-level Monte Carlo distributions, NOT the full possession/field-position drive simulator.

**Next:** Verify complete historical drive/field-position/scoring events and publication times; add opponent-specific OL/pressure/red-zone/turnover matchup effects, weather, and independently verified QB replacements to future challengers; compare a calibrated possession simulator and selective market-aware decision thresholds on independently new slates versus V04, the sportsbook and simpler alternatives. Require cross-week improvement, proper probability scoring, enough genuine quotes, and no model promotion based on this retrospective backtest alone.

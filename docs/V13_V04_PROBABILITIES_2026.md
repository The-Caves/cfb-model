# V13 — Keep V04 scoring, add source-dated probabilities, publish new prospective shadow

**November 13, 2026.** The experimental V12R3 possession model does not beat direct V04 scores on the same 377 games. The missing capability is not a larger list of unverified per-play factors: it is coherent **prediction uncertainty**, especially against sportsbook lines, without degrading V04's proven regularized opponent-strength scoring foundation.

## Evidence-based diagnosis

- 377 previously evaluated 2026 historical games / seven original V04 weekly cutoffs. Original V04 correctly picked **246/377 (65.25%)** winners, margin MAE **12.9266**, total MAE **13.5414**.
- V11 with earlier-game learned pace picked **232/377 (61.54%)**, margin MAE **13.9023**, total MAE **13.8145**, margin CRPS **9.87791**, total CRPS **9.64680**, winner Brier **0.233372**.
- Over these same 377 games, V04's average predicted **home advantage +4.61 points**, while the actual mean was **+2.99**, and V11+pace projected only **+0.97**. V11's mean margin correction relative to V04 was **−3.64 points**. On the 74 winner-disagreement games, V04 had **44/74** correct and V11 **30/74**. Stronger apparent possession detail often eroded rather than improved the opponent-adjusted V04 signal.
- Prior V04 opponent-strength scoring incorporates opponent-rated margin, separate offense and defense point-strength fits, 28-day recency and bounded home venue, not the older simplistic V03 approach. The website already has V09 empirical paired score-residual research; V13's parametric prior-error distribution is a different uncertainty hypothesis, not a claim that prior residual research did not exist.

## New V13 model

`scripts/v13_v04_probabilities.py` **preserves V04's home, away, margin and total point means exactly** and computes probabilities with a transparent normal-margin / normal-total approximation. The main `prior_variance` variant estimates each dispersion using **only earlier completed holdout weeks** and a fixed 70-effective-game prior (**16.5 margin SD, 17.0 totals SD**). It uses no market line to fit probabilities, only observed real book quote(s) to evaluate cover/over probabilities, when independently captured before kickoff. Game-level probabilities are **not calibrated wagering edges**.

Retrospective ablations are explicitly separated, not promoted: fixed historical league SD, V11 spread/total width replacing SD, bounded 10% V11 score blending, and prior-mean-error correction. None is treated as a reliably selected improved scoring engine from 377 repeatedly inspected games.

## Executed historical comparison

Source data are the **same original V12R3 fixed 377-case archive** of pre-original-week game labels. `scripts/v13_v04_backtest.py` locks calibration to previously tested **whole weeks**. V04 score means and archived histories cannot be refitted or rewritten, quote samples are observed **156 ATS and 154 totals** with no invented missing lines. GitHub Actions V13 artifact contains exact game-level probabilistic metrics.

| V13 variant | SU correct | Margin CRPS ↓ | Total CRPS ↓ | Winner Brier ↓ | 80% total interval observed coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| V04 points / fixed league normal SD | 246/377 | 9.15545 | **9.53614** | 0.215103 | 80.64% |
| **V13 V04-scored / prior-week residual variance** | **246/377** | 9.16376 | 9.54065 | **0.215008** | **79.31%** |
| V13 V04 scores / historical V11 interval width | 246/377 | 9.14774 | 9.53890 | 0.215927 | 78.25% |
| Experimental 10% V11 mean blend | 244/377 | 9.16134 | 9.54036 | 0.214883 | 79.58% |
| Experimental prior-week mean-error correction | 248/377 | 9.15242 | 9.51181 | 0.215015 | 80.64% |
| V11 + learned possession pace reference | 232/377 | 9.87791 | 9.64680 | 0.233372 | 78.25% |

V13's `prior_variance` ATS-home-cover Brier **0.267208** and total-over Brier **0.270122** on small observed-book cohorts; scores worse than an all-50% hypothetical Brier benchmark **0.25** on these selected quotes. Neither model has proven betting edge, expected profit or prospectively reliable bookmaker residual advantage. No historical first-publication authentication for retrospectively retrieved ESPN 2026 results.

**Bottom line:** The V13 probability layer improves *historical* distribution calibration compared to V11+pace without sacrificing V04 scoring, but the comparison is repeatedly examined 2026 data. We have not proven a new scoring champion or independent improvement.

## Website publication and prospective grading

`scripts/site_v13_shadow.py` attaches to the real site only when:

- An independently source-verified V04 forecast is observed **before the game** and matches the exact original score fields.
- It has at least **35 distinct independently settled and originally captured V04 games across 2 earlier forecast days**, all finalized before the current forecast observation timestamp; the original captured source and independent finals are read from `context-state`, not hindsight reconstructions or current-season refits.
- A visible sportsbook cover/total probability is attached only for a genuine earlier observed bookmaker quote before kickoff; absent lines stay null.
- New V13 scores are **identical to frozen V04 scores**; original V03/V04/V05/V09 model picks, market policy decisions and graded records are not changed.
- The website labels the V13 probabilities as **research**; original V04 point projections remain the scoring foundation. A V13 display is not a production scoring-model promotion.

`scripts/site_decision_archive.py` now validates source IDs, calibration history, original V04 scores, computed normal-CDF probabilities, 10–90% bands, market-quote identity and timing before freezing a separate `v13_frozen_probability_shadow` under the immutable first pre-kickoff website receipt. `scripts/site_v13_performance.py` grades **only the earliest actual timestamped V13 pre-kickoff receipt against a separately observed, post-kickoff final**. Multiple website runs do not increase the denominator. Missing V13 forecast or final means **not graded**; no retrospective source reforecast is created.

The site score model still uses V04. The V13 field is a separately displayed, independently prospectively gradable, research-only probability upgrade. V13's full **score-model promotion** requires untouched future weeks, source-verified QB injury/weather effects and predeclared SU, ATS, totals CRPS/Brier/coverage thresholds. The 377-game backtest explicitly cannot authorize that promotion.

## Other priority experiments after accumulating untouched evidence

1. Early/late drive state: real down-and-distance, possession length, timeouts, first down conversion and game-script pace from genuinely archived PBP. Avoid hand-tuned extra drive effects.
2. Opponent-specific attack/defense: opponent-adjusted EPA, explosive rate, pass-protection versus pressure, rushing trench, field position, third/fourth down, turnover quality and red-zone opportunity **only if historically pregame source-authenticated**. Fit as a tightly regularized, low-dimensional residual to V04, not as a replacement for team scoring strength.
3. QB continuity, confirmed QB1/QB2 status, OL/front absences and weather must be timestamped first-published **before the decision**, with unknowns preserved and no postgame lineup leakage.
4. Compare a frozen model to market spreads/totals with uncertainty and selective PASS thresholds. If it merely learns the book line, don't claim an independent betting advantage.
5. Evaluate challenger versus V04 and actual book on **new future snapshots**, with predeclared sample gates, paired chronological performance, and separate ATS/OU/calibration stability.

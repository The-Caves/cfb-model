# V05 — robust opponent-strength challenger (November 2026)

**Status: RESEARCH ONLY.** V05 is not a validated wagering model, does not replace original V03 or current V04 displayed scores, and must never silently overwrite an archived forecast. It is published as a *shadow* on the site for prospective comparison.

## Improvements in this milestone

1. **Two-sided score fit.** Fit offensive scoring and opponent defensive suppression from previously completed games, with separately estimated opponent-adjusted margin. No V03 total, sportsbook quote or unsourced team injury enters the point forecast.
2. **Blowout resistance.** Cap training margins at 28 points; winsorize extreme team scores; use three deterministic Huber IRLS iterations so extraordinary routs cannot dominate otherwise comparable games. Compare against identical nonrobust ridge ablation.
3. **Weekly opponent strength.** Margin fit is ridge-stabilized and weighted by 28-day exponential half-life (14-day and 56-day research variants allow paired recency ablation). Same-day Eastern results are embargoed even when earlier kickoff has completed.
4. **Opponent-specific attack/defense.** Separate home/away team scoring predictions and opponent effects, combined with a constrained home-field prior of 0–4.5 points and opponent strength margin. A neutral-site reversal should reverse predicted margin without a home advantage.
5. **Recent team trajectory.** Only prior score residuals, last four games; at least three previously played games. Apply very small shrinkage toward zero and explicit caps; margin/total/no-form variants are evaluated independently.
6. **Thin-history uncertainty.** Identify where either team has fewer than four completed games; do not invent a full-season profile, a confirmed starter, or a replacement value.
7. **Strict paired benchmark.** Every V04 and V05 score/ablation in a fold uses the same held-out ESPN game IDs, from the exact same past-only training date cutoff. Report SU, margin/total MAE, signed margin/total bias, large-miss fraction, home-pick tendency and always-home baseline. No retrospective chosen best parameter can trigger promotion.
8. **Later-fold interval diagnostic.** Derive provisional 80% absolute-residual intervals using **earlier holdout weeks only** (at least 35 earlier out-of-sample game residuals across at least two weeks); record actual coverage, interval width and inability to guarantee stable calibration.
9. **Prospective archive & site performance.** Store V05 independent scores along with V04 and the untouched V03 receipt, then compare V05 with V04 on exactly the same subsequently settled games. Count missing/unknown evidence without rewriting old forecasts.
10. **CI and audit guardrails.** Test clock cutoffs, duplicates, invalid scores, negative points, neutral symmetry, ablations, no-future-labels, checksum protections, immutable receipts and non-promotion. Real 2026 data benchmark runs in a separate workflow and uploads full per-game results.

## Important evidence gaps

- **Quarterback starters and injury replacement value:** 2026 pregame sources still have incomplete verification. This milestone makes *no inferred QB adjustment*.
- **Actual play-by-play and team style:** existing matchup/creative research uses retrospectively mutable play-by-play. V05 in this milestone uses source-matched final scores only; no unsourced sack, EPA, turnover luck, red-zone efficiency or drive origin enters its fitted scores.
- **Historical betting line timestamps:** original market publication history cannot be authenticated reliably. V05 is **not** graded ATS on historical data without truly observed pregame lines.
- **Small evaluation window:** one season of evolving programs and opponents cannot validate probabilistic intervals or profitable ATS. Each shadow prospective cohort accumulates only after the model and source observation were frozen before kickoff.

## Independent model-competition gate

The auditable gate in `scripts/v05_competition_gate.py` requires at least 200 historical paired games across four weeks, **at least 2% improvement on both margin and total MAE**, no decrease in straight-up accuracy, a home-selection fraction within 10 points of actual home-win frequency, and at least 75% observed coverage for *both* nominal 80% intervals on earlier-fold-only residuals. It also separately requires at least 250 genuinely archived prospective decisions over four weeks, authenticated market-quote timing and independently verified final results.

A passing historical experiment **cannot** authorize promotion. The output always states automatic promotion is false. If all checks were ever supported, the gate would only flag readiness for an explicit human review.

## Promotion criteria

Keep V05 **shadow-only** unless *fresh, genuinely prospective* non-overlapping samples demonstrate paired improvements over V04 and market baselines, calibrated uncertainty, acceptable home/away bias and stable performance across multiple weeks. Never use postgame boxscore starter labels as if known before kickoff. Do not tune a candidate on the same slate and report the fit as an independent win.

## Files

- `scripts/v05_robust_scores.py`: score model and ablations
- `scripts/v05_score_benchmark.py`: paired weekly 2026 V04 versus V05 contest
- `scripts/v05_calibration.py`: earlier-fold-only interval evidence
- `scripts/v05_competition_gate.py`: fixed metric thresholds, prospective source checks and fail-closed no-promotion audit
- `scripts/site_home_bias_guard.py`, `scripts/site_decision_archive.py`, `scripts/site_performance.py`: optional source-matched V05 shadow and future objective grades
- `.github/workflows/cfb-v05-score-research.yml`: real-data run and immutable run artifact

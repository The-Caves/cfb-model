# v0.4 Step 3F — Prospective validation readiness gates

**Research-only:** all output is `PASS_UNVALIDATED`. This is not an operational betting-pick engine, not a completed predictive validation, and not a basis for quantitative injury penalties. This version assesses *research readiness*, not a claim of real-world predictive accuracy.

## Frozen walk-forward membership, no hindsight

`scripts/personnel_ablation.py` now exports explicitly sorted `train_game_ids` and `test_game_ids` for **every** weekly fold, including skipped folds. `scripts/personnel_validation_readiness.py` reads Step 3E's original separately audited JSON files and validates each fold's exact identity against kickoff times and **observed final availability**. Each training game must have kicked off and had its final observed before that fold's cutoff. Every testing game must be in the fixed 7-day interval after cutoff; no game may appear on both sides of the fold or in multiple evaluated test folds. Fold metrics and model variants must use identical held-out samples.

Source-time correctness remains bounded by when *our* archive first observed the information. The evaluator's fold-wise means, standard deviations and ridge parameters are fit from training games only, not recalculated using test games. Unknown personnel information is kept missing, never assumed healthy.

## Predeclared research readiness checks

| Check | Required threshold |
| --- | --- |
| Historical training set | At least 90 previously observed final games per fitted fold |
| Held-out test group | At least 20 games per fitted fold |
| Repeated chronological testing | At least 3 nonoverlapping fitted folds and 60 held-out games total |
| Personnel variant comparison | Every personnel variant evaluates the same games as its baseline in each counted fold |
| Complete team availability reports | At least 60% of policy-eligible matchups with both teams reviewed |
| Explicit starting quarterback review | At least 25% of eligible team/QB slots independently reviewed |
| Feature completeness | No more than 50% of all feature cells are null |

These thresholds are **project diagnostics**, not statistically established clinical, betting or forecasting cutoffs. They are frozen in code to discourage repeated tuning against observed game results. Strict non-overlap, duplicated-ESPN-ID blocking, impossible outcome timestamps, damaged file schemas, future sources, missing candidate features and malformed metrics all fail closed.

Even if every check above passes, Step 3F reports `model_ready_for_promotion=false` and `model_promoted=false`, because the archive is not independently immutable, historical PBP publication timestamps are not externally authenticated, historical predecision sportsbook lines are unavailable, and out-of-sample statistical significance is not established. The `observed_personnel_research_comparison_ready` flag means **only that future research comparisons have adequate observed coverage and paired samples**, not that any adjustment is successful.

## Automation and artifacts

`python -m scripts.personnel_validation_readiness --dataset-dir data/step3e --output data/step3e/step3f-readiness.json` produces a JSON readiness report. It is integrated after Step 3E in both Data Intake and Observed Final Settlement GitHub workflows, each using the same free GitHub infrastructure and existing 30-day audit artifact retention. The report summarizes sample/fold counts, QB and report coverage, missingness, explicit blockers, and persistent research-only clearance.

## Current interpretation

October 22, 2026: the existing archive has 108 observed upcoming game profiles, of which 49 are in the specified 24–72-hour prediction window, but **zero** linked completed-game outcomes. No live QB/injury performance validation is possible at this stage. The project should continue collecting observed snapshots and finals, and **not invent old injury reports or guess historical market prices**.

## Next operational checkpoint

Verify that both workflows pass the full suite and that a live 3F JSON report says insufficient paired evidence without promoting a model. After observed games settle, rerun controlled, fully paired SU/margin/totals research ablations; add market ATS/O-U only with truly dated predecision odds.

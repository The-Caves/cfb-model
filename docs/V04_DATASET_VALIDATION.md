# v0.4 Step 3E — As-observed dataset and personnel ablation verification

**Clearance: research-only `PASS_UNVALIDATED`.** This step does not issue picks, declare historical provider publication timestamps proven, compute nonexistent sportsbook ATS/O-U lines, or promote a betting model.

## Evidence loader (free `context-state` branch)

`python -m scripts.personnel_archive_dataset --output data/step3e` reconstructs each 2026 original pregame capture and later score record using the existing GitHub `research_2026/pregame_index.json` and `research_2026/outcome_index.json`. Only branch-held, separately timestamped gzip evidence is used. The code refuses missing or unexpected files, duplicate ESPN IDs, altered hashes, invalid source/run/game identities, out-of-order timestamps, postkickoff captures, invalid label score arithmetic, mismatched scheduled kickoffs, and revised or unselected pregame observations.

The label's `outcome_known_at_utc` is the **first observed retrieval** in this pipeline, not independent proof of the earliest publisher release. The loader also verifies the original profile and personnel join SHA values before passing features onward. It enforces the predeclared **latest observed capture between 24 and 72 hours before actual kickoff**. It never repurposes October player reports as September evidence.

## Generated research artifacts

Each run writes `quality.json` (archived-game counts, dated observation coverage, QBs with reviewed confirmation, team availability-report coverage, missing-value counts, excluded labels, and evaluation gate), `pregame_features.json` (score-free feature vectors and capture provenance), `postgame_labels.json` (separate ESPN observed final outcomes), and `personnel_ablation.json` (fold diagnostics, baseline comparisons, and explicit blocked-promotion status). Files are created exclusively to avoid silently overwriting a past report.

The observed settlement-only workflow runs Step 3E **after** successful score settlement, even if no new final was linked that day. The Data Intake workflow also audits after each full pregame archive run; each workflow publishes the report as part of its existing 30-day Actions artifact. Raw source records are retained on `context-state` rather than in a paid service.

## Research validation gate

The evaluator uses the existing `scripts.personnel_ablation` research runner with **at least 90 earlier known finals for training and 20 test games per weekly fold**. Step 3E adds a conservative diagnostic threshold of **three matched walk-forward test folds and 60 total held-out games** before *even calling research comparisons sufficiently observed*. It also rejects missing candidate variation and compares variants only on identical held-out samples. Any threshold failure is `INSUFFICIENT_PAIRED_OBSERVED_EVIDENCE`.

Passing those numerical thresholds does **not** validate the model or approve picks: historic PBP assets can be retrospectively revised, source publication times are not independently attested, statistical significance is not established, and historical sportsbook prices remain unavailable. `model_promoted=false`, `model_ready_for_promotion=false`, and `PASS_UNVALIDATED` are enforced regardless of output.

## Operational start (October 22, 2026)

The first Step 3D archive contained **108 upcoming games and zero linked finals**. Step 3E should therefore confirm source/feature coverage and report insufficient outcome pairs, not claim a QB/injury-model improvement. As those archived games finish, the settlement workflow will create eligible final labels. Any 2026 predictions remain unvalidated.

Files: `scripts/personnel_archive_dataset.py`, `tests/test_personnel_archive_dataset.py`, updated `.github/workflows/cfb-data-intake.yml` and `.github/workflows/cfb-outcome-settlement.yml`.

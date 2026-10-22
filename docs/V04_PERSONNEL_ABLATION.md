# v0.4 Step 3C — Time-valid QB/availability features and ablations

**Status:** Research-only, `PASS_UNVALIDATED`. No new betting picks, promoted model, hand-tuned injury penalties, medically inferred conditions or proof that a reported player actually participated. The v0.3 retrospective results cannot be reinterpreted as source-publication verified.

## 1. Pre-kickoff feature joins

`scripts/personnel_features.py` accepts separately captured, verified-structure pregame team profiles (`scripts/pregame_evidence.py`) and timestamped QB and player-availability observations (`scripts/qb_history.py`, `scripts/injury_history.py`).

- Historical personnel observations must have been **actually observed at or before the profile capture**. Capture, source and review timestamps are validated using the existing history gates; mismatched ESPN ID, home/away or kickoff rejects the join. An observation from tomorrow cannot enter a decision yesterday.
- The feature record has game identity, profile SHA-256, own record SHA-256, captured time, each team's report coverage, reviewed QB status and individual source-backed *reported* availability. Evidence remains explicitly reported, not a diagnosis, replacement-value inference, player identity crosswalk or observed snap count.
- One-sided or missing report coverage never becomes a numeric zero injury difference: both-sided status differential features are `null` unless both team reports are explicitly reviewed. Unlisted players stay `UNKNOWN`.
- Baseline features are profile-derived metrics (margin, scoring, adjusted EPA, rushing/passing/success/explosive/pressure/drive history). They deliberately do not reproduce every field in the v0.3 training table (notably rest and venue), so **do not equate the new baseline with previously published v0.3 SU accuracy**. QB and team-report knownness indicators are binary; no per-player damage or speculative points applied.
- The workflow input is the **same** context JSON that supplied the initial profile capture, so source time and opponent identities can be checked before any join. QB news was not queried by this Data Intake step, so it does not claim that unavailable feeds were fetched or that an unreviewed mention confirms a starter.

Run from actual captured artifacts:

```bash
python -m scripts.personnel_capture \
  --capture data/pregame_evidence/capture-<GITHUB_RUN_ID>.json \
  --context data/context/upcoming_game_context_2026.json \
  --output data/pregame_evidence
```

On scheduled/manual Data Intake runs, its `data/pregame_evidence/personnel-joined-<run-id>.json` is a 30-day GitHub Actions artifact, along with `personnel-ablation-<run-id>.json`. This does not claim long-term independent immutable storage, and it does not silently write a research prediction to the context-state branch.

## 2. Controlled held-out ablations

`scripts/personnel_ablation.py` defines a predeclared **latest captured observation between 24 and 72 hours prior to kickoff** policy for each ESPN game. It requires a separately sourced, timestamped final label before the evaluation clock and prior-game labels actually published before a training fold cutoff. For each matched set it fits the baseline and candidate research ridge models using only training folds, comparing the following:

| Variant | Added features |
| --- | --- |
| Profile baseline | Pre-kickoff profile history only |
| Plus QB coverage | Independent reviewed-QB knownness by team |
| Plus availability coverage | Verified team-report knownness by team |
| Plus reported availability | Both-sided OUT, QUESTIONABLE, LIMITED and QB-OUT reported-count differentials when covered |
| All personnel | All of the preceding additions |

Unknown statuses are never treated as healthy. Variants without a varying signal in a training fold are **not fit**, rather than implying a valid zero effect. Output includes SU accuracy, margin MAE and total MAE (not ATS/O-U betting grades), pairwise baseline comparisons only for identically evaluated game sets, coverage QA and insufficient-sample statuses.

**Important:** The existing repo does not have a sufficiently large season-long body of verified pregame personnel captures linked to genuinely publication-time-verified results. Earlier September player reports cannot be reconstructed from later October live feeds. No authenticated historical FanDuel line series is available to produce ATS/O-U betting comparisons. The code will report insufficient data rather than invent an improvement or train an injury point penalty. Source URLs and timestamp fields are necessary but are not independent third-party publication-time attestation.

The comparison framework is deliberately not model-promotion machinery: every output remains `model_promoted=false`, `statistical_significance_established=false`, `safe_for_betting=false` and `PASS_UNVALIDATED`.

## 3. Next prerequisites

Accumulate several weeks of actual pregame captured profile and personnel artifacts, preserve appropriate permissions/retention and match to independently observed postgame finals with verified label availability. Adopt a source-time-verifiable EPA/profile input where possible. Then execute fixed-policy chronological ablations against identical held-out games, inspect missingness, leak tests, variance, and compare a genuine market-anchored SU / ATS / O-U baseline only when real dated sportsbook lines exist.

**Do not claim that synthetic tests or successful ingestion establish predictive improvement.**

## Cloud verification — October 22, 2026

[Full CFB Data Intake run 39788167540](https://github.com/The-Caves/cfb-model/actions/runs/39788167540) succeeded with **322 passing unit tests**, successful research-context ingestion, pregame profile capture, Step 3C feature joining and artifact upload. The per-run log reported **108 upcoming matchup profiles joined**, **9 matchups with both teams' verified availability reports**, **0 reviewed quarterback starters**, and `ablation_validated=false`. Artifacts `cfb-2026-data-39788167540` and `cfb-2026-snapshot-audit-39788167540` were uploaded successfully. The new `personnel-joined-39788167540.json` and `personnel-ablation-39788167540.json` are within the 30-day Data Intake artifact, not a permanent independent timestamp archive. Missing historical observed-outcome pairs prevent empirically comparing injury/QB adjustments yet. No actual live model predictions were generated, no injury points were assigned, and status remains `PASS_UNVALIDATED`.

# v0.4 Step 3G.1 — Prospective outcome grading from frozen research forecasts

**Status:** `PASS_UNVALIDATED`, research-only; neither model calibration nor a betting advantage has been established. This stage never generates a pick and never calls a sportsbook API.

## Selection and controls

The successful [Step 3G production research run](https://github.com/The-Caves/cfb-model/actions/runs/39809951180) archived **108 computed research forecasts**, of which **49 were observed with profile captures 24–72 hours before kickoff**. Zero official final-result pairs existed then. The grading stage is separate from the forecast archive and cannot alter earlier predictions.

`scripts/personnel_forecast_grade.py` reads `research_2026/forecast_index.json`, every referenced dated `research_2026/forecasts/...` record, the original pregame archive indexes and bundles, and the independently archived completed-game outcomes. It verifies profile, forecast, grade and postgame result checksums; event identity, home/away, kickoff and availability timestamps. It chooses **the latest truly observed qualifying 24–72-hour pre-kickoff forecast** for a completed ESPN game. Postkickoff, rescheduled, unmatched, missing-price, unverified or retrospectively forged records are never turned into predictions. A grade is written only after the final score was actually observed in the outcome archive.

## Grading metrics

Per observed finalized game, the new grading record includes the immutable forecast source SHA, original feature row SHA, finalized source SHA, decision/observation times, actual versus projected **home margin** and **game total**, absolute margin/total errors, a win-direction correctness indicator (ties and zero-projection margin are explicitly ungraded), and a **descriptive, uncalibrated** Brier probability diagnostic for straight-up winners. The Gaussian research win probabilities are not calibration-verified, and scoring them does not certify them.

Because no authenticated contemporaneous FanDuel quote is in the public archive, **ATS, O/U against the bookmaker, CLV and ROI are unavailable**. These fields remain `null`, no sportsbook quote is synthesized from the predicted margin, and no bookmaker API is queried.

## Immutable archive and daily reconciliation

The grader appends a separate `research_2026/forecast_grades/YYYY/MM/DD/<ESPN game ID>.json.gz` record and maintains `research_2026/forecast_grades_index.json` on the existing free GitHub `context-state` branch. It will not overwrite a prior grade or silently replace the chosen forecast if a later research snapshot appears. Conflicts and score corrections are flagged for audit; if nothing newly eligible is graded, **no new Git commit is created**. Existing archived grade files are read back and authenticated by SHA. Daily Observed Final Settlement runs grading after archiving finals. The Data Intake run also checks for newly gradeable historical games after freezing its own current-run forecasts.

The archive is Git-versioned and access controlled, **not** independent externally attested write-once custody. Its original 2026 play-by-play inputs can be retrospectively revised; future-source availability claims remain limited to when this workflow captured them. Thresholds from Step 3F and `PASS_UNVALIDATED` remain in force regardless of the number of graded games.

Run independently after Step 3D/3G archives are available:

```bash
python -m scripts.personnel_forecast_grade --output data/step3g-observed-grades.json
```

Files: `scripts/personnel_forecast_grade.py`, `tests/test_personnel_forecast_grade.py`, updated `.github/workflows/cfb-data-intake.yml` and `.github/workflows/cfb-outcome-settlement.yml`.

# Milestones 3–6: implemented research pipelines and acceptance boundaries

**Research only. No validated betting model.** This document distinguishes implemented software from unavailable authenticated historical inputs and empirical effect validation.

## M3 — Opponent-adjusted EPA / play-by-play

- `scripts/model_v03.py` and `scripts/weekly_profiles.py` calculate prior-game, date-exclusive 2026 EPA, pressure, drive and opponent-adjusted features, and chronological *retrospective* research folds.
- `scripts/pregame_evidence.py` and `scripts/personnel_archive_dataset.py` freeze actually observed pregame profile captures and match independent later final scores.
- `scripts/multifactor_walkforward.py` trains ridge models on prior **known** finals only and evaluates identical held-out games for baseline and enriched variants. It rejects late captures, duplicate games, mismatched finals, and future outcome timestamps.
- **Unresolved:** Provider historical PBP publication times and revisions are not independently authenticated. Retrospective chronology alone cannot prove point-in-time EPA availability.

## M4 — Timestamped sportsbook history and movement

- Existing `scripts/market_quotes.py`, `market_vault.py`, `market_features.py`, `market_event_crosswalk.py`, `market_settlement.py`, `market_walkforward.py` and `market_evaluation.py` normalize, archive, match, evaluate and grade source-backed odds, while quarantining ambiguous or post-cutoff observations.
- `scripts/market_history_import.py` batch-imports **user-supplied provider historical JSON snapshots offline** to the existing private local vault. It makes no paid calls and publishes no prices in CI.
- The quote's provider timestamp and later retrieval timestamp remain distinct. Retrospective imports are not presented as quotes executable at an earlier decision time.
- **Unresolved:** No authenticated historical FanDuel source snapshots are supplied. True opening/closing prices and actual market ATS/O-U results cannot be produced without those inputs. User must explicitly opt in to any paid provider requests.

## M5 — Weather and matchup effects

- Existing `scripts/game_context.py` captures outdoor pregame forecasts and indoor status.
- `scripts/weather_matchups.py` joins the original forecast to each archived matchup and calculates wind×pass, wind×explosive pass, rain×rush, cold×pass exposures. Unknown weather remains null. Source issuance, capture, game identity and kickoff chronology are checked.
- `scripts/multifactor_walkforward.py` evaluates weather variants against the same held-out games as the EPA baseline, learning coefficients from training games only.
- **Unresolved:** Historical forecast observations must accumulate in durable, date-indexed pregame archives before meaningful weather ablations are possible. The present weather sidecar is an Actions artifact, not independently time-attested permanent history.

## M6 — Player replacement effects

- Existing `scripts/injury_history.py` and `personnel_features.py` preserve reviewed pregame designations and missing coverage.
- `scripts/player_replacement.py` derives per-position confirmed-absence counts, separate uncertain counts, and estimates **position-level** residual margin effects using only pre-cutoff games and ridge regularization.
- `scripts/personnel_replacement_capture.py` joins the same actual pregame injury snapshot to the matching game and writes nullable position-count features. No report means unknown, never healthy.
- `scripts/multifactor_walkforward.py` compares absence-enhanced and combined variants on identical held-out games.
- **Unresolved:** Position counts are not individual player replacement value. Validating player-specific effects requires stable roster identities, depth/usage and actual observed snap participation, plus adequate held-out sample sizes.

## How to run

GitHub Actions `.github/workflows/cfb-data-intake.yml` runs:
1. All Python unit tests.
2. Retrospective EPA and chronological research diagnostics.
3. Official injury/QB source ingestion and coverage checks.
4. As-observed weather and replacement-count capture alongside personnel profiles.
5. Step 3E archived feature/final dataset.
6. Multifactor held-out walk-forward analysis (may correctly report insufficient paired games).
7. Prospective readiness and forecast/grade audits.

Local private historical odds import (offline only):

```bash
python -m scripts.market_history_import --vault /private/location/market.sqlite3 /private/snapshots/*.json
```

Offline observed walk-forward on a previously exported Step 3E dataset:

```bash
python -m scripts.multifactor_walkforward \
  --dataset data/step3e \
  --output data/step3e/multifactor.json \
  --first-test 2026-09-26T00:00:00Z
```

**Acceptance:** Passing tests proves the mechanics work, not that sufficient verified historical evidence exists or that the model beats market prices. Keep `PASS_UNVALIDATED`, compare only matched held-out games, and never report synthetic fixtures as actual bets.

## Validation checkpoint

The final full intake must pass the new observed weather, replacement and multifactor steps. A passing unit suite alone does not close this check.

## October 22 game settlement check

Request a fresh completed-game scoreboard ingestion and official settlement. Same-day captures remain excluded from the 24–72-hour official label policy; separate exploratory evaluation must never rewrite that policy.

## Previous-weeks research rerun

Re-run the 2026 retrospective weekly walk-forward comparison against freshly retrieved completed-game results. Do not label the retrospective EPA release as authenticated historical pregame evidence.

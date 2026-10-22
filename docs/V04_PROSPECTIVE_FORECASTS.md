# v0.4 Step 3G — Genuine prospective model forecasts and responsible market handling

**No bets, no financial charges, no fabricated prices, `PASS_UNVALIDATED`.** The model has not met prospective accuracy/calibration or injury-effect validation requirements. Step 3G establishes a frozen, reproducible ledger of **genuine computation**, not a recommendation engine.

## Actual fitted research projections

`scripts/personnel_forecast.py` uses actual completed 2026 ESPN scoreboard final games and the 2026 PBP-derived research dataset that were retrieved by the same Data Intake run. It reconstructs the model's time-ordered 2026 training feature rows with `model_v03.build_weekly_games`, then fits the **existing** regularized ridge estimator on 14 observed profile-derived base features (not the full 16-feature v0.3 model, and not a new hand-tuned injury model). In-sample training uses only actual completed game outcomes collected before the frozen pregame profile. If fewer than 90 completed research games exist, every forecast **PASSes** without numeric values. No invented team rankings, opponent outcomes, probabilities or injury point weights.

The frozen record includes home/away and ESPN IDs, kickoff, feature captures, per-feature values, profile/feature SHA-256, number of prior games, training-game-ID digest, full fitted-parameter digest, output model identifier, source manifest hashes, and **actual computed** projected margin, total points, implied home/away points, and an explicitly **uncalibrated** Gaussian research win probability. Research predictions are clipped to valid point totals. If the game kicks off before the record is generated, it is excluded. A projection is never retroactively reconstructed as if observed earlier.

## Market quote policy — opt-in and private, zero-cost by default

The existing `scripts.market_capture`, `scripts.market_quotes`, `scripts.market_event_crosswalk`, and `scripts.market_vault` support **offline synthetic tests and opt-in user-held source snapshots** from a bookmaker provider, with exact game joins, timestamp checks and local append-only SQLite storage. **No GitHub scheduled task fetches paid Odds API requests.** There is no configured free verified FanDuel historical line feed. The public Step 3G forecast contains `market.status=NOT_OBSERVED_PRIVATE_OPT_IN_ONLY` with *null* spread, total, moneyline and quote hash, and `actual_quote_count=0` for every game. It does not label a contemporary line as an opener/closer or include any purchased/private sportsbook prices in public GitHub artifacts.

To collect actual FanDuel observations, the user must explicitly opt in to the provider and manage credentials/credit costs separately; snapshots stay in the existing **private** vault outside the repository. This step does not configure credentials, run a paid API request, or grant sportsbook execution capability. Therefore ATS/O-U and ROI are still unavailable unless actual independently observed lines and settlement criteria are available.

## GitHub archive and next validation

Following the same successful Data Intake run's Steps 3C–3F, Step 3G freezes the ledger at `context-state/research_2026/forecasts/YYYY/MM/DD/run-<run-id>.json.gz`, plus `context-state/research_2026/forecast_index.json`. The dated file is append-only with readback, an original run ID and fresh capture (<45m old), and is stored with the existing free GitHub Actions artifact. No model calibration claims or validated betting scores are produced.

The validation gate remains the Step 3F policy. Only independently observed postgame labels and future captured market quotes can support later SU, spread and totals grading. A fitted model and successful CI do not by themselves establish a betting advantage.

**Note:** the 2026 PBP release can be retrospectively revised; Step 3G can only attest *this GitHub run's capture*, not earlier source-publication times. Research win probabilities use fitted residual uncertainty but are **not calibrated**, and published projections cannot be presented as verified model picks.

## CLI

```bash
python -m scripts.personnel_forecast \
  --joined data/pregame_evidence/personnel-joined-<RUN_ID>.json \
  --games data/games_2026.csv \
  --advanced data/advanced/team_game_advanced_2026.csv \
  --advanced-manifest data/advanced/advanced_manifest.json \
  --score-manifest data/manifest.json \
  --output data/pregame_evidence/step3g-forecast-<RUN_ID>.json
```

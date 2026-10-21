# Model v0.3 candidate — retrospective 2026 advanced football model

This public repository's 2026 SportsDataverse play-by-play is downloaded as a **later, retrospectively mutable release**, not stored as the historical version available before each earlier kickoff.

Implementation:
1. \`scripts/model_v03.py\` reads ESPN completed scores, two-sided validated SportsDataverse 2026 team-game EPA/drive aggregates and the original retrieval manifest. Every weekly feature vector uses earlier **calendar-date** games only, not the score or PBP of its target game. Its inputs include pass/rush EPA, offensive and defensive EPA, EPA matchup adjustments using the historical opponent's *prior* metrics, success, explosive plays, drive yards, pressure, scoring form, capped margin and rest.
2. Full-season enriched team profiles are **not** directly used in older weekly games, because they would leak future games. Instead team profiles are reconstructed from individual prior games. Missing advanced values remain missing until fit-time imputation is estimated from training games.
3. Fixed-parameter multivariate ridge models (margin and total) compare an explicit score-only baseline to v0.3 advanced features and to a no-opponent-adjustment ablation, each refit using only earlier game-score targets.
4. Calendar-week tests report SU accuracy, margin MAE, total MAE and exploratory SU Brier with a training-residual Gaussian approximation; no invented ATS/O-U grades or FanDuel EV without authenticated pregame sportsbook quotes.

**CRITICAL:** This is *chronology-of-games* testing, but not an authenticated, leakage-free historical data test: the PBP/drive source can be revised after earlier games. Source manifest has \`historical_pregame_availability_verified=false\`. All results and status remain \`PASS_UNVALIDATED\`. No model selection is promoted and no betting picks are authorized by this exploratory comparison. Availability, weather and QB replacement weights have not been trained or validated yet.

The job saves research-only \`weekly_features.csv\`, \`research_backtest.json\` and \`heldout_research_predictions.json\` as ephemeral, ordinary Actions artifacts, not in Git history. The report identifies source SHA256 and retrieval time, game counts, tested weeks, and comparison metrics. Actual betting-line/closing-line value requires a separate authorized FanDuel source.

Next gate: preserve pregame-versioned advanced snapshots across future weekly refreshes, obtain adequately deep earlier-season labeled features/prior training, and run a true source-timestamp-verified walk-forward evaluation before any claim of model calibration or success.

## Step 1–4 implementation checkpoint

- **1 — Integrate advanced data:** prior-game 2026 EPA, efficiency, success, pass/rush split, explosive-play, QB-hurry proxy, drive-yard and opponent-aware EPA features included in an actual candidate prediction matrix. Opponent adjustment uses the opposing team's pre-existing profile when rating a past matchup, not the opponent's eventual end-of-season value.
- **2 — Weekly team profiles:** each team is rebuilt only from results on dates before a scheduled game. Calendar-day games are applied together to prevent same-day leakage. All current-game outcome labels are separated into `weekly_postgame_labels.csv`, while `weekly_pregame_features.csv` contains only pregame-shaped features.
- **3 — Enhanced score model:** separate margin/total ridge models, with training-only imputation and standardization, compared against score-only ridge and an opponent-adjustment ablation. No market-anchored ATS model or calibrated QB effect has been promoted.
- **4 — Walk-forward tests:** retrain every weekly window using strictly earlier games; collect straight-up accuracy, margin/total MAE and exploratory Brier, and preserve raw held-out retrospective comparisons for audit.

**Provenance restriction:** The input Parquet was retrieved later and is mutable. A chronology-only retrospective comparison is **not** a verified historical pregame feature backtest. Any measured improvements are exploratory and may not be used as betting recommendations. The full scheduled/manual intake must run successfully on the new code before its real-data metrics can be cited. Final artifacts are kept as 30-day GitHub Actions workflow artifacts only.

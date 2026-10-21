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

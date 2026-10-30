# CFB player-stat and player-prop research — October 30 2026

## Honest source and grading gates

The SportsDataverse `espn_cfb_player_box` release includes player-game
passing, rushing and receiving statistics, identified by ESPN athlete_id and
game_id. Each category is sparse; absence from a stat/category DOES NOT prove
zero, health or participation. ESPN team/game reconciliation and publication
timing are separate evidence requirements.

`player_prop_history.py` ingests a bounded 2026 asset with schema audits
and builds a player-game record with explicit missing categories.
`player_prop_walkforward.py` evaluates a simple last-four average against a
six-appearance recency-weighted model with a strict football-date embargo.
Both models grade the identical historical recorded-category games.

**Crucial:** This is not a true pregame availability backtest. Knowing
which player/category appears in a completed game is hindsight selection bias.
It excludes DNP/no-stat players; they are UNKNOWN and never zero-filled.
The 2026 table is a retrospectively revised release, not authenticated
point-in-time training data. No real prop quote history is included.
A model that improves a proxy MAE but loses on matched future player props
will be rejected.

## Next stages

1. Capture pregame *named roster eligibility*, player-ID mapping, expected
   role/usage and time-stamped injuries independent of future box scores.
2. Archive a pre-kickoff player-market universe, and preserve unknown/DNP
   outcomes according to market settlement rules.
3. Verify previous-player game form, opponent pressure, rushing defense,
   pass-coverage matchups, teams' predicted possessions and score script,
   conditioning only on observed-before-kickoff data.
4. Simulate correlated player attempts, targets/carries, catches, yards and
   touchdowns conditional on the SAME game pace, QB situation and team score
   context. Prior and transfer histories are shrunk, not guessed.
5. Collect authentic player prop lines/over-under prices from a provider
   with player props; audit ESPN player IDs and betting rules manually when
   names collide. Never fabricate book lines.
6. Grade proper over/under/tie probabilities using log-loss, Brier, accuracy,
   CRPS/coverage and calibration plus source/missingness; benchmark against
   market-implied no-vig probabilities where both sides are captured.
7. Promote only on independent prospective improvement. V03 remains active.

Sources:
https://js.sportsdataverse.org/docs/cfb/reference/loaders
https://the-odds-api.com/sports/ncaaf-odds

## Historical player PERFORMANCE data expansion

`player_prop_prior_seasons.py` now captures **2024 and 2025 football-season**
player-game passing, rushing and receiving box stats, joined to completed
ESPN game schedules using the season-year identifier. January 2026 bowl and
playoff results properly belong to the **2025 football season**. Player IDs
are matched within each game to ESPN home/away team IDs and missing categories
stay unknown rather than zero. The downloader reports distinct actual
provider-observation dates and SHA-256 source hashes.

An ESPN athlete ID seen on different teams in 2024 and 2025 is a **team-ID
association change**, not a verified transfer date or proof of roster
eligibility/availability. These previous-season rows provide research
priors, not independently frozen 2024/2025 pregame information.
The true sportsbook historical player-prop archive remains a separate
missing-data problem addressed by `player_prop_historical_market.py`.

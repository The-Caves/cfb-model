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

## November 5, 2026 — conserved opportunity simulation challenger

**Implementation:** `scripts/player_prop_team_budget.py` is an audited-input optional adapter to `scripts/player_prop_joint_simulation.py`, not the active PlayerForm. When an independently reviewed, complete historical **team** attempts ledger is supplied, it validates exact ESPN game/team identities, kickoff and Eastern football dates, outcome-known/capture/decision chronology, HTTPS provenance, at least three prior games **per side**, and matched prior observed team possession counts. It then samples the same game's possessions and verified historic team pass/rush attempt workload, applies a common pace factor, and distributes attempts across all modeled players rather than letting every player draw an unconstrained workload.

A Hamilton proportional allocator caps modeled pass attempts and rush attempts at the sampled team allowance, preserves a distinct nonnegative **unallocated player** residual, and caps modeled receptions against plausible completed-pass capacity. Player yardage and touchdowns are scaled/capped with the opportunity change. This is a research distribution, **not** a verified player participation model, target share model, calibrated simulator, or actual gamebook reconstruction. Missing receiving opportunities, DNP status, incomplete athlete records and unmodeled roles remain unknown. No fabricated opponent-adjusted workload or market lines are supplied.

**Strict fallback:** Without this reviewed team-attempt data, the original simulation runs with `team_attempt_budget_applied=false` and explicitly reports `PASS_NO_REVIEWED_TEAM_ATTEMPT_BUDGET_SOURCE`; it must never imply conserved attempts. The new `--team-attempt-budgets` CLI option is optional and requires an as-observed JSON source. **November 5 addition:** `scripts/player_prop_team_box_source.py` now translates the free ESPN-derived 2026 SportsDataverse `espn_cfb_team_box`, `espn_cfb_drives`, and `cfb_schedules` releases into *source-observed* team attempt and drive-count budgets, requiring both team rows and completed ESPN game/team identity. `scripts/player_prop_team_box_probe.py` and `.github/workflows/cfb-workload-source-probe.yml` perform a read-only source-coverage audit. This is a live-readiness source adapter, **not** proof of original publication dates, true drive-event completeness, verified pregame starters, or prospective model improvement. It is not yet connected to the scheduled website scoring or player-stat production process. The active V04 scores, PlayerForm projections, public site and archived picks remain unchanged. The ability to run the algorithm is **not** evidence of improved prop accuracy.

**Next deliverable, not another milestone split:** Source and independently audit complete prior FBS team pass/rush attempt totals linked to ESPN game IDs; feed those audited observations alongside pre-kickoff current expected lineups and actual source-dated historical possession counts. Freeze both the unconstrained and conserved forecasts simultaneously, then grade the same settled player-game pairs for passing/rushing/receiving MAE, unknown-player/DNP coverage, calibration and authentic prop market outcomes. Reject promotion if the constrained variant does not clearly improve; use one integrated drive/roster/volume scenario across all players rather than isolated highest-yardage candidates.


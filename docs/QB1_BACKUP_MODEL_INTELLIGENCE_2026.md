# QB1 versus backup: source-aware model improvement (October 28, 2026)

## Problem discovered in Delaware versus WKU

The original V03 scoring model fits 14 team aggregate features. It does **not** partition Delaware's previous offensive performance by the quarterback who generated those plays. Delaware's October 26 official preview explicitly reported that Nick Minicucci returned against Missouri State following two missed games, but did **not** confirm his October 27 start. The research source registry preserved this as RETURNED_FROM_INJURY_IN_PREVIOUS_GAME, yet V03 did not use it numerically. We must not silently turn a recently returned player into an authenticated next-game starting quarterback.

Sources:
- https://bluehens.com/news/2026/10/26/football-wraps-weekday-cusa-play-at-wku
- https://bluehens.com/news/2026/10/20/minicucci-ties-ud-single-game-passing-touchdowns-record-as-football-dominates-missouri-state-61-38

## Implemented phase A: real player-attributed history, with strict provenance

- scripts/qb_passer_history.py extracts each named passer from **accepted**, two-sided, completed 2026 ESPN game/PBP rows; a source must pass the existing final-score, opponent-ID and minimum-scrimmage-play gates. It saves per-game passer-tagged-play counts, EPA sums/counts, offensive pass-play share, observed missing-name coverage and the actual retrieval clock. It **does not** claim who started based on the most frequent passer.
- scripts/ingest_advanced.py now writes data/advanced/qb_passer_game_history_2026.csv and a quarterback attribution quality summary on every advanced-data ingestion. Historical source revision/publication times are unauthenticated, so retrospective reconstruction is never sold as genuinely frozen pregame evidence.
- prior_qb_form() can condition prior QB-specific pass EPA on a separately established current starter, compare with other observed passers on the same team and return NULL when samples are too small. It does not invent a point penalty.

## Implemented phase B: game-specific model-facing QB role context

- scripts/qb_role_features.py reads actual pregame upcoming matchups, the passer history, the curated official gameweek return source and (optionally) the verified Step3C pregame QB starter evidence.
- Separately records historical **season leading passer proxy**, previous-game passing-play leader proxy, recent passer-switch indicator, dated official QB-return context, and fully confirmed current game starter **if** it exists. The historical passer proxy is **not a verified depth-chart QB1**.
- If there is no verified upcoming starter, the conditional player-specific profile remains unavailable; missing QB1 is UNKNOWN, not backup and not healthy. The October 26 Delaware source may flag an officially observed prior-game return, but never asserts the current game's starter or a made-up expected points shift.
- A strictly verified current-game starter unlocks a player-conditioned statistical diagnostic, still research-only. An appropriate live model adjustment requires separately trained, prospective and opponent-aware player replacement coefficients.

## Testing

Unit tests check mixed-QB passing usage, untagged passer plays, fail-closed score conflicts, before/after decision time boundaries, game-specific official returns versus actual starter confirmation, past-only conditional passer EPA, inadequate sample thresholds, duplicate PBP player evidence and absent data. CI also tests entire existing baseline/scheduled workflow.

## Next milestones before the model actually changes its picks

1. Continue expanding source-reviewed QB1/QB2/QB3 depth charts, separately timestamped actual starters, and independently observed previous-game participation for every available school. A 2026 source list for 138 schools is not evidence of 138 verified QB1s.
2. Preserve season QB1 versus backup/multiple-QB samples and link context to observed offensive performance, opponent pressure, EPA, completion quality and game outcomes as-of; do not assume the difference is causal.
3. Create a QB-specific candidate forecast that uses *only* independently captured, game-time-valid expectation evidence, compares against no-QB V03 and the recency/latent shadow model on the **same** games, and rejects undercovered historical periods. Unknown starter should produce scenario uncertainty or PASS, not a guessed adjustment.
4. Obtain enough prospectively verified QB1→backup→QB1 changes across teams before estimating/validating replacement impact. Promotion requires independent paired out-of-sample gains; V03 remains live for now.

No QB adjustments are claimed on the public site from these source/audit changes. All forecasts, frozen predictions and existing bet-readiness policy remain unchanged.

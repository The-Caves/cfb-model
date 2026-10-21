# Step 5 readiness — timestamped sportsbook markets and walk-forward evaluation

**Status:** Proposed interface and acceptance tests. No sportsbook provider, live betting feed, or historical market database has yet been selected/validated. This file contains no credentials, private account information, or personal details.

## Purpose

The 2026 context ingestion and partial QB-source coverage are suitable as explicit research inputs **only with as-of provenance and UNKNOWN fallbacks**. Step 5 introduces historical and prospective moneyline, spread, and total prices, before any claim of an ATS/O-U calibrated prediction engine. Stage failures must not turn missing odds into fabricated or zero-valued inputs.

## Minimum input schema (one book, event, market, and timestamp)

- `season`, `espn_game_id`, canonical home/away team IDs and verified opponent mapping
- `bookmaker`, `provider_event_id`, `provider_market_id` and source URL or licensed API identifier
- `market_type`: `SPREAD`, `TOTAL`, or `MONEYLINE`
- Market selection (home, away, over, under), signed home spread **from the home perspective**, total points, and American or decimal odds; preserve both raw and standardized price
- `source_published_at_utc` (if available), `retrieved_at_utc`, `snapshot_asof_utc`, `kickoff_utc`; all timezone-aware
- `is_live_in_play`, market status, source revision ID/hash, provider fetch status and rejected-row reason
- `quote_role` (raw observed quote, opening, closing); opening/closing may be marked only from actual time/venue evidence, never guessed from a single late download

## Hard validation rules

1. Reject or quarantine ambiguous, duplicated, FCS-vs-FBS misjoined, postponed, neutral-site-conflicted, stale, mismatched and post-cutoff market records.
2. Require exact team and game-event correspondence, opening and closing books clearly identified and no cross-book synthetic line movement.
3. A line observed at 6 PM cannot be used for a hypothetical 3 PM pick, even if the closing number looks more accurate.
4. Prices and spreads are separate: ATS win probabilities must be evaluated against a timestamped selection-side quote and its vig, not against retrospectively reconstructed consensus.
5. Track provider omissions/outages and cancellation/void outcomes. Never treat absent market data as evidence of market agreement.
6. Version the normalized schema, raw snapshot hashes, processing code, training cutoff and explicit feature-release timestamps.

## Planned implementation phases

**5A — source audit:** Evaluate licensed or public historic market access; verify terms, API quotas, date coverage, opening and closing availability, bookmaker consistency and 2025/2026 overlaps. Choose a legal reliable provider only after independent checks. If reliable history cannot be obtained, mark historical ATS/O-U evaluation blocked.

**5B — prospective ingestion:** Schedule bounded API fetches, maintain raw checksum and UTC observation history, preserve line movements and bookmaker attribution. Store quote snapshots separately from late-revised ESPN play-by-play research.

**5C — as-of joins:** Match current and past games to prices only if captured and published no later than prediction cutoff. Build leak tests for post-kickoff lines, corrected scores, recency/season handling, reschedules and delayed player availability.

**5D — evaluation:** Implement chronological walk-forward SU, ATS and O/U forecasts with a reproducible baseline, confidence/pass thresholds, selected-side vig handling, calibration, distributional totals, and frozen previous-version results. Train on historical data with 2026 profiles kept 2026-only and earlier years used solely as documented priors.

**5E — model promotion:** Never enable automated bet recommendations or label research leans “model picks” until real source coverage, leakage tests and out-of-sample evaluation justify the model. `PASS_UNVALIDATED` remains the default.

## Step 4 inputs inherited by Step 5

- `state/latest.json.gz` and frozen pregame snapshots with verified fetch/collection cutoff
- `state/qb_review_latest.json` and dated QB review history, including explicit national-source gaps
- Official availability is player-status provenance, not medical diagnosis or independent QB starter proof
- Weather: actual prospective forecasts, not retroactive past-weather observations
- Approximate travel: geodesic city-centroid miles, never precise team itinerary

Read `README.md`, `docs/STEP4_HANDOFF.md` and latest Actions/manifest results before implementation. This file is a public engineering plan, not proof that the Step 5 dataset exists.

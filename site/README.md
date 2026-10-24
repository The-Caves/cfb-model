# 2026 CFB research dashboard

This is a mobile-friendly front end to real, frozen 2026 college-football model research forecasts. It is **not** a validated betting recommendation engine, and displays `PASS_UNVALIDATED` until the model has adequate leakage-safe out-of-sample evidence. It does not fabricate moneylines, spreads, totals, QB starters, injury diagnoses, or graded outcomes.

## What is built

- The responsive website is `site/index.html`: an Eastern-time day navigation strip, chronological kickoffs, searchable teams and ESPN game IDs, configurable sort (time, largest ATS/total disagreement, alphabetical), matchup filters (market coverage, home/away ATS, over/under, reviewed QBs), projected scores, model total and **uncalibrated** home-win estimate, conditional market-comparison cards, provenance and performance panels.
- The exporter `scripts/site_export.py` reads the most recent pregame archive from `context-state/research_2026/forecast_index.json` and the indexed `forecasts/YYYY/MM/DD/run-*.json.gz` file.
- It validates the original forecast record with `scripts.personnel_forecast.verify`, compares the index checksum and record identity, rejects surprising sportsbook market data, and excludes games which kicked off before site publication. It keeps the exact originally frozen forecast capture timestamp.
- The export payload is schema v2 in `site/data/dashboard.json`. It exposes only public game identity, genuine numeric projections, 0–2 reviewed-QB and team-report coverage counts, original provenance, and explicit model limitations. Private sportsbook vault information and player-level detail are not exported.
- `tests/test_site_export.py` tests output safety, missing odds, time gates, index checksum, path traversal and compressed forecast reading.
- `.github/workflows/cfb-site.yml` builds and validates the dashboard on selected pushes, scheduled checks and manual runs. It also embeds the JSON into the generated HTML so the downloadable ZIP includes a self-contained **offline-viewable** page. No paid infrastructure or AWS is needed.


## Actual public market lines and experimental ATS / O-U comparisons (October 24)

`scripts/site_market.py` fetches free, publicly visible pregame **ESPN scoreboard** odds for future dates (bounded to 15), normalizes the payload via the existing `scripts.free_market_capture.normalize`, and joins by ESPN game ID, both team names, kickoff and source observation time. It displays the **actual provider reported by ESPN** (which may be DraftKings, ESPN BET or another provider, not necessarily FanDuel).

- Valid signed home spread requires explicit and contradictory favorite flags; unsigned-only spreads stay unavailable. Valid totals must be finite, positive, and inside expected football limits. Unknown provider, mismatched game, missing line, and post-kickoff quotes are not promoted.
- The frozen model forecast is **not refit** when a later current market quote arrives. The displayed ATS side is the sign of `frozen_model_home_margin + observed_home_spread`; the totals side is the sign of `frozen_model_total - observed_market_total`. Exactly equal is `PASS`. Both are unvalidated research **comparisons** to the displayed observed market, not claims that sportsbook prices were known at the original forecast time.
- Every quote shows its provider and UTC observation timestamp, displayed in ET, and clearly states the **upstream publication timestamp is not independently authenticated**. Never call the prices opening or closing odds. Historical ATS/O-U backtesting still needs independently proven as-of market evidence.
- If any scheduled fetch fails, the build records its error and missing quote values remain unavailable; it does not invent prices or suppress the clear missingness state. Do not claim future dates' quotes exist merely because the ESPN API returned a successful response.
- The dashboard pipeline's market export and comparison logic have standalone tests in `tests/test_site_market.py`; the website's generated JSON is checked before publishing.

**Verified live checkpoint:** [GitHub Actions run 40102895593](https://github.com/The-Caves/cfb-model/actions/runs/40102895593) passed build tests, model/archive export, free public source capture, safety validation and self-contained website packaging. It processed **102 future model projections** and found **56** observed, source-matched games with valid spreads and totals across seven successfully fetched dates, with no fetch errors in that run. `PASS_UNVALIDATED` remains the model status. Market coverage and prices will change on later runs; these counts are a single timestamped observation, not permanent coverage claims.

The overall model does **not** yet forecast player propositions (passing/rushing/receiving/receptions) or calculate player-prop edges. There is no validated individual-player usage/rate distribution model or reliable prop quote pipeline. A separate model milestone is needed rather than using team score forecasts to fabricate player bets.

## Opening the website today

The GitHub Actions `CFB Research Dashboard` workflow creates an artifact called `cfb-website-preview-<run number>`. On a phone, download the ZIP from the most recent successful Actions run, extract it in Files, then open the HTML file. The exported HTML has its data embedded, so it does not require GitHub Pages for an offline preview. Note that its static forecasts will not update while the local file is open.

### Optional public web address

Earlier project instructions requested a private preview. **GitHub Pages creates a publicly accessible website**, so the workflow does not enable it automatically. If the owner chooses to make this research site public:

1. Go to repository **Settings > Pages**.
2. Under **Build and deployment > Source**, select **GitHub Actions**.
3. Open **Actions > CFB Research Dashboard > Run workflow** or let its next scheduled build complete.
4. Confirm an actual successful Pages deployment. The expected standard address, once live, is `https://the-caves.github.io/cfb-model/`.

Do not call that address live before verification. The Actions deploy job records when Pages is disabled; the preview ZIP remains available regardless. For a restricted-access website, use an authenticated hosting provider instead of public GitHub Pages.

## Remaining model limitations

Projections are **research outputs**, not calibrated bets. National game-specific QB1 evidence and availability are incomplete. The 2026 historical play-by-play availability times are not independently attested. Authenticated historical FanDuel lines are unavailable. Live public ESPN pregame sportsbook observations can now support clearly labeled **conditional research comparisons** where matched, but not authenticated historical ATS/O-U validation; trustworthy performance claims require genuine predecision markets and paired verified outcomes. Keep these limitations visible in the public site.

For official personnel-source verification and milestone exit rules, see `docs/MILESTONE_2B_OFFICIAL_SCHOOL_SOURCES.md`. Update this README and the milestone record whenever the publication contract or evidence changes.

## Game-specific quarterback labels and official availability (October 24)

QB names shown as `RECENT_GAME_PASSER` are only past-game statistical context. **Starter not confirmed** stays prominent until the independent, time-safe `CONFIRMED_OFFICIAL` review gate passes. Named players, official report statuses and cited source links appear on each game widget. The game can be filtered by confirmed QB, names available, or official QB status uncertainty. The headline `Model pick · experimental` means genuine computed projections, **not** validated betting picks.

A supplementary, read-only official conference availability overlay runs in `scripts/site_availability.py` after `scripts/site_qb.py`. It matches timestamped public SEC, B10, ACC, B12 reports to the exact scheduled game before displaying per-QB `OUT`, `QUESTIONABLE`, `AVAILABLE`, etc. A missing or rejected report remains unknown, not healthy. Official availability and current name overlays **do not retroactively adjust** the existing frozen forecast; the live model still fits 14 base features and must pass leakage-safe validation before a new QB-weighted model can be promoted. Progress and acceptance blockers are in `docs/QB_WIDGET_SOURCES_2026.md`.

## QB1–QB3 chart ranks on every upcoming game (October 24)

Every ranked QB in a matchup is shown as `QB1`, `QB2`, or `QB3` based on a dated 2026 Ourlads college-football depth chart, with an outbound source link and its update date. `QB1` means **first on the third-party depth chart**, not guaranteed to start today. Real, date-matched *official* availability is overlaid beside the named player (for example, Taylor `QUESTIONABLE` at Mississippi State) and confirmed game-specific starter evidence is a separate stronger source class. A player whose only evidence is last week's box score remains labeled as last week's passer, not a QB1.

Verified [successful final site build 40108010413](https://github.com/The-Caves/cfb-model/actions/runs/40108010413): all 102 upcoming matchups have both teams' chart-rank slots, covering 135 distinct teams and 570 listed quarterback entries. This does **not** mean 102 verified starting-QB matchups, and the model is **not** injury/replacement adjusted simply because names/ranks are displayed. `scripts/site_depthchart.py` and `tests/test_site_depthchart.py` implement source validation and daily caching.

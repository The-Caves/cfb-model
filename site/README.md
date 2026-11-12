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

## Public dashboard and offline preview (October 29)

The public GitHub Pages dashboard is live at **https://the-caves.github.io/cfb-model/**. Its source code, frozen model forecast and research disclosures are published via `.github/workflows/cfb-site.yml`. GitHub Pages is public, not a private/authenticated site.

Each successful workflow also builds a standalone zipped HTML preview with its then-current data embedded: `cfb-website-preview-RUNID`. Opening that exported HTML offline will not refresh lines or games.

### Compact UI version

The redesigned game cards use two team rows, with model-projected score, one compact **QB rank + player name** line and its evidence caveat. Three-deep depth charts, medical availability and link provenance remain available in a secondary expandable **QB depth, availability & sources** panel; **Team scouting** remains separately expandable with run/pass/defense and turnovers. Never relabel a statistical passer or third-party depth-chart QB1 as an official starter.

The color palette is a restrained navy/slate/teal design with a responsive mobile-first header. Where the exact ESPN game ID, opponents, kickoff and team metadata match, source-labelled school color and a logo URL from ESPN's `a.espncdn.com` CDN are displayed. Logos are **third-party trademarks and art** belonging to their respective owners; the ESPN API does not itself grant license to redistribute or repurpose them. Images are hotlinked to their source, not saved or rehosted, and a neutral text monogram renders if any image fails. Do not generate fake official color palettes. School branding is an optional display enhancement, never a model signal.

The original archived forecast model and market source safeguards are unchanged by this redesign. New tests in `tests/test_site_ui_compact.py` and `tests/test_site_team_branding.py`, plus a JavaScript syntax check, protect the mobile layout's data contract and fallback behavior.


## Cumulative prospectively archived performance (October 29)

The Performance tab is populated by `scripts/site_performance.py` during every successful dashboard build. It reads archived, independently observed **final outcomes** and append-only pregame records from the `context-state` branch, verifies source checksums and refuses changed fixture identities. This corrects the original site placeholder `prospective_records: {su: null, ats: null, ou: null}` and provides cumulative win/loss/push records, actual scored-game count, home-margin and total MAE, weekly summaries and recent finished game-by-game grading.

**Separate decision populations:** SU is based only on uniquely selected, frozen 24-to-72-hour preregistered `Step3G` forecast grades (`forecast_grades_index.json`). ATS and totals are graded from the **earliest captured pre-kickoff website selection per exact game/market** (`site_board_snapshots/index.json`), matched to independently archived ESPN final scores (`market_finals/index.json`). Since the website sometimes displays a later-observed market quote than the original model forecast, these are **as-displayed comparisons** and *not* claims of synchronized preforecast sportsbook prices. More than one website build, refresh, line or provider must never multiply a game outcome. Unmatched finals remain ungraded; a missing market is not interpreted as a loss, win or push.

All values remain `PASS_UNVALIDATED`, no net profits or real wagers are inferred, no grade changes the original model coefficients, and historic bookmaker publication clocks remain unauthenticated. Real future results can enter subsequent builds after independent outcome settlement; do not change a published grade retroactively. CI covers deduplication, source hashes, missing finals, late quotes and preservation of the original future predictions.

## Remaining model limitations

Projections are **research outputs**, not calibrated bets. National game-specific QB1 evidence and availability are incomplete. The 2026 historical play-by-play availability times are not independently attested. Authenticated historical FanDuel lines are unavailable. Live public ESPN pregame sportsbook observations can now support clearly labeled **conditional research comparisons** where matched, but not authenticated historical ATS/O-U validation; trustworthy performance claims require genuine predecision markets and paired verified outcomes. Keep these limitations visible in the public site.

For official personnel-source verification and milestone exit rules, see `docs/MILESTONE_2B_OFFICIAL_SCHOOL_SOURCES.md`. Update this README and the milestone record whenever the publication contract or evidence changes.

## Game-specific quarterback labels and official availability (October 24)

QB names shown as `RECENT_GAME_PASSER` are only past-game statistical context. **Starter not confirmed** stays distinguishable until the independent, time-safe `CONFIRMED_OFFICIAL` review gate passes. A compact QB name and provenance label appear on each card; full chart ranks, official report statuses and cited source links live in the collapsed QB details panel. The game can be filtered by confirmed QB, names available, or official QB status uncertainty. The headline `Model pick · experimental` means genuine computed projections, **not** validated betting picks.

A supplementary, read-only official conference availability overlay runs in `scripts/site_availability.py` after `scripts/site_qb.py`. It matches timestamped public SEC, B10, ACC, B12 reports to the exact scheduled game before displaying per-QB `OUT`, `QUESTIONABLE`, `AVAILABLE`, etc. A missing or rejected report remains unknown, not healthy. Official availability and current name overlays **do not retroactively adjust** the existing frozen forecast; the live model still fits 14 base features and must pass leakage-safe validation before a new QB-weighted model can be promoted. Progress and acceptance blockers are in `docs/QB_WIDGET_SOURCES_2026.md`.

## QB1–QB3 chart evidence (October 24 collection, October 29 compact display)

QB1–QB3 chart ranks for each matchup are available inside a collapsed source panel based on a dated 2026 Ourlads college-football depth chart, with an outbound source link and its update date. `QB1` means **first on the third-party depth chart**, not guaranteed to start today. Real, date-matched *official* availability is overlaid beside the named player (for example, Taylor `QUESTIONABLE` at Mississippi State) and confirmed game-specific starter evidence is a separate stronger source class. A player whose only evidence is last week's box score remains labeled as last week's passer, not a QB1.

Verified [successful final site build 40108010413](https://github.com/The-Caves/cfb-model/actions/runs/40108010413): all 102 upcoming matchups have both teams' chart-rank slots, covering 135 distinct teams and 570 listed quarterback entries. This does **not** mean 102 verified starting-QB matchups, and the model is **not** injury/replacement adjusted simply because names/ranks are displayed. `scripts/site_depthchart.py` and `tests/test_site_depthchart.py` implement source validation and daily caching.

## 2026-10-30: PlayerForm R1 compact player-stat outlook in each game widget

The **score model remains the original frozen V03 archive**. Before the site
publishes, `scripts/site_player_props.py` now source-matches actual ESPN
athlete game boxes, prior-season recorded athlete IDs and real ESPN
game/team/kickoff identities, then attaches a separate **PlayerForm R1**
experimental player-stat estimate. The one-look widget shows up to three
conditional player-stat cards: passing, receiving and rushing yards. A
collapsed details view lists up to six candidate rows across both teams.

Components: last-four 2026 observed player games; 2025 shrinkage after
only one or two 2026 appearances; conservative .25 capped prior-opponent
allowance modifier, when a past-only source qualifies. The previous-season
and defensive interactions were individually screened, NOT jointly
calibrated prospectively. Their combination is strictly **research-only**.

Player presence in past recorded games is **NOT confirmed participation** for
the upcoming matchup. An OUT/OUT_FIRST_HALF/SUSPENDED/DOUBTFUL QB from the
official overlay is suppressed from opening-game QB projection. A named
candidate player still is not a guaranteed current starter or healthy.
No actual player-prop sportsbook line is attached, and any Over/Under
probability remains null. If ESPN data is missing, the card shows a small
unavailable state and does not create fake odds, scores or players.

The game scoreboard, V03 archived projection sha, ATS selection, totals,
performance grades and current market remain unchanged by the player module.
Source failures are explicit and the data may be newer than the underlying
V03 freeze. Player names can be searched, and there are separate filters for
available player stat projections. Mobile teasers show two compact chips and
the rest remain one tap away.

The score-model promotion gate remains independent: challenger evidence
has not justified replacing V03, despite development of a separate
PlayerForm R1 experiment.

## 2026-10-30: All-position official availability and recorded workload

The structured conference availability source was always broader than QB,
but the site previously surfaced only QBs. The current pregame overlay now
preserves all published positions (RB, WR, TE, OL, DL, EDGE, LB, DB, etc.)
in each game's `player_availability_home/away` fields; the QB-specific
display remains unchanged. A player without a report is **UNKNOWN**, never
declared healthy or starting.

An official OUT, OUT_FIRST_HALF, DOUBTFUL, SUSPENDED or contradictory
availability status prevents a full-game yardage preview for the matched
player. QUESTIONABLE/GAME_TIME_DECISION/LIMITED remain conditional forecasts
with a clear official status label, never converted to an unsupported
playing probability. These are published designations, not diagnosis.

`player_prop_workload.py` computes player shares of *recorded team*
passing attempts, rushing attempts, and catches, only from prior observed
box games. Recorded catches are NOT targets, and none of these are snap
shares. Receiving shares require reconciled QB completions versus total
player receptions; missing categories and unlisted players are not zeros.
The public game card shows a compact role-share label when available.
These workload indicators do **not yet** alter yardage forecasts. A
retrospective same-player recorded-game competition tests their statistical
usefulness against the previous-four player workload baseline, with
same-football-date withholding and explicit source-timing caveats.
Live V03 scores and PlayerForm yard projections remain unpromoted.

## Prospective player-stat performance archive (same-day game/week)

Each successfully built PlayerForm game board now also freezes its exact
conditionally displayed research-yard prediction before kickoff into
`context-state/research_2026/player_projection_snapshots/`. It includes the
player/game/metric ESPN ID, original score V03 hash and model ID, role-share
and official availability evidence, and the observation/capture times.
Prior snapshots are immutable and cannot be quietly replaced by postgame
forecasts. This is essential groundwork for credible independent later
per-player model performance grades. Nothing in this mechanism adds a real
sportsbook prop line, a market over/under selection or an injury diagnosis.

## Prospectively graded PlayerForm yard performance

`scripts/player_prop_prospective_stat_grade.py` now joins immutable
pre-kickoff player/game/metric snapshots with **freshly observed** completed
2026 ESPN schedules and recorded athlete box categories. Select earliest
eligible pregame model prediction for each player/game/stat, never a chosen
later update. Missing players, missing stat categories, incomplete games,
and unverified identity matches are **not recorded zeroes**. An explicit
zero from a recorded stat category IS gradeable.

Since October 31, each new displayed PlayerForm forecast also stores the
same-source recent-four player yard baseline separately. Only frozen
baseline values are paired on the same settled athlete-game cohort.
Earlier snapshots without this baseline have no invented comparison.
A source-verified latest grade summary is published on `context-state`,
and the site's Performance tab shows sample size, yardage MAE and paired
baseline differences, with no sportsbook or ROI claims. The grade is
conditional on a player having a recorded stat category; it does not
measure correct injury, absence, starter or player-prop betting predictions.

## October 31: first real prospective grading checkpoint

The first successful PlayerForm settlement found **11 valid recorded
stat-category outcomes** (3 passing, 4 rushing, 4 receiving) from
**668 unique** originally frozen game/player/stat predictions. The
conditional mean absolute errors were 82.0, 30.025 and 17.675 yards
respectively. **These samples are too small to validate any model
advantage**, and older forecasts have no paired frozen recent-four
baseline; this is an audit checkpoint, not a win-rate claim.

The grader and site build can run concurrently. The site now refreshes
`context-state` immediately before reading the latest player-grade
record, then asserts the displayed grade matches the source's observed
timestamp and sample count. Historical prediction snapshots remain
separately checksum-verified and immutable. The read-only UI grade is
not sportsbook prop performance.

## October 31 score-card visibility correction

The V03 home-bias quarantine briefly replaced the projected final score
on each game card with a dash, reducing the usefulness of the dashboard.
A follow-up now displays an **explicit hybrid illustrative final score**.
The independent opponent R1 score-margin model is combined with the
original separately frozen V03 **total only**:

- illustrated home points = (V03 total + R1 home margin) / 2
- illustrated away points = (V03 total - R1 home margin) / 2

These are mathematical score illustrations, **not independently trained,
jointly calibrated, or prospectively validated game-score forecasts**.
The final-score hints and game header label them as hybrid research. If
the margin and total cannot form a nonnegative score, the score remains
unavailable rather than inventing points. Frozen V03 original scores,
ATS selection quarantine, research opponent-rating margin, prospective
archive receipts, and player stat projections remain unchanged.

## October 31: Correct underlying opponent-adjusted scoring (V04, research)

The original V03 score model learned a very large false home advantage
from an unbalanced 2026 nonconference schedule. V04 replaces that scoring
architecture with two separate, directly source-trained components:
(1) opponent-adjusted home/away team strength difference and a
conservatively regularized 2.5-point venue prior;
(2) team offense-versus-defense expected scoring, with explicit 2026
past-only 28-day recency decay, limited 70-point single-team targets,
regularization, and no bookmaker fit. Two directly estimated quantities
form coherent projected points for both teams, margin and total.
Unlike the earlier R1/V03 display workaround, the V04 predicted **total
is fitted directly from historical team scores, not recycled V03**.

The reproducible original October 31 2026 research source achieved
**301 matched games across 5 weekly past-only folds**: V03 margin
MAE 15.890, totals MAE 13.700 and home pick frequency 97.7%;
V04 margin MAE **13.205**, totals MAE **13.480**, home
selection 68.1%. V04's mean signed home margin error was +0.23
points versus +10.41 for V03. This is a chronological retrospective
ablation rather than authenticated earlier-publication history and
does not establish betting success.

The public site's verified-source overlay now includes V04 directly
trained final scores on game cards where the exact-run original
training inputs pass checksum, team, venue and kickoff checks. V03
remains quarantined and its original immutably archived picks are
unmodified. V04 is labeled experimental, not prospectively promoted,
and no V04 ATS picks/edge/profit claims are generated. Where there is
no V04 source-matched prediction, fall back to the clearly labeled
R1/V03 illustration or show unavailable. Each source-matched
V04 pregame score is saved as its own separate research field in
the game's site decision receipt for future genuine prospective
competition against V03.

## November 5, 2026: streamlined game center, lifetime grades and Live tab

The primary matchup card is intentionally small: game time, the two projected score lines, the **V04 current displayed research** winner/total and concise actual-market comparisons. PlayerForm conditional stat estimates, source-reviewed injury/QB context, advanced scouting, and V05 alternatives remain accessible under **Player outlooks, injuries & scouting** but are hidden until expanded. The page uses separate purple model, blue market, teal live-score and amber injury/uncertainty treatments. No inference or scoring coefficients were changed by these interface updates.

**Do not reset performance when the displayed model changes.** The Performance tab still reads the immutable cumulative `context-state` archive via `scripts/site_performance.py` and `scripts/site_player_stat_performance.py`. V03 frozen original predictions, V04 challenger selections, V05 shadows and PlayerForm stat grades remain separate research cohorts. V04 is the latest eligible model shown on pregame cards; V05 and V07 are still non-promoted experiments. Displaying a higher version number must never imply proven forecasting superiority.

The dedicated **Live** tab obtains only ESPN `state=in` actual game scores from `scripts/site_live.py`. It matches game ID, actual teams, kickoff and source capture time to the latest **immutable V04 pre-kickoff website snapshot** if one exists. A missing or invalid pregame snapshot is explicitly shown as unavailable, never fabricated from a post-kickoff forecast. The tab intentionally does **not** show an in-game win probability or recomputed ATS/total selection: these require a separately trained, calibrated, prospectively frozen in-game model. It does **not** change the original pregame model data or lifetime performance.

The static GitHub Pages site publishes score snapshots at build time, not continuously streaming ESPN data. Extra game-night workflow clocks target roughly 30-minute refreshes (subject to GitHub Actions queue and source access); the Live tab checks for a newer published dashboard every two minutes while visible and provides a manual refresh button. Each card/source panel shows ESPN observation time. Scores may be stale between builds, and the capture can be unavailable. No AWS, paid data feed or new billing service is used.


## November 11, 2026 — Fieldhouse mobile UI and pregame bookmaker prices

The game desk now uses a brighter navy/teal/blue palette, high-contrast V04
score projections, highlighted model favorite, three quick bookmaker
comparisons, date strip, quick-filter buttons, search, and improved responsive
navigation. The one-time experimental-model disclosure remains available
without filling every card with repeated warnings; deep QB, player, scouting,
model alternatives, source clocks and evidence limitations remain expandable.

* **Moneyline / spread / total:** `scripts/free_market_capture.py` accepts
  actual public ESPN scoreboard odds from the source-named bookmaker. Signed
  spreads still require explicit favorite flags; source-provided American
  moneylines require both home/away prices between ±100 and ±10000. Zero, EVEN,
  missing sides, malformed prices and inferred prices are not accepted.
  `scripts/site_market.py` exposes the same-provider original quote as
  `market_home_moneyline` and `market_away_moneyline`, or null when absent.
* **Model forecast is not a sportsbook quote:** The score-based V04 pregame
  winning side is a directional prediction, not a calibrated moneyline price.
  The V04 ATS and O/U **decision policy** continues to return a conspicuous
  `PASS` when confidence, market comparability, or QB safety gates fail.
  V03's quarantined favorite must not accidentally appear as a V04 pick.
* **Pregame snapshot in Live:** Pre-kickoff archived model scores, winner,
  spread/totals research selections, and original book line/quote time remain
  visibly separate from the latest ESPN scoreboard state. When the original
  model favorite is trailing, the UI labels that fact clearly but **does not**
  claim the live win probability or in-play model has changed. Archived
  moneylines are kept only when originally observed before kickoff.
* **Bookmaker limits:** ESPN's no-key public scoreboard can return DraftKings,
  ESPN BET or another identified quote provider. It is not a direct FanDuel
  integration, a guaranteed bookmaker feed, a reliable opening/closing
  sportsbook archive, or a live in-play price source. Empty fields stay
  empty. A dedicated authenticated sportsbook provider and independently
  timed live odds are **future work**, not silently fabricated.
* **No score-model change:** All changes are interface and observed-market
  presentation only. Archived picks, grade cohorts, model coefficients,
  settlement status, source limits, and `PASS_UNVALIDATED` remain unchanged.

Validated by `test_site_ui_compact.py`, `test_site_market.py`,
`test_free_market_capture.py` and `test_site_live.py` in the GitHub
workflow. Any individual build must still pass and deploy before the current
Pages URL is considered updated.

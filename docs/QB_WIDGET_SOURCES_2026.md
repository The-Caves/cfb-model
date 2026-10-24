# 2026 QB identity widgets — evidence layers and source-time rules

**Date:** October 24, 2026. **Status:** implemented and cloud-tested as a research-only **display overlay**. This does **not** complete national game-specific starting QB verification or validate QB injury/replacement scores. No sportsbook pick is promoted.

## The problem

The latest verified `context-state/state/qb_history_latest.json` had **204 2026 pregame team slots, zero `CONFIRMED_REVIEWED_PREKICKOFF` starters**. The manual review file (`data/manual/qb_starter_evidence_2026.csv`) remains header-only. Before this upgrade, the site reduced this to `QBs 0/2`, leaving users without player identities.

The upstream model deliberately **does not** call a season passing leader or a team's last week's passer a confirmed starter. This is important when a starter gets hurt, benched, or replaced.

## Implemented 2026 website source hierarchy

The dashboard's `scripts/site_qb.py` runs after the existing frozen model forecast export and free ESPN market comparison. It overlays **two** named player statuses onto every future game. It does **not** refit model coefficients or modify frozen historical feature values.

1. `CONFIRMED_OFFICIAL`: comes **only** from a timestamped, checksum-validated `context-state/state/qb_history_latest.json` observation with `CONFIRMED_REVIEWED_PREKICKOFF`. It must match the exact ESPN ID, opponent, kickoff, and official reviewed source and must have been observed before kickoff. Display includes player name and official source URL.
2. `RECENT_GAME_PASSER`: fallback for an unconfirmed school. Match a school's ESPN ID/name against a *previously completed* 2026 game within a 22-day window, fetch that completed game's ESPN box score, and display its first listed passing athlete with a **last-game date and source link**. This is a past-game statistical player, **not** proof that he started that past game, is healthy, is QB1, or will start the upcoming game. Label reads **“Last game passing leader · NOT confirmed to start.”**
3. `CONFLICT_REVIEW`: preserves conflicts in existing reviewed official QB evidence; never promotes an identity.
4. `UNKNOWN`: no usable player identity or previous game. Unknown is not assumed healthy, absent or cleared.

The website shows separate away/home QB identity panels, clearly described provenance and links. It has search by player names and filters for both officially reviewed QBs, both named prior-game passers, and missing names. The official `QBs N/2` counter continues to count **only** independently confirmed game-specific starters.

## Evidence quality and reproducibility safeguards

- The ESPN team `/leaders` endpoint was empirically found to return empty JSON for 2026 CFB in live Actions; it was **not** used to infer starters.
- ESPN previous-week scoreboards do not include directly accessible QB leaders at competitor level; the verified `/summary?event=<ESPN ID>` route returns per-team passing box scores and athlete names. Both scores and team identity must match before accepting this **past performer**.
- Only games already marked *completed* and with kickoff before the display capture may be used as historical context. Team IDs, exact names and ESPN game event IDs must match; futures or stale/ambiguous matches are not candidates.
- Last-game passer information is **observed now** and separately sourced; it does not claim that the information was published before the previously frozen forecast. Never backfill post-decision QB context into a prior training fold or graded prediction.
- Direct HTTPS source URLs are shown for display status; news, depth charts and team availability reports still do not independently prove the specific upcoming starter.
- This current pipeline does **not** assign injury/replacement penalties, retrain QB-aware features, or change `PASS_UNVALIDATED`.

## Live verified checkpoint

[CFB Research Dashboard run 40104610994](https://github.com/The-Caves/cfb-model/actions/runs/40104610994): website **build passed**, with 10 focused QB source/UI integration tests; current 2026 model archive yielded 102 games (204 team slots). ESPN exact IDs matched **204 slots**, and 135 distinct schools had usable previous-game passing performers. The website displayed names in **204 of 204** slots (some repeated for the same team across multiple upcoming games) with **zero official confirmed starters** and zero QB source fetch failures on that snapshot. This is *player identity visibility*, **not 100% QB starter certainty**.

## Next material QB milestone

To raise true starter-confirmation coverage rather than merely show recent players:

1. In Milestone 2B, verify actual official football game notes and embedded depth charts across all 138 schools; record **candidate QB1** separately from confirmation, with exact season/game relevance and document source time.
2. Monitor official school releases and on-record coach statements. Put exact player/game/statement and reviewed publication, capture, approval timestamps into `data/manual/qb_starter_evidence_2026.csv`. Gate via `scripts/qb_starter_review.py`; never auto-upgrade RSS headlines, depth-chart rank or passing statistics.
3. Use official availability reports to flag contradictions such as an announced starter marked OUT; a purported backup remains *not confirmed* until separately sourced.
4. Refresh near kickoff. If no legitimate official declaration exists, display a **projected** starter only if a verifiable, contemporaneous projection source is added with its own label, provenance and acceptance tests; do not quietly call it confirmed.
5. After enough independently observed QB changes and paired final games exist, evaluate QB replacement-value and starter-aware model adjustments chronologically, with strict point-in-time training/validation. A better website label alone is not proof of predictive improvement.

**Key distinction:** Display coverage is now stronger; verified starter coverage is still sparse. Improvement to the actual predictive model requires additional authoritative evidence and successful out-of-sample tests.

## October 24 follow-up: explicit model picks and official QB availability

- `site/index.html` now labels every game card **Model pick · experimental**. Winners, scores and totals are actual frozen predictions from `V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1` and ATS/total sides derive mechanically from the frozen forecast and real, separately observed ESPN lines. A warning still states **PASS_UNVALIDATED**; this is not a manually curated pick or validated betting return.
- For QB display, **Starter not confirmed** is the prominent text unless `CONFIRMED_OFFICIAL` is present. Prior game's passing performer now appears as a *secondary* contextual field with ESPN source and date.
- Added `scripts/site_availability.py`, `tests/test_site_availability.py`, and workflow integration. It retrieves official SEC, Big Ten, ACC and Big 12 conference publisher feeds via the existing strict `scripts.official_availability` matcher; requires a complete, publication-timestamped, scorecard-matched game report and joins QB-only player designations to the website as **official availability, not starter confirmation**.
- An officially **QUESTIONABLE** QB does not mean OUT, does not automatically appoint the replacement QB, and does not change the frozen forecast. If a formally confirmed QB later conflicts with official OUT/DOUBTFUL availability, the *site* quarantines that confirmation as `CONFLICT_REVIEW` instead of showing it as verified. This does not rewrite the underlying archived model evidence.
- Game cards warn when observed official QB designation signals meaningful uncertainty. Source reports may be newer than the archived forecast; values are never smuggled into a historical decision.
- **Critical limit:** the current prospective ridge model trains/predicts on `BASE_FIELDS` (14 team performance features), **not** player identity or the personnel/replacement features. Website enrichment is *not* a QB-adjusted model prediction. Promote a QB-aware candidate only after proper game-specific 2026 QB1 evidence, replacement effects and point-in-time out-of-sample evaluation.
- **Latest successful official-report integration checkpoint:** [run 40105483563](https://github.com/The-Caves/cfb-model/actions/runs/40105483563) passed its 7 dedicated availability tests and export. It accepted **zero QB designations** for 102 upcoming games; its full live public publisher audit accepted SEC 0, Big Ten 4, ACC 3, Big 12 0 *game reports*, not necessarily QB-containing reports. The SEC's zero matched reports is an **unresolved acceptance/matching limitation**, not proof that an SEC game has no published injury information.
- **Mississippi State vs Oklahoma** (October 24): contemporary reporting says Kamario Taylor was officially listed questionable and expected to attempt to play, while last-game backup Parker “Billy” Puckett played against LSU. A new pre-kickoff reviewed statement that explicitly names this game's starter is still required to call anyone confirmed. Do not infer a Taylor OUT, a Puckett confirmation, a replacement-value spread, or a revised betting pick from this report alone.

Next priority: debug missing *published SEC* cards by inspecting exact report-matching reason, fix verified school alias/date/schema bugs with fixtures, obtain explicit current game-specific QB starter claims from official school announcements or on-record coach quotes, then feed them into the immutable review archive *before* recalculating new model variants. Maintain separate clocks for official report observation, forecast capture and market observation.

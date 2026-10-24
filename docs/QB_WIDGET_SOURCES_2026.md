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

## Verified late-morning October 24 repair — official QB reports now flow

The earlier `0 official QB designations` checkpoint above is **superseded** by the following verified repairs and results. Keep it as a timestamped record of the original defect, not as the current state.

### Root causes resolved

1. Public official conference report cards contain rows with `status: Exempt`. This is **not** a medical/availability designation. Former code rejected an entire report on such a row, producing SEC 0/6 and Big 12 0/8. `scripts/official_availability.py` now explicitly excludes Exempt rows from player claims (never calls them AVAILABLE or OUT), while still rejecting truly unrecognized *reportable* statuses. `tests/test_official_availability.py` covers both cases.
2. `site_availability.run` had taken its evidence as-of time **before** live network fetches, so valid reports captured a few seconds later were all rejected as future-sourced. It now uses an actual **post-fetch** UTC cutoff in live runs, while preserving the explicit deterministic test cutoff. It still rejects reports published in the future or game IDs/kickoff times that do not match. `tests/test_site_availability.py` contains a dedicated live-return regression test.
3. The official report publisher returns full-roster availability, including many `AVAILABLE` backups, which is not starter evidence. The website now displays only **consequential** official QB designations (e.g., OUT, QUESTIONABLE, DOUBTFUL, GAME_TIME_DECISION, LIMITED) and keeps full-source counts in the audit; a list of AVAILABLE backups is not promoted to named starters.

### Live acceptance evidence

- [Build 40106031838](https://github.com/The-Caves/cfb-model/actions/runs/40106031838) passed with 25 accepted official matchup report cards out of 27 fetched: SEC 6/6, Big Ten 6/6, ACC 5/7 and Big 12 8/8.
- [Build 40106267876](https://github.com/The-Caves/cfb-model/actions/runs/40106267876) passed after the post-fetch cutoff repair. It matched **245** public-source quarterback player availability rows across **25** upcoming games, sourced from **5,266** published athlete rows (QB position 245). `official_qb_designations` counts report claims, not confirmed starters.
- For October 24 Oklahoma at Mississippi State (ESPN game `401856730`), the verified source data at approximately 11:17 AM ET listed **Kamario Taylor: QUESTIONABLE**, while **Parker “Billy” Puckett: AVAILABLE**, **AJ Swann: AVAILABLE**. “Available” does **not** mean the player is starting. The ESPN last-game box score displays Parker Puckett as last week's passer, also not confirmation of today's QB1.
- Official starting-QB confirmation count is still **zero**, because `data/manual/qb_starter_evidence_2026.csv` has no newly reviewed explicit game-specific declaration. Do **not** silently change it to 245 or declare either Taylor or Puckett the starter.
- The live 14-feature team model scores, market comparisons and historical forecasts remain untouched. An official current-day QB availability overlay **flags** a risk but does not magically supply trained replacement-value adjustment or a retested QB-aware model.

### Next evidence milestone

Audit and approve explicitly current game-specific school/coach confirmations, including links and time stamps, before submitting to the QB evidence review gate. A final SEC report 90 minutes before kickoff is a useful **availability** update but need not contain an affirmative “starting QB” claim. For prediction adjustments, collect confirmed QB identities and replacement performance in point-in-time training rows, run chronological ablations against the current 14-feature model, and promote only if independently validated.

## 2026 October 24 — national quarterback depth-chart rankings

Added `scripts/site_depthchart.py`, `tests/test_site_depthchart.py`, and a once-per-UTC-day bounded public-source cache in the dashboard workflow. This takes small, explicitly ordered QB1/QB2/QB3 fields from 2026 Ourlads third-party projected depth charts and includes source URL and source update time in each game card. It does **not** assert that a charted QB1 starts today, and it does **not** update 2026 frozen score/ATS/O-U model estimates. When the posted site lacks a reliable current 2026 date or an unambiguous QB row, the list is withheld. A chart rank is independent of the official this-game `CONFIRMED_OFFICIAL` status and the conference-issued `OUT` / `QUESTIONABLE` report.

[Initial live build 40107518936](https://github.com/The-Caves/cfb-model/actions/runs/40107518936) successfully parsed 130 school charts and placed QB depth lists on both sides of 94 out of 102 future games (552 ordered QB player entries); zero chart ranks promoted to officially confirmed starters. Five requested schools lacked exact index-name matches: FIU, Miami (OH), USF, UCF and Utah State; the first four now have source-specific reviewed canonical alias mappings, and Utah State remains under review until uniquely matched. The live dashboard's current checkpoint may improve in subsequent builds; always record exact build run and totals. The prior scraper URL mismatch was fixed after an initial no-data build, and the regression test suite passed (9/9 depth-specific checks).

Do not interpret displayed QB1 as certain playing status. Example, the depth chart may list Kamario Taylor at QB1, while a current official conference report lists him QUESTIONABLE and the previous game's passer was Parker Puckett. These facts must remain separately sourced and timestamped.

**Revised live checkpoint:** [Build 40107690785](https://github.com/The-Caves/cfb-model/actions/runs/40107690785) completed successfully with 134 teams charted, 566 explicitly ranked QB entries, 100 of 102 future games with both teams' charts and 0 chart ranks mistaken for official starters. Remaining Utah State link includes the `s=utah+state` encoded whitespace spelling, which is now allowed only within the existing strict Ourlads origin/path and numeric-ID checks. Fresh chart cache namespace v3 will retest the live route.

### Verified final national widget checkpoint — 2026-10-24

[GitHub Actions run 40108010413](https://github.com/The-Caves/cfb-model/actions/runs/40108010413) completed successfully after fixing the query-encoded whitespace case on the Utah State chart URL. The *actual exported research dashboard* had **135 distinct upcoming teams with 2026 QB charts**, **102 of 102 upcoming matchups with QB rankings on both sides**, **570 ranked QB1/QB2/QB3 player entries** (some teams have only two charted QBs), **196 slots where the most recent passer matched a listed chart player**, and **0 claimed starting-QB confirmations from depth charts**. All included charts carry Ourlads source links and are read-only current-site overlays, while the original frozen model's picks, feature values and validation status remain unchanged. The download HTML passed an independent Node syntax check and was inspected against Mississippi State's actual game card: Taylor QB1 (officially QUESTIONABLE), Parker Puckett QB2, AJ Swann QB3. This is **chart rank**, not a confirmed October 24 starter.

School name mismatches were handled by exact reviewed aliases (Florida International/FIU, Central Florida/UCF, South Florida/USF, Miami (Ohio)/Miami OH). The provider's `s=utah state` URL is percent-encoded only after strict Ourlads-host, chart-path and numeric-ID validation. The website build uses a UTC-day cache to avoid repeatedly crawling all charts; the live availability publisher is checked separately at every scheduled website run.

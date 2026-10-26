# 2026 QB starter monitoring — automation coverage and limits

**Updated:** October 26, 2026. **Active model:** `V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1` (`PASS_UNVALIDATED`). New gameweek watcher does not change model predictions, game-day player statuses, or the independently reviewed starter archive.

## Already automated

| Mechanism | Trigger | Trust boundary |
| --- | --- | --- |
| 2026 Data Intake (`.github/workflows/cfb-data-intake.yml`) | Three scheduled GitHub UTC runs per day; optional manual dispatch | Updates as-of schedules, free market observations, opponent profiles, official conference availability, QB review queue, frozen forecast and archived results. A source *candidate* is not confirmed QB1. |
| Official football RSS pilot (`scripts/qb_official_news_watch.py`) | During scheduled full intake | Watches **7 reviewed school feeds**, flags QB and possible injury news as unreviewed article leads. RSS snippets do not approve starters. |
| Official school candidate registry (`scripts/official_school_source_registry.py`) | During full intake | Covers **138 school homepage candidates**, not 138 document-level official game-week starter announcements. |
| Game-specific QB source review worklist (`scripts/qb_confirmation_worklist.py`) | Full intake plus dedicated source validation on changes | Joins known official game-week previews and context mentions to each future ESPN game/team slot without asserting QB1. |
| **New game-week source monitor** (`scripts/qb_gameweek_watch.py`) | `.github/workflows/cfb-qb-gameweek-watch.yml` scheduled **four times each UTC day**, on code changes and on manual dispatch | Fetches five reviewed current game-week preview URLs, stores sanitized article/metadata text fingerprints, flags changes and candidate starter/injury language, and uploads a JSON+CSV review artifact. A detected phrase is not player evidence. |
| QB trainability audit (`scripts/qb_trainability_audit.py`) | Full intake | Refuses to train replacement effects without verified player/game-starter identities, as-of availability, postgame participation and enough held-out observations. |

## Live monitor acceptance, not a blanket claim of confirmed quarterbacks

[GitHub Actions watch run 40369624983](https://github.com/The-Caves/cfb-model/actions/runs/40369624983): **8 unit tests passed; workflow succeeded**. Live captured source behavior:

- **5** active dated university football previews monitored.
- **4** publisher pages had accessible, limited **SEO description metadata**, with stable fingerprints relative to the previous source check.
- **0** pages exposed adequate *full article body* through ordinary HTML parsing in the GitHub runner.
- **1** source (Sam Houston) lacked even a readable description and was marked a fetch failure.
- **0** machine-detected starter declarations and **0** officially confirmed QB1s.
- All source timestamps refer to the actual crawler capture instant; historical upstream publication time of changed material is **not** attested by an HTML crawl.

The watchdog reports `FETCHED_METADATA_ONLY` rather than `FETCHED_HTML`, flags `METADATA_ONLY_INSUFFICIENT_FOR_QB1_CONFIRMATION`, and reports monitor health `PARTIAL_FAILURE`. The pipeline fails explicitly if **all** active sources become unreadable and uploads a diagnostic artifact on failure. No metadata-only excerpt can be silently promoted to `CONFIRMED_OFFICIAL` or included as an as-of training feature. Thus scheduling and limited metadata-change monitoring **are automated**, but reliable body-text screening of these Sidearm-rendered pages is **not yet solved**.

Earlier source-review acceptance: [40365177539](https://github.com/The-Caves/cfb-model/actions/runs/40365177539) matched the archived **122 future QB slots**, **5** official game-week preview source links, **3** game-note landing/document links, **4** non-confirming contextual player mentions, and **0** confirmed starters.

## What is deliberately NOT automatic today

1. **Official positive game-specific QB1 verification:** a coach/school announcement must explicitly name *this* game's starter, have a valid actual publication and observed capture instant, and be reviewed independently. Neither `QB1` in a third-party depth chart, season leading passer, game notes mentioning prior starts, nor `AVAILABLE` in a conference report qualifies.
2. **Human approval:** `scripts/qb_starter_review.py` requires reviewed excerpts and their real source/capture/review evidence fields. No language-model, HTML keyword or manual CSV placeholder is granted approval on its own.
3. **QB replacement impact in picks:** no model promotion or quarterback point penalties until real confirmed pregame starters and postgame participation labels accumulate and pass source-time-safe chronological validation.
4. **Nationwide current game-week reporting:** discovering 138 homepages is not the same as monitoring 138 official football RSS/article bodies. Verified coverage must be expanded publisher by publisher.

## Next engineering work

- Obtain reliable, publisher-permitted content feeds or parsed game-note documents for schools whose interactive site returns only metadata; record a full-text source status separately from a metadata ping. Prefer official university football RSS feeds with dated story bodies or the school's published media-note documents.
- Expand verified football feed registrations beyond the current seven to cover the next scheduled games. Never invent standard-looking feed URLs or claim working feed access without a live validation test.
- Re-run the game-week source review regularly as new official releases are published. Collect actual game-specific QB declarations and conflicting injury reports into the reviewed evidence gate; preserve earlier capture times and frozen model versions.
- Add independently verified postgame QB starts and substitution labels separately, then test learned player availability and replacement value without leakage.

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


## October 26 late-evening follow-up — 3/3 direct university game-note PDFs now readable

The official five-page HTML monitoring remains partial (four readable publisher metadata descriptions, zero fully parsed article bodies, one metadata fetch failure). A separate, source-authorized direct-PDF watcher now provides a **full-text source path** without pretending metadata is enough.

New modules:
- `scripts/qb_official_notes_watch.py`: strict official-publisher or matching Sidearm S3 game-note URL checks; bound PDF bytes and page count; reject encrypted, malformed or unexpectedly HTML responses; extract searchable PDF text via `pypdf`; record file SHA256, actual capture timestamp, before-kickoff constraints and a capped set of QB/injury language review snippets; preserve **confirmed_starter=false**.
- `tests/test_qb_official_notes_watch.py`: replay direct PDFs, misdirected HTML landing pages, document changes, unsafe publisher URLs, postkickoff exclusion and corrupt files; no automatic QB1 promotion.
- `.github/workflows/cfb-qb-gameweek-watch.yml` installs `pypdf`, tests and executes PDF screening alongside four-times-daily HTML source review. Both results are exposed in the archived GitHub Actions artifact, not as active model inputs.
- For the two originally reviewed football-note landing pages, the safe official-document link discoverer extracted exact matching PDF names and publisher-authorized Sidearm S3 URLs; the verified links replaced the HTML landing pages in `config/official_gameweek_sources_2026.json`. This was reviewed linkage, not inference about the starting QB.

**Final acceptance:** [GitHub Actions run 40413098757](https://github.com/The-Caves/cfb-model/actions/runs/40413098757) **passed**, with **3 direct official PDF documents extracted out of 3 linked game-note documents**, **0 PDF landing pages**, **0 unreadable docs**, **0 candidate game-specific "will start" phrases**, and **0 confirmed starters**. The companion [official fixture/source validation run 40413098739](https://github.com/The-Caves/cfb-model/actions/runs/40413098739) also passed. Documents currently monitored:
- Western Kentucky vs Delaware — source-discovered exact official Sidearm PDF (`2026/10/25/WKU_FB_26___Game_Notes___Delaware.pdf`).
- Delaware at WKU — previously direct official Sidearm PDF (`2026/10/26/2026_Delaware_Football_Notes_-_WKU.pdf`), **77 pages** verified on initial run.
- Missouri State vs Sam Houston — source-discovered exact official Sidearm PDF (`2026/10/23/Game_Notes_8_vs_Sam_Houston.pdf`).

This improves **document readability**, not actual starter coverage. The watcher records PDF byte-level changes but no independently authenticated upstream publication timestamp or human approval. Old source previews still cover only 5 of 122 candidate team/game slots, and directly linked readable game notes cover only 3 of those 122. The current signal is a review lead, not QB1 evidence, and the active V03 model remains unchanged.

**Next acceptance work:** Expand verified full-text notes/news coverage to additional scheduled schools, obtain real explicit game-specific QB announcements and capture times, then collect *independently validated postgame QB starts/substitutions* for prospective replacement-value modeling. For longer-term provenance, preserve the document-monitor run summaries/fingerprints beyond GitHub artifact expiration in the immutable `context-state` archive; today's watcher uses GitHub Actions cache for comparisons and 30-day artifacts.


## October 26 evening — expanded documents and durable provenance

- Added the officially dated **North Texas vs FAU** preview (October 26, ESPN 401862812), raising fixture-matched preview sources to **6**. The same exact matchup is covered by an earlier official **FAU** October 23 broadcast note. The 2026 North Texas [football media center](https://meangreensports.com/sports/2026/9/2/unt-media-center) shows a Game 8 vs. Florida Atlantic section, but its own game-note download was not published as an accessible link at the time of inspection. We have **not** invented one.
- Official Sam Houston's [2026 Game Notes Archive](https://gobearkats.com/sports/2021/1/26/football-game-notes) now lists Game 8 at Missouri State. The university document-landing page led to its exact-name Sidearm S3 direct PDF; its original landing URL was preserved as `game_notes_landing_url`. This raises current official full-text documents to **4**: WKU, Delaware, Missouri State and Sam Houston.
- The source verifier and 2026 122-slot QB worklist validation succeeded after the expansion: [run 40429936232](https://github.com/The-Caves/cfb-model/actions/runs/40429936232).
- The [live notes monitor run 40429936206](https://github.com/The-Caves/cfb-model/actions/runs/40429936206) extracted **4 of 4** current official PDFs with zero unparseable notes and zero landing pages, while detecting one possible starting-QB phrase. That Sam Houston passage describes **Landyn Locke's previous ten games as starting quarterback**, not an affirmative assignment for the Missouri State kickoff. The system correctly retained **0 confirmed upcoming starters**.
- Implemented `scripts/qb_source_watch_archive.py` with strict source type, capture clocks, unplayed game identity, file SHA256 and nonconfirmation guards, plus tests. Successful run `40429936206` permanently committed its screening report to `context-state/research_2026/qb_source_watch/2026/10/27/run-40429936206.json.gz`. The original HTML and extracted PDF bytes themselves are **not** stored; the research record contains observation metadata, hashes, capped review excerpts and run identity. Repeated runs are write-once, never historical rewrites.
- Implemented source-specific `scripts/qb_media_notes_index_watch.py` and `config/official_football_media_index_pilot_2026.json`, monitoring North Texas's exact **Game 8 / Oct 29 / Florida Atlantic** media-center section. It records only an actual on-page school-authorized link under that section; a bare nonclickable 'UNT Game Notes' label or an old week's download is not accepted as a lead. These observations have been added to the permanent research-source archive, separate from QB1 review approvals.
- All watch runs still count site metadata as **limited**, not independently authenticated game-week article bodies. Game-note PDFs are searchable, but a phrase or depth chart remains an unreviewed source lead rather than a verified starter. The active 14-feature model remains unchanged. The QB-data trainability gate still blocks player-replacement effects.

**Next priorities:** scale published football media center/source indexes by school, audit each exact new document, obtain explicit dated QB declarations or credible official injury reports and follow through with postgame participation labels before testing a learned QB-impact feature. Preserve fresh capture and upstream-publication clocks separately.


### Verified targeted media-center polling and complete source-run archival

The latest [Official Gameweek QB Watch run 40430715155](https://github.com/The-Caves/cfb-model/actions/runs/40430715155) succeeded with direct text extraction from **4/4** official game-week PDFs, **1 historical/undated "starting quarterback" keyword lead**, 0 verified QB1s, and 6 monitored school previews (4 metadata-only successes, 2 unavailable). The official North Texas media-center pilot fetched its 2026 index, matched the **Game 8 / October 29 / Florida Atlantic** section, and found **0 actual linked current-game notes documents**, so it did not reuse a previous week's UNT notes or invent a URL. Official [UNT football media center](https://meangreensports.com/sports/2026/9/2/unt-media-center) remains a reviewed index lead.

Source-watch archiving includes the media-center observation hash, original link-review status, HTML metadata/PDF capture times and contents SHA256, via `scripts/qb_source_watch_archive.py`. Run **40430715155** persisted research-only audit record `context-state/research_2026/qb_source_watch/2026/10/27/run-40430715155.json.gz` and verified its GitHub commit. This is an observation archive, **not** an authenticated upstream publish timestamp, starter approval or historical source-body archive. Automatic source discovery remains a pilot for **one official media center**, not nationwide coverage. The full-body HTML news parser remains incomplete.

The specific PDF false-positive snippet arose from Sam Houston's *prior ten games* description of **Landyn Locke as starting quarterback**; it is contextual historical usage, not verification that Locke will start October 27. No starter confirmations or injury-related point values have been added.


### October 27 follow-up — FAU Game 8 official notes lead

**Code commit:** [1bef0f4](https://github.com/The-Caves/cfb-model/commit/1bef0f408479a5e08cbfa0a01337096966add87a). **Acceptance:** [Official Gameweek QB Watch run 40579637383](https://github.com/The-Caves/cfb-model/actions/runs/40579637383), [QB Official Source Review Validation run 40579637305](https://github.com/The-Caves/cfb-model/actions/runs/40579637305), and [Data Intake run 40579637312](https://github.com/The-Caves/cfb-model/actions/runs/40579637312) all **succeeded**.

- Florida Atlantic's [October 26 “Football Game Notes #8” announcement](https://fausports.com/news/2026/10/26/football-game-notes-8) explicitly concerns the October 29 matchup **at North Texas**, game **401862812**. Its publisher-linked [“FB: Game Notes #8” document landing URL](https://fausports.com/documents/2026/10/26/2026_Game_Notes__8_remediated.pdf) is now tracked in `config/official_gameweek_sources_2026.json`. The October 23 FAU broadcast preview is preserved in `superseded_preview_url` for audit. Do not backdate this October 26 evidence to a previous model run.
- Source matching tests assert that a PDF link discovered from that landing page must be the **identical officially named document**, from the proper university/Sidearm publisher. Previous-game notes and external-host links are rejected. A link or page title does not verify the PDF text.
- **Live observed screening:** 6 reviewed gameweek preview URLs (**4 metadata-only**, **2 fetch failures**, **0 complete HTML story bodies**); **5 official notes links**, **4 PDFs successfully extracted**, **1 non-PDF landing page**, **0 unreadable PDFs**. There was **1 keyword candidate**, not an explicit confirmed upcoming QB assignment. The FAU notes landing page needs publisher-linked direct-PDF resolution and is **not** counted among readable source documents.
- **Starting QB confirmation remains 0;** the archive reports `verified_starter_game_slots: 0`. Immutable research-only report was stored under `context-state/research_2026/qb_source_watch/2026/10/27/run-40579637383.json.gz`, without claiming authenticated upstream article publication time or archiving full PDF bytes.
- QB review worklist validation accepted **6** reviewed previews and **5** links to notes, preserving non-confirmation. The existing live `V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1` model, frozen forecasts and betting-readiness status were **not** changed. **Milestone 2B is still OPEN.**

**Next engineering priority:** safely resolve FAU's published landing page to a real verified PDF *if* the official publisher exposes a direct download; expand exact-game official media-note discovery beyond the UNT pilot without fabricated routes or previous-week reuse. Then acquire independently reviewed, timestamp-safe official game-specific starter declarations and postgame QB participation labels before any player-effect training.

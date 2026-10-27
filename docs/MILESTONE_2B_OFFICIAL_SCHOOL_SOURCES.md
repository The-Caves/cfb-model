# Milestone 2B — 2026 Official School Source Verification

**Checkpoint:** 2026-10-24 (America/New_York)  
**Status:** DISCOVERY INFRASTRUCTURE VERIFIED; DOCUMENT-LEVEL SOURCE-TYPE VERIFICATION OPEN  
**Scope:** Nationwide official source discovery and verification for 2026 FBS personnel information. This **Milestone 2B** is distinct from the older *v0.4 Step 2B* optional private AWS-archive discussion in the README. **No AWS or paid service is required for this milestone.**

## Source of truth and safety rules

- Source directory: `data/archive/2026_team_aliases.csv` (138 teams, including North Dakota State and Sacramento State), plus `config/official_athletics_sites_2026.json`.
- The school-source audit does **not** establish starting QB1, injuries, player replacements, or historical player availability. Missing sources/statuses remain `UNKNOWN` or `NOT_YET_VERIFIED`, never healthy/unavailable by inference.
- Candidate URL, reachable page, or filename is not a document-level verification or confirmed game-specific player claim.
- Before any person/game evidence can influence predictions or walk-forward evaluation, require verified team, 2026 football season, precise game/opponent, source provenance, publication and observation times before decision/kickoff, and audit trail. Never backfill modern knowledge into a prior decision.
- The research model remains `PASS_UNVALIDATED`. Do not represent subjective choices as model-produced picks; do not promote betting readiness based on successful CI alone.

## Implemented and verified through October 24, 2026

| Area | Evidence / state |
| --- | --- |
| 138-school inventory and reviewed candidate athletics domains | Implemented in `config/official_athletics_sites_2026.json`, `scripts/official_school_source_registry.py` |
| Public site/RSS reachability | `scripts/official_source_connectivity.py` probes 138 school athletics homepages and 8 reviewed official RSS feeds. RSS is optional, not a 138-feed target. |
| Official school page discovery | `scripts/official_personnel_source_discovery.py` crawls athletics homepage, football page and bounded secondary pages; verifies school-domain links, preserves failed probes, records candidate game notes/depth charts/injury sources, does not promote player evidence |
| Explicit per-school unresolved source types | `scripts/official_personnel_source_coverage.py` exports JSON/CSV and review backlog; distinguishes `NO_CANDIDATE_LOCATED` from `NOT_PUBLISHED` |
| Latest successful source audit | [Run 40066306748](https://github.com/The-Caves/cfb-model/actions/runs/40066306748), at [main commit 438505947cb3f9d4f7d1cd50d08c8cecb823b7e2](https://github.com/The-Caves/cfb-model/commit/438505947cb3f9d4f7d1cd50d08c8cecb823b7e2): 138/138 football pages audited; game-note link candidates for 80 schools, separate depth-chart candidates for 12, school-site injury-report candidates for 1. **Those are candidate-link counts, not verified documents or players.** |
| Same-commit Data Intake | [Run 40066306686](https://github.com/The-Caves/cfb-model/actions/runs/40066306686): both validate and ingest jobs succeeded |
| Same-commit scheduled context refresh | [Run 40087648886](https://github.com/The-Caves/cfb-model/actions/runs/40087648886): refresh job succeeded. Successful run does not imply complete QB/injury coverage. |

Previous failed runs 40065228822, 40065228838, 40065238026, and 40065238074 came from an incorrect fallback-URL test fixture and were followed by successful runs. Do not count historic failed runs as current failing HEAD without checking the latest run.

The dedicated workflow is `.github/workflows/cfb-school-source-audit.yml`; its acceptance guard checks all 138 football pages were audited **and** that unreviewed player evidence has not been promoted.

## Outstanding work — 2B is not yet closed

1. **Verify real documents:** fetch candidate game-note PDFs/HTML and separate depth charts; confirm authorship, football relevance, season, opponent/game, source URL, publication timestamp and the existence of any *embedded* depth chart. Reject or quarantine stale, generic or mismatched documents.
2. **Expand gaps:** for each canonical school and each source type, record `VERIFIED_DOCUMENT`, `CANDIDATE_REVIEW_REQUIRED`, `SEARCH_INCOMPLETE`, or defensible `NOT_PUBLISHED_OR_NOT_AVAILABLE` with dated audit details. No discovered link must **not** be treated as no published document.
3. **Official conference availability mapping:** map verified SEC, Big Ten, ACC and Big 12 reporting publishers via `scripts/official_availability.py` to canonical eligible schools and games. Check publication/collection timestamps and freshness. Official `AVAILABLE`, `OUT`, etc. are *availability reports*, not inferred diagnoses, player participation or starting-QB statements.
4. **Keep source types separate from player assertions:** verified game notes or a verified depth chart are only evidence of document availability. Promote `CONFIRMED_REVIEWED_PREKICKOFF` QB1 or player status exclusively through the independently reviewed game-specific evidence gate.
5. **Test and verify end-to-end:** add fixture/acceptance coverage for misleading candidate links, outdated notes, embedded depth charts, ambiguous conference matches, missing time metadata, and pre-kickoff as-of rules. Run unit tests and inspect actual latest-head GitHub workflow outputs/artifacts.

**Exit condition:** An auditable 138-school, per-source-type inventory of verified official 2026 documents or explicitly justified status, with provenance and timestamp evidence; conference-report school coverage mapped; safety gates passing. **Not** merely 138 reachable football pages, **not** 138 RSS feeds, and **not** automatic nationwide QB1 confirmations.

## Roadmap following this milestone

- **Milestone 1:** QB-confirmation acceptance infrastructure existed before 2B; verify its current acceptance report rather than assuming every game-specific QB was confirmed. `scripts/qb_milestone_acceptance.py` explicitly distinguishes infrastructure checks from verified-starter coverage.
- **2C:** verified game-specific starting QB1 records.
- **2D:** reviewed game-specific player availability.
- **2E:** statistically tested player replacement value (no unvalidated manual point penalties).
- **2F:** strict, timestamp-safe prospective / walk-forward SU, ATS and O/U evaluation, including market provenance and ablations.

## Documentation maintenance convention

Update **this file** alongside each material 2B code change, acceptance result or verified source-coverage change. Record:
- UTC timestamp, affected scripts/config/tests;
- precise numerator/denominator by team/source type and explicit `UNKNOWN`/missingness;
- commit SHA, GitHub Actions run URLs, pass/fail and relevant artifact names;
- discovered blockers, verified resolutions, remaining work, and whether research-model status changed.

Keep broader status aligned with `README.md`, `docs/CONTEXT_DELTA.md`, and applicable `docs/V04_*.md` documents. Never replace observed results with fixture-only claims. Preserve historical checkpoints; append dated updates instead of silently rewriting past evidence.


## October 26, 2026 follow-up — verified upcoming gameweek source worklist

**GitHub acceptance run:** [CFB QB Official Source Review Validation #40365177539](https://github.com/The-Caves/cfb-model/actions/runs/40365177539). Dedicated source review tests and replay against archived `cfb-2026-data-40252874370` **passed**. The source-linked JSON and CSV are available as GitHub artifact `cfb-qb-reviewed-source-worklist-40365177539`. This run verifies source linkage and worklist logic, NOT starter confirmation.

### Observed exact 2026 starter-review coverage

| Measure | Verified |
| --- | ---: |
| Upcoming ESPN matchups in frozen Oct 26 queue | 61 |
| School/game starting-QB slots | 122 |
| School homepage *candidates* | 122 slots |
| Canonical school IDs included in directory | 138 schools |
| Reviewed, fixture-matched official gameweek previews | **5 slots** |
| Official gameweek notes URL/landing-page links | **3 slots** |
| QB player mentions in the reviewed gameweek sources | **4 slots** |
| **Explicit independently reviewed official game-specific starting-QB confirmations** | **0 / 122** |

**Confirmed documentary scope, not starter identity:**

- [WKU athletics October 25 Delaware preview](https://wkusports.com/news/2026/10/25/football-hilltoppers-welcome-delaware-for-weekday-cusa-matchup) matches ESPN game 401871071 (Oct 27) and links [WKU game-notes page](https://wkusports.com/documents/2026/10/25/WKU_FB_26___Game_Notes___Delaware.pdf). The URL ends `.pdf` but the website resolves to an **HTML document landing page**. This does not establish that an attached PDF was independently read/verified.
- [Delaware athletics October 26 WKU preview](https://bluehens.com/news/2026/10/26/football-wraps-weekday-cusa-play-at-wku) matches the same game. The [Delaware notes document](https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/bluehens.com/documents/2026/10/26/2026_Delaware_Football_Notes_-_WKU.pdf?timestamp=20261026032134) was visibly checked as a 77-page official game-specific PDF; the cover and notes feature **Nick Minicucci** and explain his return from a recent injury, but do not explicitly guarantee that he will start at WKU. Official preview context is `RETURNED_FROM_INJURY_IN_PREVIOUS_GAME`.
- [Missouri State athletics October 23 Sam Houston preview](https://missouristatebears.com/news/2026/10/23/football-bears-back-home-tuesday-to-host-sam-houston) is official and fixture-matched for 401871072, with [official game-notes landing page](https://missouristatebears.com/documents/2026/10/23/Game_Notes_8_vs_Sam_Houston.pdf). The school says **Henry Belin IV** made two previous starts; that is **not** game-specific Tuesday starter confirmation.
- [Sam Houston athletics October 25 Missouri State preview](https://gobearkats.com/news/2026/10/25/football-game-8-preview-at-missouri-state) is official and fixture-matched for 401871072. It describes **Landyn Locke's** season passing production, not an explicit starting assignment. Its "Sam Houston game notes" page link currently resolves to a **Game 7 vs NM State** document, so **no current-game notes URL was promoted** from that mislabeled link.
- [FAU athletics October 23 North Texas broadcast release](https://fausports.com/news/2026/10/23/football-florida-atlantic-at-north-texas-to-air-on-espn) is the official, dated 401862812 fixture preview and references **Caden Veltkamp** season passing stats, but does not name him as the confirmed Oct 29 starter.

`config/official_gameweek_sources_2026.json` stores these source URLs, original published dates, exact opponent and kickoff, distinct contextual-QB mention categories, and `starter_confirmed=false`. `scripts/qb_confirmation_worklist.py` joins the sources to the frozen 2026 official-school inventory and upcoming review rows. The acceptance validator rejects mismatched ESPN game, school, opponent, future-season/stale publishing dates, unapproved source domains, duplicate candidate sources, and any attempt to treat a contextual mention as confirmed QB1. The script does not alter `data/manual/qb_starter_evidence_2026.csv`, the `qb_history` archive, or the active forecast.

### Remaining work

The verified game-week preview sample covers **only 5 of 122** upcoming QB slots; **117 slots** still require official-document discovery or closer source review. Even the five confirmed documents yield **zero actual starter confirmations**. Earlier source discovery across 138 schools is not equivalent to a verified document or starter statement, and these observed counts should not be extrapolated. We still need: (1) authentic this-game coach or school QB1 declarations with time of publication, capture and independent review; (2) evidence of relevant injury availability and contradictory announcements; (3) separately verified postgame starts and actual substitution participation. Only then can QB-specific point effects be estimated and evaluated prospectively.

**Current production model unchanged:** `V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1` and `PASS_UNVALIDATED`. The corrected home-bias candidate is still experimental; totals work remains next after QB-evidence acquisition.


## October 27: model-facing injury coverage clarification and partial-report capture

The **five game-note links / four readable PDFs** are a small verification pilot, not a nationwide injury feed. Official-source inventory covers 138 registered schools, while the active availability collector polls four official conference structured feeds (SEC, Big Ten, ACC, Big 12) and an optional reviewed CSV. Other schools often lack structured official reports; preview articles and notes are leads, NOT automatic player availability. Missing means **UNKNOWN**, not healthy.

The [October 27 Data Intake run 40535406287](https://github.com/The-Caves/cfb-model/actions/runs/40535406287) completed with **68 future games / 136 team-game slots / 0 verified pregame report slots** at that source capture. All four publisher endpoints returned **0 accepted published cards** because the relevant official game-week reports were still marked `Report Pending`; this is a point-in-time coverage snapshot, not a season-long coverage rate, medical conclusion, or evidence that feeds are broken.

**Scoring separation:** `scripts/personnel_forecast.py` fits/predicts only the 14 `BASE_FIELDS`, so frozen V03 predictions are NOT yet directly adjusted for injuries. `scripts/player_replacement.py` derives position-specific absence counts and can fit experimental past-only residual coefficients, but it is **not** a validated player-value model and those estimated adjustments are not in live picks.

Improvement: `scripts/personnel_replacement_capture.py` now also keeps the as-of **home and away position-specific official availability report counts separately**. If the home team has a verified report but the away report is missing, the observed home OL/WR/QB etc. counts are retained, the away side remains unknown and two-team differentials/replacement points stay null. The capture reports verified team slots, partial matchups, reported absences and uncertain designations; it explicitly records zero live injury adjustments. Source rows remain subject to strict pregame capture/publish-time and provenance checks.

Next source engineering: extend trustworthy game-specific official and team journalism coverage to unreported schools, record depth/previous snap contributions and postgame QB participation independently, accumulate paired as-of outcome cases, then train/compare a candidate injury-aware score model chronologically against frozen V03 and the market. No fixed "QB out = N points" shortcut, no in-sample promotion, and no read-only website-only fix.


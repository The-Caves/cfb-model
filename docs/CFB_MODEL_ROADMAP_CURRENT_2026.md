# College Football Model — current prioritized roadmap (November 3, 2026)

This is the **current handoff and order of work**. The existing [next-generation design](NEXT_GENERATION_MODEL_ROADMAP_2026.md), [V05 robust scoring](V05_ROBUST_RESEARCH.md), [V06 opponent-adjusted trajectory experiment](V06_REGIME_RESEARCH.md), and [long-term QB source controls](OFFICIAL_LONGTERM_QB_ABSENCE_RESEARCH.md) remain relevant. Nothing in this roadmap authorizes automatic score-model promotion, changing a past prediction, or claiming a validated ATS advantage.

**Current live website:** V04 independent score projections with market-anchored research PASS gates; V05 displayed as shadow, V06 an additional chronological benchmark. V03 remains quarantined for home bias. Frozen predictions and market quotes are archived separately from final labels.

## Practical game-day deliverable — stop splitting Milestone 1

**User-facing goal:** Before each game, show a named **expected** quarterback if credible
current depth-chart evidence exists; flag all officially reported unavailable /
questionable players by position; update near kickoff; distinguish
`CONFIRMED_THIS_GAME`, `PROJECTED_DEPTH_CHART`, and `UNKNOWN`.
Never select the presumed QB by historical yards or silently substitute a
historical team passing leader into a player prop. A game-specific
confirmation is still a stronger claim than an expected starter.

**What now works:** The same centralized HD Intelligence official conference
feed handles SEC, Big Ten, ACC, Big 12, MAC, and American; Gameweek availability
is polled by the site overlay. The displayed QB defaults to a current
third-party depth-chart projection *only* when the candidate is not ruled
out, and is labelled unconfirmed. PlayerForm passing scenarios now require a
reviewed confirmed QB or current ranked chart QB; if no matching named
player has valid historical stat sample, abstain rather than showing the
former high-yardage passer. Frozen game score forecasts are not rewritten.
Tests enforce the name-selection invariant.

**Remaining real blocker:** A free universal feed that confirms actual
starting lineups 60 minutes before every FBS kickoff has **not** been
verified. Availability designations are not starter assignments, and
official conference reports may be pending early in the week or never
issued for nonconference games. Do not write "confirmed" from an absence of
injury reports. The pipeline must show current coverage counts and source
timestamps; false certainty is worse than an honest projected starter.

**One finish line, not infinite 1A.x steps:** Have the automated pregame
website display current sourced expected QBs, exclusions, uncertainty, and
updated player projections for upcoming actual games; empirically check
against eventual named gamebook starters and report misidentifications.
Keep the separate **research validation** thresholds below unchanged;
reaching the practical display goal does not imply that replacement-effect
training, independent prospective predictive lift, or betting validation
has passed. We should proceed with later model work in parallel rather
than using research perfection as a reason never to advance.

## Milestone 1 — Verified quarterback intelligence (current)

The *engineering* for several components exists, but **the milestone is not complete just because code or CI passes**. The authoritative evidence report is `scripts/qb_m1_completion.py`, stored from every actual Data Intake in `data/pregame_evidence/qb-milestone1-completion-RUN.json` and in the `cfb-qb-milestone1-RUN` artifact.

| Step | Implemented mechanism | Required real-world evidence / completion gate |
|---|---|---|
| **1A. Confirm game-specific starters & availability** | Nationwide candidate directory, official-news review worklist, game-week sourced notes, strict independent reviewed-starter history, current scenario rank/counter-source checks. New `qb_longterm_expected` excludes a reviewed university season-OUT player from next-game projected starter scenarios, preserves UNKNOWN, and does not invent QB2 starter status. | At least **25%** of active team-game starter slots explicitly verified pregame for research readiness, with original publisher/observation timestamps. A third-party QB1, season leading passer, availability designation, or reviewed article that mentions a previous game **is not confirmation**. Work toward much higher nationwide coverage. |
| **1B. Named player historical profiles** | Named passer EPA/play and observed pass shares, within-team comparisons, defensive-opponent prior-date context, last-game roles, experimental passer-exposure scenarios. Existing same-run QB research forecasts are archived. | Demonstrate player-specific observable sample on live prospectively frozen games; past publication revisions are still not authenticated; transfer/rushing/pressure contributions are not yet complete. |
| **1C. QB1-to-QB2 impact** | `qb_conditional_forecast` & `qb_defense_adjusted_peer` estimate regularized *conditional experimental* margin changes, with no automatic backup penalty. `qb_trainability_audit` blocks independent causal replacement training without verified labels. | At least **25 independently verified replacement participation events**, **60 two-sided starter-reviewed games**, enough labelled games, and *properly timestamped* pregame features/official actual-starter postgame identity. The absence of these labels blocks any claim of a verified QB replacement point value. |
| **1D. Historical & prospective validation** | Frozen candidate shadows, source-hashed archival, and `candidate_shadow_grade` compare against exactly the same V03 research grades. New `qb_m1_completion` cross-checks same-game IDs, source clocks and sample coverage, and publishes failures explicitly. | At least **100 same-cohort, independently settled QB-conditional research forecasts** with actual margin error improvement against a frozen reference, plus replacement event and starter verification readiness. Test against V04 and a market baseline on the same independent prospective cohort before manual review. |

**Latest known blockers:** reviewed *game-specific* QB coverage remains near zero; current historical Step 3E manifests do not encode independently named actual starters and replacement participation; there are no warranted causal replacement-value coefficients. The official Mississippi State Kamario Taylor season-ending source first becomes eligible for *newly made* reports on November 4 UTC. Previously frozen Texas–Mississippi State forecasts remain unchanged. Official season-OUT plus unverified replacement triggers V04 ATS/O-U research PASS, not a guessed downgrade.

**Step 1A code is integrated, but evidence is not complete.** Do not call Milestone 1 complete or move directly to live QB-adjusted scores until the true evidence tests pass. A newer data-intake report should supersede any dated coverage percentages above.

### Milestone 1 deliverables and operational checks

- `scripts/qb_longterm_expected.py` — future-only long-term QB OUT filter between `qb_expected_starters` and `qb_confirmation_coverage`; preserve playable backups as scenarios, but leave next-game starter UNKNOWN until directly verified.
- `scripts/qb_m1_completion.py` — combined identity/time/coverage/held-out acceptance report, run after the same-run candidate-shadow grade. `milestone_1_evidence_complete` may remain false indefinitely while real sources are missing: this is the correct behavior.
- Data Intake publishes `cfb-qb-milestone1-RUN` with QB coverage, shadow, trainability, and completion receipts for review. Run `python -m unittest discover -s tests -p 'test_qb_longterm_expected.py' -v` and `test_qb_m1_completion.py`; then run the full suite and verify an actual Data Intake run.
- No named QB is manufactured from roster rank or a passing leader; no missing report means healthy; no post-game label becomes a pregame input.

### November 3 real intake and postgame source evidence

The full Data Intake [41699478351](https://github.com/The-Caves/cfb-model/actions/runs/41699478351) succeeded. Its acceptance artifact measured **148 upcoming team-game slots, zero officially confirmed starters, 127 named unconfirmed projected starters, 71 QB-conditional research forecasts, 45 early prospective QB grades, and zero independently labeled in-game replacements**. QB conditional mean absolute margin error was 12.59498 versus the exact same-cohort V03 reference's 12.60667, not a demonstrated lift.

An independent postgame settlement [41689626364](https://github.com/The-Caves/cfb-model/actions/runs/41689626364) reported **14 accepted postgame QB labels across the archive, zero labels overlapping the 114 eligible frozen pregame team-game slots, and 100 review targets**. The settlement's academic-ready gate remains closed even though official labels are on file.

A reviewed official [University of Oregon boxscore for Northwestern at Oregon on October 31](https://goducks.com/sports/football/stats/2026/northwestern/boxscore/24384) establishes two *postgame* QBs (Northwestern Aidan Chiles, Oregon Dylan Raiola), score 26–34, and exact date/team identity. This source matches an existing pregame-frozen matchup and is added to the official gamebook source registry for fresh postgame archiving; first exposure is **November 3 or later**, not retroactively October 30. It does not establish either team's next starter or identify an in-game replacement effect. The source's live CI capture must pass before counting any new accepted paired labels.

### November 3 expanded official gamebooks and settlement handoff

The verified school gamebook library now covers **9 reviewed football games / 18 literal after-game starter flags**, confirmed by [read-only live source check 41704138741](https://github.com/The-Caves/cfb-model/actions/runs/41704138741), with no source parse failures. Newly reviewed October 31 matchups with *earlier frozen pregame QB candidates* are:

- [Northwestern at Oregon](https://goducks.com/sports/football/stats/2026/northwestern/boxscore/24384), final Oregon 34–26: Northwestern **Aidan Chiles**, Oregon **Dylan Raiola**. The first postgame settlement archived both, bringing the accepted historical starter-label index from **14 to 16**.
- [Southern Miss at UL Monroe](https://ulmwarhawks.com/sports/football/stats/2026/southern-miss/boxscore/16562), final Southern Miss 35–21: Southern Miss **Landry Lyddy**, ULM **Aidan Armenta**. Parser support for source-reviewed combined team STARTERS tables passed the same live source audit. These additional two **cannot be counted as persisted training labels until a settlement job commits them**, even though the source extractor independently verified them.

GitHub's shared `cfb-context-state` concurrency queue cancelled the newer [settlement 41704138738](https://github.com/The-Caves/cfb-model/actions/runs/41704138738) while the prior [Oregon settlement 41703635420](https://github.com/The-Caves/cfb-model/actions/runs/41703635420) was still processing. This is not a model or source failure; arrange a fresh `[run-settle]` trigger once the older writer completes, and inspect both the append-only starter ledger and `qb-starter-trainability` summary. A single shared archive writer must remain serialized to avoid source-index corruption.

This work improves the ability to *grade* QB starter scenarios; it does **not** resolve the zero confirmed starters for future games or prove injury-specific replacement value. The primary score model remains V04 until separately validated.

### November 3 QB1/backup gamebook expansion and honest forecast evaluation

University-published offensive STARTERS now have **11 independently reviewed October 24–31 boxscore sources**, yielding **22 actual-starter labels** in a source-only CI capture; 4 newly observed October 31 players are from:

- [Texas 31–3 Mississippi State](https://texaslonghorns.com/sports/football/stats/2026/mississippi-state/boxscore/22501): **Arch Manning**, **AJ Swann** (not team leading-passer inference). Critically, the frozen pregame Mississippi State QB projection was Parker Puckett; the gamebook says Swann. This provides a falsifiable mistake to evaluate, but a hindsight starter switch cannot change the 10/31 frozen spread.
- [Georgia Southern 19–3 App State](https://gseagles.com/sports/football/stats/2026/app-state/boxscore/17433): **Max Johnson**, **Malachi Singleton**. The Georgia Southern freeze was UNKNOWN, so the grader must count this as abstention, **not** a correct projection.

Official source check [41725949018](https://github.com/The-Caves/cfb-model/actions/runs/41725949018) succeeded with **22/22 unambiguous QB starter flags and zero failed sources**. The postgame ledger and same-cohort trainable-example counts are separate; source acceptance alone does not certify training readiness.

The new `qb_starter_supervised.py` forecast scorecard grades only **already frozen** starter identities against subsequent independently source-verified starters. It distinguishes CORRECT, INCORRECT, UNKNOWN, and pregame projected names missing from its frozen roster; records known-pick accuracy only over graded projections and discloses small-sample/single-week limitations. It never counts postgame source labels as known at prediction time or promotes a QB model based on a few gamebooks.

Neither real game-specific pregame starter coverage nor a causal injury replacement points model is complete. Continue the next prospective football weeks and manual validation of actual official gamebooks before training. The Milestones 2–5 below remain on the roadmap unchanged.

### Verified November 3 expanded QB settlement and first QB-selection audit

The completed [settlement 41726199391](https://github.com/The-Caves/cfb-model/actions/runs/41726199391) archived **22 unique actual-starting-QB labels** (zero conflicts) and paired **8** with immutable, 24–72-hour pregame QB shadows on **one football date** (Oct. 31). The manual source backlog fell to **92**. The calibrated replacement model is not ready.

Newly paired October 31 university gamebooks are [Texas 31–3 Mississippi State](https://texaslonghorns.com/sports/football/stats/2026/mississippi-state/boxscore/22501) (Arch Manning, AJ Swann) and [Georgia Southern 19–3 App State](https://gseagles.com/sports/football/stats/2026/app-state/boxscore/17433) (Max Johnson, Malachi Singleton). These are **postgame evidence**, not earlier pregame confirmations. Mississippi State's frozen projected starter was Parker Puckett, not AJ Swann; Georgia Southern's was UNKNOWN. These are diagnostic error and abstention examples.

[PR #58](https://github.com/The-Caves/cfb-model/pull/58) added a postgame-frozen-starter scorecard with distinct CORRECT, INCORRECT, UNKNOWN, and projected QB absent from the frozen roster. It estimates a hit rate only from named pregame projections subsequently linked to independently verified starters, and never promotes automatically. The completed [settlement 41727017866](https://github.com/The-Caves/cfb-model/actions/runs/41727017866) computed its first real postgame-only audit: **6 correct named frozen projected starters, 1 incorrect named projection (Parker Puckett instead of AJ Swann for Mississippi State), 1 UNKNOWN (Georgia Southern), and 0 frozen-roster mismatches**. That is 6/7 correct **among named and independently gradeable projections**, NOT 7/8 or a reliable nationwide win rate. All eight examples came from only four games played October 31, so this is insufficient for probability calibration, injury-impact scoring or betting validation. V04 stays primary.

### QB-score promotion safeguard — benchmark the active model, not V03

The QB conditional model's existing prospective grade file compares each forecast to a **V03** reference. V03 was quarantined for substantial home-field bias, so outperforming it does **not** demonstrate improvement over the site's live **V04** independent scores. Milestone 1D now stays blocked until the grader supplies a **same-game, predecision-frozen, source-hashed V04 margin MAE** on exactly the same QB forecast cohort. Synthetic tests include a V03-only false win, wrong-sized pairing, and candidate performance worse than V04. This restriction does not invent missing archived V04 comparisons: the necessary paired V04 grade collector remains future engineering work. No automatic model promotion is permitted.

### Milestone 1D source-controlled comparison requirement

[PR #59](https://github.com/The-Caves/cfb-model/pull/59) completed on November 3 (1,109 regression tests passing). Since V03 was quarantined for anomalous home bias, the QB scoring candidate cannot be considered validated merely for beating frozen V03 margin MAE. The Milestone 1 readiness gate now requires **the same exact prospective games, source-hashed before kickoff, with a frozen V04 baseline** plus a lower QB candidate margin error. The current shadow-grade pipeline reports a V03 comparison but **not yet that V04 comparison**, so 1D correctly remains blocked. Future work: implement authenticated same-game V04 paired collector, then validate across independent weeks without altering archived forecasts. This stricter gate does not claim a new QB impact coefficient.

### Source-hashed V04 comparison for QB research (November 3 engineering)

The paired-score collector `scripts/qb_v04_archive_pair.py` now uses actual, separately archived website V04 scores from `research_2026/site_board_snapshots` rather than rebuilding V04 with later game results. For each independently settled QB shadow, it selects the latest V04 site capture **at or before that QB shadow**, at most six hours old, for the exact same game ID, home, away, and kickoff. Both captures must have 24–72 hours before kickoff; the website archive's source hash and V04 non-V03 provenance are checked. This is an *asynchronous prior-captured* active-model comparator, **not an exact simultaneous forecast**. Missing or postdecision V04 scores are explicitly unpaired and do not receive estimated controls.

The original `candidate_shadow_grade` research-grade artifact is not overwritten. A new per-run `qb-v04-paired-grading-RUN.json` records the source hashes, timing, matched and unmatched cohort counts, and conditional same-game V04 MAE. Milestone 1D now requires **all graded QB games to have source-verified prior V04 receipts**, at least **100 scored QB research forecasts spanning three separate football dates**, and improvement over both the **existing V03 no-QB ablation** and the **active frozen V04 control**. These are necessary research-readiness gates, not proof of causality, calibrated confidence, or profitability. The sources and controls remain immutable; retrospective source publication dates are not claimed to be authenticated.

[Relevant original validation plan](V04_VALIDATION_READINESS.md). Milestones 2–5 remain the same and shall not be discarded or automatically promoted.

### November 3 production audit: zero legacy V04 matches and source-aligned remedy

The completed [Data Intake 41734586143](https://github.com/The-Caves/cfb-model/actions/runs/41734586143) passed its code checks but the read-only earlier-website comparator found **0 of 45 eligible QB-conditioned frozen grades** with a valid earlier same-game V04 control in the six-hour/24–72h window. This is a missing *capture-coordination* problem, **not evidence that QB adjustment beat V04**. It is explicitly recorded as 45 unmatched and Milestone 1D remains blocked.

The new `qb_v04_same_intake.py` provides a prospective solution: before the QB forecast is generated, the same GitHub Data Intake freezes the independent V04 model's scores using the already retrieved, checksum-bound football score CSV, dated score manifest, and exact as-observed future fixture context. It employs the **same V04 fit/predict functions** as the website, with the same football-day embargo, no future game scores, no V03 total reuse, and no betting lines. The resulting before-QB score receipt is bound by hash to each QB shadow game **before immutable GitHub archival** and later graded on the same selected game and observed final.

These are independent V04 **same-intake research projections**, **not claims that the public website had displayed the exact same number at that instant**. The pre-existing earlier-site comparison remains available for older runs, but same-intake receipts are distinguished in the per-game audit and never mislabeled as website snapshots. Existing historical forecasts are unchanged, and old unpaired examples cannot be backfilled with these new predictions.

Milestone 1D still needs 100+ actually paired, independent future QB forecasts on at least three game dates, and source-authenticated improvement against active V04 and the no-QB ablation. No QB replacement effect is promoted. Milestones 2–5 remain preserved.

### Predeclared post-instrumentation QA cohort — prevents false perpetual gate failures

The source-hashed V04 collection began only on November 3. Existing 45 previously graded QB research games have **no independently archived contemporaneous V04 score** and will remain visibly unpaired forever; they must not be retroactively supplied one. Requiring all old results to carry the new data would make Milestone 1D structurally impossible. The new audit separately counts **all** graded games (including prior missing baseline controls) and the source-declared **post-instrumentation** QB forecast cohort.

Research readiness can therefore be tested on *the correctly selected post-instrumentation cohort*: at least **100 genuinely paired QB+V04 games**, on **three distinct football dates**, with **at least 90% pairing coverage among all QB-conditional games that were flagged as instrumented before outcomes**. Missing scores count against coverage, not silently removed. The QB model must beat **both V04 and the no-QB V03 research ablation** on the exact same paired games; those control errors are recalculated and checked against the game-level receipts, not accepted from aggregate claims. Game identity, source SHA, predecision/forecast clock and model PASS requirements remain mandatory. This is a *necessary research evidence gate*, not permission for automated promotion or an assertion of injury-causal impacts. Earlier unpaired 45 remain in the performance report.

## Milestone 2 — Evolving team and individual intelligence (retained)

**Status: partially implemented, not complete.** Improve opponent-adjusted recent offense/defense, remove schedule and turnover-luck distortions, distinguish genuine structural changes from one-game outliers, and expand positional participant intelligence (QB/rushing, OL, pass rush and coverage). Existing V05/V06 models are separate, V06 covered only **13 of 301** historical heldout games with enough 3-vs-4 evidence on both teams. Require matched, strictly earlier-game score and quality tests, predeclared ablations, useful prospective lift before any live adjustment.

## Milestone 3 — Advanced opponent-specific matchup scoring (retained)

**Status: research prototype.** Connect run-heavy teams versus rushing defense, pass EPA versus pressure/coverage, QB responses to pressure, offensive line vs opponent defensive front, explosive plays, early-down success, fourth-down and red-zone outcomes. Carry explicit unavailable and source-time flags. Train only from time-correct actual matchups and compare each feature family to the unmodified reference on identical future games, not on favorable anecdotes.

## Milestone 4 — Full-game possession simulation (retained)

**Status: prototype, not calibrated.** Derive genuine historical drives, field position, pace, time remaining, possession and scoring event attribution, correlated possessions and overtime handling. Produce SU, ATS, and game-total distributions only after authentic predecision model context and lines are available. Check out-of-sample calibration against independent future scores, including extreme margins and totals.

## Milestone 5 — Independent model competition and promotion (retained)

**Status: paired evaluation infrastructure implemented; predictive superiority unproven.** Compare V04, V05, V06, mixtures, other challengers, and the contemporaneous sportsbook on **exactly the same games**. Freeze each model, line timestamp, QB availability, confidence, PASS, result and cancellation before kickoff. Require independent market close snapshots and multiple prospective weeks. Track winner accuracy, absolute margin/total error, signed bias, ATS/O-U on *actual issued research selections*, PASS coverage, and calibrated edge probabilities. Existing `v05_competition_gate` deliberately forbids automatic promotion, even if a backtest improves.

## Next work after this Milestone 1 engineering pass

1. Review a *new* real intake artifact's verified starter count and actual postgame gamebook starter labels. Prioritize official university/coach statements rather than trying to guess every QB1.
2. Expand the registry of **verified original source articles** only when the publication and observation timestamps are defensible. Do not backdate newly found sources into previous slates.
3. Crosswalk independently observed QB1/QB2 past participation with previous team/transfer history, train a calibrated opponent-adjusted replacement challenger from actually verified events, and keep low-coverage games PASS.
4. Grade it prospectively before promoting, then resume Milestones 2 → 5 in this documented order.

**Non-negotiable:** A green CI run means code works; it does not mean the quarterback evidence or prediction accuracy requirement has been met.

## November 3 — Miami (Ohio) injured-QB selection incident and safer player inputs

**Observed public evidence:** Miami University's [October 29 Buffalo preview](https://miamiredhawks.com/news/2026/10/29/football-redhawks-put-win-streak-on-the-line-versus-buffalo-on-tuesday) explicitly says **David McComb and Thomas Gotkowski will miss the remainder of 2026**. It says **Caleb Heavner is expected** to make his fifth start November 3; this is a strong dated university *expectation*, **not** an independently verified literal starter confirmation. FanDuel not offering McComb is a warning signal, not a stand-alone proof of injury or starting status.

**Root cause confirmed in code:** `scripts/site_player_props.py` originally selects the highest projected passer from historical ESPN boxes even when `scripts/official_longterm_qb_absences.py` has separate reviewed university season-OUT data. The source registries also previously permitted only one long-term-out QB per team, losing multi-QB cases. Official SEC/Big Ten/ACC/Big 12 gameweek availability does not guarantee MAC or nationwide injury coverage. Historical passing leader, third-party QB1 chart and sportsbook prop listing are not starter confirmations.

**Fix committed:** The reviewed source registry now holds **both** Miami absences with distinct `team + player` keys and a first-use timestamp (no backdating). The official-outage dashboard and future expected-starter scenario filters apply all eligible QBs, preserve conflicts and provenance, and do not infer the next starter or alter archived scoring. PlayerForm excludes the same unavailable QB from passing *and QB rushing* forecasts, includes an independently reviewed game-specific starter gate, and retains existing all-position conference OUT/DOUBTFUL/SUSPENDED/CONFLICT suppression. QB header and university absence notices now avoid promoting a previously reported injured passer. Unit tests cover duplicate QBs, pre-source and pregame cutoffs, fallback selection, and immutable V04 scores.

**Still incomplete / acceptance gates (Milestone 1 and later Milestones 2–5):**
1. Obtain much broader **free, official, source-dated injury/availability coverage** for all FBS teams, including independents and MAC, and player identity with **correct position/team/season/game**. Track coverage and report `UNKNOWN` rather than healthy when missing. Do not derive a diagnosis from a boxscore, prop board or unofficial rumor.
2. Feed time-safe, verified all-position participation context into *newly frozen* model training/features. QB replacements, missing RB/WR targets, offensive-line units, DB coverage and pass rush need observed participant usage and opponent interactions; do not invent player-point penalties or overwrite earlier forecasts.
3. Keep **expected vs confirmed** QB identities distinct; a university future tense "expected" statement may inform a projected scenario, never a confirmed starter count.
4. Establish opponent-adjusted, position-specific leave-one-out/ablation tests on *held-out future games* versus the concurrently frozen V04 score model. Measure starter identification accuracy, position/source coverage, margin/total MAE and confidence/PASS performance, with explicit source-time gates. V04 remains the site's active unvalidated scores until independently better evidence exists.

**Validation:** GitHub Actions Data Intake and CFB Research Dashboard jobs must run and pass on the final code commit; check actual run receipts rather than relying on this dated documentation. The incident fix addresses **incorrect player display/projection and uncertainty gating**, not yet calibrated injury-driven score recalculation. All historical pre-review archived forecasts stay unchanged.


## November 3 — Data Intake personnel reconciliation (new Milestone 1 safeguard)

The original injury and QB observations already existed but were fragmented across per-conference reports, game-specific QB review, university season-ending announcements, expected-QB candidates and website-only player projections. The **Data Intake** pipeline now has a canonical, observed-as-of **all-position personnel evidence board** at `scripts/personnel_intake_board.py`, written per GitHub run to `data/pregame_evidence/personnel-intake-board-RUN.json` and published in the `cfb-qb-role-profiles-RUN` archive. It runs after the existing `qb_longterm_expected` safety filter; it is not a second injury scraper.

Each future ESPN game/team is keyed to exact opponents and kickoff; reports retain player, position, status, source URL and observed/published timestamps, including source-reviewed season-long QB OUT. A verified current QB must match a reviewed, exact-game official claim in the same as-of context; passing leaders, depth rankings and a sportsbook prop listing do not certify starters. An unconfirmed starter is explicitly projected or UNKNOWN, conflicts are review-only, and missing school reports remain UNKNOWN rather than a healthy-roster zero. All positions (RB/WR/TE/OL/DL/EDGE/LB/DB etc.) are carried from the accepted official conference reports, with non-QB injury status preserved individually. Outputs contain per-position counts, report coverage, reviewed QB coverage, unresolved conflicts and source quarantine totals.

**Important: the evidence board is not yet a trained replacement-value or injury-adjusted score model.** It never rewrites frozen forecasts or selects a player because the competing sportsbook lists their props. The next milestone is **source expansion across all 138 schools (especially MAC/G5)** plus a time-valid *player identity, team/position, participation and replacement contribution* crosswalk; only subsequently can a new candidate adjust team offense/defense, player opportunities or expected passing volume. Both game scores and prop models need prospectively graded ablations before promotion. The existing site directly ingests conference reports and reviewed QB absences; the intake board is a separately archived audit to reconcile upstream features before those future model changes.

**Operational verification:** code validation on ordinary pushes runs unit tests only; a *full live intake* occurs on the schedule, manual dispatch or a designated `[run-intake]` push. Require successful real `ingest` job with a populated `personnel-intake-board` artifact and nonzero actual game/team slots. Missing official sources or zero confirmed starters are evidence limitations and must be reported, not misrepresented as a successful starter solution. CFB repository only; never use CBB feeds.


## November 3 — centralized conference intake expansion, truth vs proxies

**Confirmed free source discovery (no per-school injury scraping required):**
- HD Intelligence structured official reporting: [SEC](https://www.secsports.com/fbreports), [Big Ten](https://bigten.org/sports/2026/9/10/FB_Availability_Reports.aspx), [ACC](https://theacc.com/sports/2025/8/28/availability-reporting-football.aspx), [Big 12](https://big12sports.com/sports/2025/8/14/FBreporting.aspx?lv=true), [MAC](https://getsomemaction.com/sports/2026/7/28/FB_0728265050.aspx.aspx), and [American](https://theamerican.org/sports/2026/8/6/football_player_availability.aspx). The MAC and American official portals both embed `app.hdintelligence.com`, with conference/source IDs matching `MAC` and `American`, respectively. These two conferences have now been registered in `scripts/official_availability.py` using the existing public-source capture, report authentication, per-player position parsing and fail-closed exact-game matching. MAC "Miami" is explicitly matched to Miami (Ohio) **only** when extracting the MAC official feed; it is never a global Miami alias. Expand tests with Miami (Ohio) vs Miami (Florida) and American South Florida canonicalization.
- **Different-format official conference portals** identified for the [Mountain West](https://themw.com/sports/2026/8/21/reports.aspx), [Sun Belt](https://sunbeltsports.org/news/2025/8/20/sun-belt-to-institute-availability-reporting-for-2025-football-season.aspx), [Conference USA](https://conferenceusa.com/sports/2025/8/23/FB_0823254134.aspx), and [Pac-12](https://pac-12.com/news/2026/9/11/2026-football-reports.aspx). These are **verified source discovery, not working automated ingestion**. Each requires bounded publisher-specific source parsing and a live, publish-time matched acceptance test. Do not copy the HD Intelligence parser into those pages without checking their data formats.
- Most conference policies limit mandatory publication to **conference matchups**. Do not assume every FBS game or independent has a report or that an unlisted player is confirmed to start. Even a fully official injury/availability report is **NOT** the published starting lineup. There is no verified free, universal pregame *confirmed starters* feed in this project. No sportsbook prop listing, ESPN season passing leader, third-party depth QB1 or last-week starter may be promoted to a verified current starter.
- Added to the independent `personnel_intake_board`: `current_qb_candidate` and `starter_eligible_for_model_input` are populated **only for exact-game independently reviewed confirmations**, after screening current official OUT conflicts. Any unconfirmed chart/history QB is exposed separately as `historical_or_chart_qb_scenario` with `PROJECTED_NOT_CONFIRMED`, never passed off as actual. This disallows precisely the historical-leader mistake observed in Miami (Ohio). The website's research scenarios and frozen live V04 scores remain separate; do not claim they automatically consume this new field.

**Milestone 1 acceptance is NOT CLOSED by a successful source-list change.** The fixed gate still requires 25% game-specific pregame confirmed QB slots, 25 independently verified QB replacement events, 60 both-starter-reviewed games, 100+ properly paired prospective forecasts on three football dates, >=90% post-instrumentation V04 pairing, and independently meaningful lift versus the contemporaneous active V04 and no-QB control. The 2026 first-party availability expansion increases *potential injury coverage*, not verification of actual starters. Only freeze a newly generated score model once as-of player/position identity, expected usage and replacement-value effects have been tested without leakage.

**Operational action:** trigger real Data Intake with `[run-intake]`, verify live accepted MAC/American report counts (not merely successful API requests), inspect `cfb-qb-milestone1-RUN` and `cfb-qb-role-profiles-RUN` artifacts. Source outages and unreported games stay UNKNOWN and separately auditable; preserve other milestones while collecting prospective outcome evidence.


## November 4 — shared current QB identity across site, player stats and gamebook audit

**Shipped / test-gated:** `scripts/site_depthchart.py::select_pregame_qb` is now the single source of game-specific quarterback identity for the displayed QB label, `site_player_props.py`, and the prospective `site_decision_archive.py` snapshot. It prefers an independently game-specific confirmed starter; otherwise uses the first credible current chart QB **after** excluding official `OUT/OUT_FIRST_HALF/DOUBTFUL/SUSPENDED/CONFLICT_REVIEW` and reviewed university season-out players. `RECENT_GAME_PASSER` is not eligible as an expected starter. A conflict results in `CONFLICT_REVIEW` / no named selection. Each result has explicit `CONFIRMED_THIS_GAME`, `PROJECTED_DEPTH_CHART`, `UNKNOWN`, or `CONFLICT_REVIEW` and source URL/time where available.

**Downstream:** QB passing-yard research outlooks select precisely the current named QB, rather than the highest historical passer, and pass on missing or unsampled current players. Historical QB rushing numbers cannot silently become the team's rushing-player pick if that QB is no longer the selected expected QB. An identity mismatch between the website and the player-prop component raises an error, and `cfb-site.yml` checks this contract before deployment. Source-matched original V03 / V04 scores, ATS and totals remain unchanged.

**Prospective measurement:** `site_decision_archive.py` now freezes each displayed `qb_pregame_expected_home/away` with source URL and capture date next to the existing immutable model score, or explicit `null` for older snapshots; these are **observations**, not verified starter outcomes. Only a *subsequent independent named gamebook QB starter* may provide an actual outcome label. Compare future same-game/team pairs to measure correct expected QB rate by confirmed / chart / unknown source and days or hours before kickoff; never use eventual starters as previously-known pregame features.

**Next meaningful model iteration (no new 1A.x substeps):** Apply the verified, sourced pregame identity/availability features to an independent **non-promoted** QB-aware score challenger, estimating player impact from past-only recorded production and genuine labeled replacement participation. Compare it prospectively to the same-run V04 predictions; report missing labels, per-group coverage, error changes and PASS. Until independent before/after replacement cohorts exist, do not invent a universal QB2 points penalty or claim predictive lift. A green unit test is a coding checkpoint, not proof of the milestone's evidence gates.


## November 5 — real-data team opportunity-budget simulation gateway

**Problem corrected:** Existing `player_prop_joint_simulation.py` shared the game drive count but projected individual player workloads separately, potentially assigning more modeled pass/rush attempts than the team could run. It now optionally calls `player_prop_team_budget.py` to constrain every same-trial player to one sampled team pass/rush attempt allocation, cap receptions against plausible completions, and preserve explicit **unallocated unknown-player opportunities**. Team scores/picks and historical freezes are unchanged; without a valid budget the original simulation runs but declares the conservation source missing.

**Real free source implemented:** The 2026 ESPN-derived SportsDataverse `espn_cfb_team_box` release includes each team's `completionAttempts` and `rushingAttempts`, `espn_cfb_drives` supplies game/team drive identities, and `cfb_schedules` supplies exact ESPN fixture IDs and completed status. `scripts/player_prop_team_box_source.py` now extracts source-schema-complete two-team historical attempt counts and team drive counts with strict team ID, season, source capture, and Eastern football-day cutoffs. This is an automatically schema-reconciled **source-observed research record**, not a verified gamebook / retrospectively authenticated original source publication, and it cannot be used to re-grade forecasts from before its actual capture. Drive identity counts are not proof all drives, offensive scoring or player snaps were published completely.

**Actual read-only public dataset CI:** [CFB Player Workload Source Probe run 42074693522](https://github.com/The-Caves/cfb-model/actions/runs/42074693522) downloaded the real release data and verified **12 of 12 upcoming FBS matchups inspected had at least three matched historical attempt/drive observations for BOTH teams**. This is preliminary *source readiness*, not a model accuracy grade. The new audit is `.github/workflows/cfb-workload-source-probe.yml`, downloadable as `cfb-workload-source-probe-RUN`. It does not spend money on a subscription, publish bets or mutate the live site.

**Single next integration objective:** Produce and archive a **non-promoted** real-data, pre-kickoff workload challenger for the same actual upcoming games and selected roster/position identities, alongside a prospectively frozen PlayerForm baseline. Evaluate matched QB passing, rushing and receiving MAE, participation/DNP unknown coverage, calibration and properly sourced market lines. Do not assume correlated play-by-play or drive-scoring simulation is ready; `observed_drive_fit` still requires actual reviewed offensive-scoring attribution. Do not move the website model unless held-out outcomes show an improvement. This is the ongoing simulation/player opportunity roadmap, **not** a new Milestone 1 subdivision.


## November 5 — website usability, archived model lineage and live scoreboard

**Delivered:** CFB Lab's game cards prioritize V04 opponent-adjusted projected scores, winner/total, and current observed spread/total; moved dense QB evidence, player stats, V03 quarantine details and scouting into an accessible expandable disclosure. Improved model/market/live/alert color hierarchy and mobile spacing without modifying forecast calculations. The data panel explicitly identifies V04 as the current **displayed research** scorer, V03 as the frozen original model and V05/V07 as **unpromoted** experiments; this is not a claim of externally validated predictive lift.

**Performance retention:** The existing `site_performance` and `site_player_stat_performance` operations remain fully intact. Historical forecasts, version-specific challengers, passed selections, retrospective grades and original timestamps stay in the append-only `context-state` archive; none are erased on website redesign or scorer version change.

**In-progress games:** `scripts/site_live.py` captures actual ESPN `state=in` scoreboard game scores and attempts to join the latest **pre-kickoff, archived V04** score/market research snapshot by ESPN game ID, exact teams, kickoff and source observation. No after-kickoff score adjustment to historical V04 is permitted; mismatches and missing snapshots remain explicit. Dedicated Live tab shows actual scores and pregame pick lineage separately. Game-night GitHub site builds target roughly 30-minute source refresh, not a streaming or guaranteed real-time score; client can check for a newer published snapshot on refresh. Research-only, no in-game probabilities or betting recommendations.

**Next model milestone:** source date/game/period-by-period in-play events and post-start playing personnel, then fit a distinct score-state and remaining-possession simulator with walk-forward predecision snapshots and independent calibration. Only after held-out comparisons against no-update / market baselines should we surface an experimental in-game projected final and probability. Do not claim the UI alone supplies in-game forecasting.



## November 8 — opponent-specific scoring repair / V08 retrospective challenger

**Root cause established:** V04's live home/away scores come from independent opponent-team scoring and neutral-strength estimates fitted to final scores. Although `team_matchup_intelligence` already computed offensive run/pass EPA against defensive allowance, pressure and explosives, red-zone play success, and ESPN-confirmed two-sided turnovers, **those existing matchup descriptions are not part of V04's fitted point estimates**. Showing scouting on the website alone did not fix Georgia–Ole Miss or other major matchup misses.

**Game diagnosis, postgame only:** November 7 Georgia 42–7 Ole Miss was a five-sack/66-rushing-yard/two-giveaway Ole Miss performance versus Georgia's 295 rushing yards. This is an outcome explaining the failure, **not** evidence those exact rates were knowable pregame. Player-specific offensive-line/front disruptions, pressure-sensitive QB passing, run-stopping ability, red-zone finishing and opponent turnover opportunity are essential candidate mechanisms, not automatically learned causal coefficients.

**Implemented research stage:** `scripts/v08_matchup_v04_comparison.py` runs a **V08 opponent interaction challenger versus refit V04** on exact same held-out games and source identities, with separate predeclared run-vs-run-defense/pass-vs-pass-defense, pass protection/pressure, explosive-pass-defense, red-zone, and turnovers/takeaways families plus a combined candidate. The training/test fold cutoff uses earlier football dates; missing source coverage is PASS, not presumed zero or converted to favorable games; each group has its own identical-game V04 comparator. `tests/test_v08_matchup_v04_comparison.py` safeguards identity, winner/margin/total comparability, and missing source refusal. The research script is integrated into Data Intake as `cfb-v08-matchup-v04-RUN`, with an explicit nonpromoted artifact. The source-derived features are from retrospectively retrieved 2026 PBP / boxscores, whose historical first-publication timestamps are not independently authenticated; **do not recalculate or rewrite frozen 2026 picks from these features**.

**Improved turnover mechanism:** Scouting can now pair team giveaways **per verified offensive drive** with the opponent's historical takeaways **per verified defensive possession**. Require at least two earlier verified two-sided ESPN boxscore+drive games; otherwise UNKNOWN. This is a descriptive susceptibility feature, not a fixed turnover probability or an automatic points penalty. The original unscaled turnovers remain separately available for ablations.

**Red-zone limitation made explicit:** Existing advanced-data `redzone_success/redzone_plays` is a **play-level success** signal, not ESPN team red-zone trips, touchdowns/trip, or field-goal share. The new matchup feature pairs a team's offensive red-zone *play* success against what the opponent allowed in prior games. We must source actual team red-zone trips, TDs and FGs from completed officially matched boxscores and estimate finishing efficiency *before* claiming a calibrated red-zone scoring adjustment. Do not call the existing play-level input a touchdown conversion rate.

**Why feature count alone fails:** November 8 archived V03-family 394-game retrospective ablation had baseline margin MAE **13.89159** and SU **0.63959**, run/pass matchup MAE **13.91409** / SU **0.63959**, turnovers MAE **13.90951** / SU **0.64213**, and the entire feature bundle MAE **15.58506** / SU **0.61929**. More indicators without regularized, fully source-paired interactions worsened performance. These experiments compare against V03, **not** V04; do not promote from them.

**Next decisive test (one goal, not nested milestones):** Verify V08 versus the actual V04 reference for the same held-out game IDs, report cohort size, weekly margin and total MAE, winner/Brier where properly calibrated, 20+-point error tail and important misses (Georgia–Ole Miss, Alabama–LSU, Oregon–Ohio State), plus missingness. Then build a *predecision* frozen adjustment candidate with real red-zone trip and turnover/pressure opportunity evidence, evaluated prospectively versus no-interaction V04 and a suitable market baseline. Never invent past odds, regress on this weekend alone, infer a turnover is automatically 7 points, or overwrite any historical performance grades. User's **7–3 against the spread** on the ten highlighted games is a different selection cohort from V04's **4–6 straight-up**; grade them separately.


## November 13 — V10R2 source-observed possession simulator, as-of profiling, and convergence

**Completed engineering:** [V10 original source intake](/The-Caves/cfb-model/actions/runs/43488854033) authenticated 387 out of 693 ESPN-completed 2026 games for two-sided real drive IDs, yards-to-goal, drive ending, score attribution and ESPN boxscore turnovers. 306 cases remain quarantined; do not impute drives. The Monte Carlo generates a sequence of actual position-conditioned possession outcomes and distinguishes offensive points from interception/fumble return scores, offensive giveaways, defensive takeaways and next-drive field position. Every historical simulation fits only games on earlier *calendar football dates*, not the match being forecast. Pre-original-date availability of some retrospectively downloaded PBP remains unverified.

**Added V10R2:** prior offensive and opposing defensive observed EPA, pass/rush EPA and tendencies, play-success/explosive rates, third-down conversions, pressure, red-zone play success and independent turnover rates, with a 28-day half-life on advanced-game exposures. Unknown metrics do not become zeros. A new *V04-anchored* drive variant uses a frozen earlier-fold opponent-adjusted home/away V04 expected-score prior to affect TD/FG outcomes **inside** each possession, never refitting V04 or overwriting past published picks. A separate challenger regresses turnover risk toward the league rate when offense/defense evidence is sparse. The full V04 engine is **not** yet replicated as a feature-for-feature latent-state model: actual QB starter replacements, injuries, precise weather and travel, calibration and down-and-distance/clock simulation are still missing or not independently verified for historical weeks.

**Paired held-out retrospective test:** GitHub Actions run [43491615567](https://github.com/The-Caves/cfb-model/actions/runs/43491615567), on the exact prior 387-drive-game source archive, 379 identical 2026 V04-evaluable matches, 2,000 draws per simulation family. In the 379-game cohort, V04 margin MAE **12.9085**, total MAE **13.5322**, SU **248/379 (65.4%)**. Basic empirical drives margin **14.5990**, total **13.9839**, SU **218/379**. Matchup-aware drives margin **14.6362**, total **14.0443**, SU **216/379**. Turnover-regressed drives margin **14.4821**, total **14.0052**, SU **219/379**. V04-anchored drives margin **13.9010**, total **14.0332**, SU **230/379 (60.7%)**. V04-anchored hypothetical raw ATS **78/156 (50.0%)**, O/U **69/154 (44.8%)**, versus V04 raw ATS **70/156 (44.9%)**, O/U **62/154 (40.3%)**; these are sparse **unfiltered sign-of-margin** choices on authentic but not verified-closing sportsbook quotes, not official picks or proof of a winning strategy. V04 remains better on SU and both score errors. **NO PROMOTION.**

**Monte Carlo convergence:** deterministic selected game runs of **500 / 2,000 / 5,000 / 10,000** trials (same historical model inputs and seed) found 5,000-to-10,000 win-probability movement of **0.39 pp** for Tennessee–Kentucky, **0.16 pp** for Kentucky–LSU, and **0.48 pp** for Oklahoma–Kentucky. One 500-to-10,000 comparison moved **3.83 pp**. These measure sampling stability, **not model accuracy or calibration**. The engine uses Wilson sampling uncertainty to avoid false zero-width intervals at extreme small-sample outcomes. Reasonable policy: 2,000 for broad challenge screening, 5,000 for independent routine distribution generation when ready, and 10,000 for stable final probability display; more simulated games cannot repair incorrect possession probability calibration.

**Next:** compare V04-anchored drive vs bare V04 only with genuine independently frozen pre-kickoff forecasts, authentic source-time matchups and historical bookmaker prices. Collect official QB starter confirmation/injury/equipment and weather observations, validate turnovers and field position with independent sources; calibrate winner/ATS/totals distributions over new later weeks, then consider market-aware PASS thresholds. Keep current V04 as the active website projection until a challenger consistently improves independent held-out margin/totals and calibrated probabilities. Do not change archived original predictions or grade records.

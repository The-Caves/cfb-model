# College Football Model — current prioritized roadmap (November 3, 2026)

This is the **current handoff and order of work**. The existing [next-generation design](NEXT_GENERATION_MODEL_ROADMAP_2026.md), [V05 robust scoring](V05_ROBUST_RESEARCH.md), [V06 opponent-adjusted trajectory experiment](V06_REGIME_RESEARCH.md), and [long-term QB source controls](OFFICIAL_LONGTERM_QB_ABSENCE_RESEARCH.md) remain relevant. Nothing in this roadmap authorizes automatic score-model promotion, changing a past prediction, or claiming a validated ATS advantage.

**Current live website:** V04 independent score projections with market-anchored research PASS gates; V05 displayed as shadow, V06 an additional chronological benchmark. V03 remains quarantined for home bias. Frozen predictions and market quotes are archived separately from final labels.

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

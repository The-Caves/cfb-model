# v0.4 Step 3D — GitHub pregame-to-postgame research archive

**Scope:** 2026-only, no AWS or paid storage setup, `PASS_UNVALIDATED`. Preserve the evidence that genuinely existed before games, and link real final results only later.

## Architecture

Every scheduled/manual `CFB 2026 Data Intake` run first collects ESPN completed results, builds 2026 retrospective team-profile histories, captures future pregame profiles and personnel joins (Step 3C). The new Step 3D archive stage:

1. Validates that pregame capture and joined features share the exact numeric `GITHUB_RUN_ID`, source checksums, game IDs, kickoffs, teams and observed timestamp. The capture must be newly observed (within 30 minutes of archival). No retrospectively fabricated September capture is allowed.
2. Commits a compressed, **append-only per-run pregame bundle** (source capture plus personnel-feature join, with their SHA-256 checksums) to `context-state/research_2026/pregame/YYYY/MM/DD/run-<id>.json.gz` and appends per-game metadata to `research_2026/pregame_index.json`. Existing dated paths are never overwritten with different bytes.
3. Reads the current **successful** ESPN scoreboard manifest and observed completed scores with a fresh timestamp. A final result can be linked only to an older indexed observation using the **predeclared latest capture between 24 and 72 hours before the game's actual kickoff** with matching ESPN ID, home/away, and kickoff. A rescheduled game keeps its old observation history, but only matching kickoff versions are eligible.
4. Commits separate compressed outcome records to `research_2026/outcomes/YYYY/MM/DD/<ESPN game ID>.json.gz` and updates `research_2026/outcome_index.json`. Outcome records contain the observed final score, calculated margin/total, original selected pregame metadata and observed/retrieval timestamps; the archived pregame bundle **never receives final scores**. Score corrections and changed eligible observation choices are flagged for manual audit and never silently revised.
5. Publishes `research_2026/summary.json` with archive counts and omissions. One GitHub commit atomically updates per-run evidence, indexes and new outcome records, using a non-force branch update. A read-back from `context-state` checks every committed artifact.

The context refresh and Data Intake workflows share the same `cfb-context-state` concurrency group, avoiding normal simultaneous branch writers. A conflicting outside writer fails the non-fast-forward push rather than overwriting it.

## Research caveats

This archive records what GitHub Actions actually captured and **when it observed** the source. It does not independently attest upstream ESPN publication time, source-provided historical revisions, or immutable external custody. Git commit history can be altered by administrators. GitHub retention policies and repository size limits still apply; the branch accumulates compressed observations and may require bounded retention / cold archival later. The optional S3 job is still present but not enabled by Step 3D; no AWS dependency or charge was added.

Team profiles include underlying retrospective PBP files that are not authenticated as published before all earlier games. We preserve that limitation in source flags; new archives do not retroactively validate previous 2026 backtests. Official team report coverage and verified starting QB coverage are partial; unreported statuses stay UNKNOWN. `scoreboard.retrieved_at_utc` is the first confirmed observation **by our workflow**, not the precise instant ESPN originally published the score. Historical FanDuel pregame lines remain unavailable, so ATS/O-U accuracy or financial ROI must not be fabricated. No picks or model changes are promoted.

**Files:** `scripts/personnel_results_archive.py`, `tests/test_personnel_results_archive.py`, `.github/workflows/cfb-data-intake.yml`.

## Next: accumulation and evaluation

Once numerous distinct postgame finals have a 24–72h original observed pregame capture, load indexed outcomes and selected pregame bundles as a verified input pair for `scripts/personnel_ablation.py`. Require chronology-safe label availability, sufficient matched test sets, no split overlap, and train-only standardization/regularization. Report sample size, missingness and baseline/ablation performance. Only then consider promoting a version, and keep source-provenance caveats intact.

## Final-game safety: settlement without future games

The daily [CFB 2026 Observed Final Settlement](../.github/workflows/cfb-outcome-settlement.yml) workflow independently fetches recently completed ESPN games and invokes `scripts.personnel_results_archive --settle-only`. It reads archived, **previously observed** pregame indexes and creates separate final records when an eligible observation exists. No new synthetic pregame capture is produced. This handles final weekends and January 2027 postseason games when Data Intake may have no upcoming eligible FBS matchups left.

The job shares the `cfb-context-state` serialization group with Data Intake and Context Delta. It is active during the 2026 season and January 2027 (with an explicit calendar gate to prevent requests in other seasons). It skips Git branch writes entirely when there are no newly linkable finals. A 28-day scoreboard lookback reduces repeat requests; any skipped older final must be handled with a deliberate, validated longer lookback. In-flight score data stays separate from earlier pregame captures.

# Step 4 — Incremental pregame context refresh (2026)

## Automation now configured

New workflow: `CFB Pregame Context Delta` runs an **hourly scheduler** on GitHub Actions. The scheduler chooses when to perform a full context refresh:
- Baseline: 10:17, 16:17 and 23:17 UTC daily.
- Within 48 hours of any upcoming kickoff: every third hour UTC.
- Within 12 hours of any upcoming kickoff: hourly.
- Manual dispatch and explicitly tagged development test commits: immediately.
- If the 4-day kickoff probe fails: run a refresh rather than silently skip.

A separate read-only scheduled job already performs full scores, EPA, and advanced profiles three times daily. The context refresh uses only scores and upcoming ESPN events; it **does not** download the entire SportsDataverse play-by-play file hourly.

GitHub Actions scheduled triggers can be delayed, skipped during load, or disabled by repository settings. This is hourly **eligibility**, not a guaranteed real-time data feed.

## Persistent state, material deltas and kickoff freezes

The workflow uses `GITHUB_TOKEN` with `contents: write` to maintain a separate `context-state` branch in this repository. Runs are serialized by a concurrency group.

- `state/latest.json.gz`: most recent 10-day upcoming-game context snapshot.
- `history/YYYY/MM/DD/<UTC>.json.gz`: one immutable context snapshot per successful run, with as-of time.
- `deltas/YYYY/MM/DD/<UTC>.json.gz`: material field changes and source gaps compared to the preceding run.
- `frozen/<ESPN game id>.json.gz`: the last **observed pregame** snapshot when the game reaches kickoff. Never filled from postgame records.
- `state/geocache.json`: previously verified exact city-and-state matches for venue and home-base travel proxies.
- `state/personnel_sources_latest.json` and `sources/YYYY/MM/DD/...json.gz`: SEC/Big Ten report page hashes and published-source watcher status.

Initial historical snapshot retention starts only when the new workflow first succeeds. The old v0.9 model has no authenticated historic injury/weather snapshots.

## Delta alerts and controls

Material changes include a kickoff/venue change, 5+ mph forecast wind, 8+ mph gusts, 20+ percentage point precipitation chance, 8+ Fahrenheit temperature difference, confirmed change of a **sourced** QB starter, or changed sourced player availability. Data disappearing is flagged as *SOURCE_UNAVAILABLE*, not mistaken for player recovery or a calm forecast.

Deltas are written to GitHub and shown in GitHub Actions artifacts. **ChatGPT push notifications are not automatically configured.** See Actions for failures and context-state branch for persistent summaries.

## Personnel coverage limitation

The workflow automatically checks official SEC and Big Ten availability report index pages, recording the fetch status and content SHA256. Any changed page is flagged `CHANGED_UNREVIEWED`. These index pages can change for unrelated reasons and often embed reports inside iframes; the source watcher does **not** automatically identify player injuries or QB starters.

Structured game-level injury/QB records remain in `data/manual/availability_2026.csv`, which requires exact game, kickoff, reviewed official source, and pregame timestamps. The file is initially header-only. Missing or stale reports are `UNKNOWN`, **never assumed healthy**. Automated verified national QB/injury extraction and injury replacement-value weighting remain future work, not operational features.

Weather forecasts are forecasts **captured at run time**, not reconstructed historical pregame weather. Travel estimates use city centroids, not actual road/flight distance. Prediction model remains `PASS_UNVALIDATED`.

## Operations and security

Workflow definition: `.github/workflows/cfb-context-refresh.yml`. Only that workflow needs the repository `contents:write` permission; it does not create pull requests or access other repositories. If branch writes are blocked by repository Actions or branch rules, GitHub will fail explicitly and **must not** report success.

Audit by checking `context-state` and the newest `CFB Pregame Context Delta` run. Weather geocoding is cached between runs to reduce API calls.

## Live cloud verification — 2026-10-21

- [First persistent run](https://github.com/The-Caves/cfb-model/actions/runs/39551375776) created the `context-state` branch and archived 109 upcoming games, 57 forecasts, 63 games with both travel estimates, 109 with both rest intervals, and the first official SEC/Big Ten index-page hashes.
- [Second persistent run](https://github.com/The-Caves/cfb-model/actions/runs/39551772595) loaded the prior snapshot and produced a new history entry and delta. It collected 109 games, 70 weather forecasts, 79 games with both travel estimates, and 109 with both rest intervals.
- The second delta initially recorded 28 weather provider-coverage changes and individual missing weather fields. A subsequent regression-tested patch suppresses duplicate missing-field notifications: a forecast outage is a **source coverage event**, not a measured change to wind or temperature.
- The Big Ten index HTML hash changed in the second run and was labeled `CHANGED_UNREVIEWED`. **This does not verify any individual player availability change.**
- Neither run provided independently confirmed two-team injury status (0/109). No QB-starting confirmation or injury adjustment was inferred.
- For future runs, the persisted `asof_utc` is the **end of source collection**, after any weather or source index requests. Fixtures that kicked off while collection ran are excluded from the saved pregame snapshot, avoiding retrospective pregame-label leakage. Earlier archived snapshots retain their original timestamps and should be interpreted accordingly.

These checks establish that persistent daily/hourly infrastructure and source delta audits work. Official document-level player extraction and comprehensive availability coverage remain pending.

## Automated official SEC and Big Ten player-level availability (added October 21, 2026)

The collector now calls the same **public structured availability publisher** embedded on the official conference pages:
- SEC: https://www.secsports.com/fbreports
- Big Ten: https://bigten.org/sports/2026/9/10/FB_Availability_Reports.aspx

It ingests `/api/get-publish-public` for each conference, but **not historical archived reports as if they had been known pregame**. For every publisher card, it requires: a report with non-pending publication status, non-future publication timestamp in the reported conference timezone, the exact two publisher teams matched through the 138-team school alias map to **one** ESPN game on the same local date, kickoff still in the future, both teams' player rows successfully parsed, and publication/capture timestamps before the context cutoff. A partially parsed, stale, ambiguous, or unsupported card is quarantined and explicitly identified in `official_availability_manifest.json`.

When accepted, the source produces both team-level report attestations and individual `INJURY` designations with position when the official display row includes it. These are fed through the preexisting `availability_context.evaluate` and persist in timestamped context snapshots/deltas. Source capture is performed **before** the context issue cutoff; a later missing report never means a player recovered. Reports can cover only games in the conferences' official reporting programs, not all FBS teams. The current conference feed was tested while all upcoming cards displayed **Report Pending**, so no player-level claims were fabricated.

**Starting QB limitation:** A QB listed `OUT` or `QUESTIONABLE` is a sourced availability signal, **not** a sourced confirmation of who starts. This feed never emits `QB_STARTER` records and no backup or replacement-value score adjustment is inferred. Confirmed game-day starting QB reports still require a separate verified official source or manually reviewed and timestamped assertion. This is automated published **availability**, not automatic starting-lineup verification. No bets are enabled (`PASS_UNVALIDATED`).

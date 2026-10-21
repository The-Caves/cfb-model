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

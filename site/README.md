# 2026 CFB research dashboard

This is a mobile-friendly front end to real, frozen 2026 college-football model research forecasts. It is **not** a validated betting recommendation engine, and displays `PASS_UNVALIDATED` until the model has adequate leakage-safe out-of-sample evidence. It does not fabricate moneylines, spreads, totals, QB starters, injury diagnoses, or graded outcomes.

## What is built

- The responsive website is `site/index.html`: Eastern kickoff times, Today / Next 48h / All game filters, team search, projected scores, model total and **uncalibrated** home-win estimate, QB/injury source coverage warnings, provenance and performance panels.
- The exporter `scripts/site_export.py` reads the most recent pregame archive from `context-state/research_2026/forecast_index.json` and the indexed `forecasts/YYYY/MM/DD/run-*.json.gz` file.
- It validates the original forecast record with `scripts.personnel_forecast.verify`, compares the index checksum and record identity, rejects surprising sportsbook market data, and excludes games which kicked off before site publication. It keeps the exact originally frozen forecast capture timestamp.
- The export payload is schema v2 in `site/data/dashboard.json`. It exposes only public game identity, genuine numeric projections, 0–2 reviewed-QB and team-report coverage counts, original provenance, and explicit model limitations. Private sportsbook vault information and player-level detail are not exported.
- `tests/test_site_export.py` tests output safety, missing odds, time gates, index checksum, path traversal and compressed forecast reading.
- `.github/workflows/cfb-site.yml` builds and validates the dashboard on selected pushes, scheduled checks and manual runs. It also embeds the JSON into the generated HTML so the downloadable ZIP includes a self-contained **offline-viewable** page. No paid infrastructure or AWS is needed.

## Opening the website today

The GitHub Actions `CFB Research Dashboard` workflow creates an artifact called `cfb-website-preview-<run number>`. On a phone, download the ZIP from the most recent successful Actions run, extract it in Files, then open the HTML file. The exported HTML has its data embedded, so it does not require GitHub Pages for an offline preview. Note that its static forecasts will not update while the local file is open.

### Optional public web address

Earlier project instructions requested a private preview. **GitHub Pages creates a publicly accessible website**, so the workflow does not enable it automatically. If the owner chooses to make this research site public:

1. Go to repository **Settings > Pages**.
2. Under **Build and deployment > Source**, select **GitHub Actions**.
3. Open **Actions > CFB Research Dashboard > Run workflow** or let its next scheduled build complete.
4. Confirm an actual successful Pages deployment. The expected standard address, once live, is `https://the-caves.github.io/cfb-model/`.

Do not call that address live before verification. The Actions deploy job records when Pages is disabled; the preview ZIP remains available regardless. For a restricted-access website, use an authenticated hosting provider instead of public GitHub Pages.

## Remaining model limitations

Projections are **research outputs**, not calibrated bets. National game-specific QB1 evidence and availability are incomplete. The 2026 historical play-by-play availability times are not independently attested. Historical FanDuel lines are unavailable; SU/ATS/O-U retrospective and prospective claims require genuine, time-stamped markets and paired verified outcomes. Keep these limitations visible in the public site.

For official personnel-source verification and milestone exit rules, see `docs/MILESTONE_2B_OFFICIAL_SCHOOL_SOURCES.md`. Update this README and the milestone record whenever the publication contract or evidence changes.

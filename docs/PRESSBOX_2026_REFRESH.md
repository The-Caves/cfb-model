# PRESSBOX — November 12 interface and validation boundaries

## Website and markets
- Compact purple, black and white PRESSBOX branding replaces the oversized hero.
- Each card compares independently modeled V04 home margin and total with current ESPN-observed provider-specific sportsbook spread and total. Gap = model home margin + signed book home handicap, or model total minus observed total. Differences are arithmetic, not calibrated betting edges.
- Browser refreshes source-observed ESPN pregame quotes on the selected date, and every five minutes while the game desk is active. Identity/time/provider gates require exact ESPN game ID, teams, kickoff and valid upstream fields. CORS failure leaves the published quote. We do not infer opening/closing or in-play odds, or overwrite archived picks and grades.
- A single player disclosure splits away and home projected passing, rushing and receiving yards. Actual PlayerForm R1 conditional model output only; no verified sportsbook props, participation assumption or implied prop win probabilities.
- Weather data is attached by scripts/site_weather.py using immutable context-state/state/latest.json.gz. It requires matched game ID, teams, kickoff and source timestamps. Alerts for wind 18+ mph or gusts 30+, rain chance 60%+, cold 35F or below, heat 95F or above. This is city-level Open-Meteo forecast, not actual game observations, and never adjusts frozen scores. Missing means unknown.
- Live page remains an exact contrast between actual ESPN in-game scores and archived pregame V04 forecasts, not an in-game probability calculator.

## Simulation maturity
scripts/game_simulation_research.py already runs conditional empirical drive/possession simulations with win, cover and total distributions when supplied with source-timed historical drive fits. scripts/observed_drive_fit.py requires complete verified historic drives with scoring attribution and starting field position. The research_2026 context-state archive does not currently contain the verified complete game-drive bundle to fit the simulator automatically. No validated simulation-probability signal is powering production.
Next: capture and audit drive-level PBP and red-zone possessions, timestamp when records became available, run held-out walk-forward simulations against paired frozen V04 and market baselines, and only promote after independent results.

## QA
tests/test_site_market_browser.py, tests/test_site_weather.py, tests/test_site_ui_compact.py and existing site live, performance, QB and archived market tests protect the data contracts. Model coefficients, initial picks, permanent grades and starter-confirmation standards remain unchanged.
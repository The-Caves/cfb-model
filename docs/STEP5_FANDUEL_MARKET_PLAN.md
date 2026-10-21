# Step 5 — FanDuel-first market pipeline (design + 5A implementation)

**Status (2026-10-21):** Offline quote parser, secure opt-in collector, and tests implemented. The provider is **not yet connected**; no actual FanDuel lines, opening prices, historical market dataset, or model-derived bets have been ingested. All predictions remain `PASS_UNVALIDATED`.

## Primary source and book

Primary book: **FanDuel**, stable internal bookmaker key `fanduel`. Other books can be added explicitly to the same normalization schema without mixing their prices or line movement.

Initial candidate provider: [The Odds API v4](https://the-odds-api.com/liveapi/guides/v4/) (host `api.the-odds-api.com`, **not** similarly named `theoddsapi.com`). It documents the NCAAF sport key `americanfootball_ncaaf`, markets `h2h`, `spreads`, and `totals`, an explicit `fanduel` book filter, and a paid historical-snapshot endpoint. Provider-listed historical availability is not proof that FanDuel quotes were present for every FBS game or timestamp; a coverage audit remains required. API requests consume credits, so no automatic poll schedule is active yet.

## Three distinct price concepts

1. **Opening line (provider-verified):** Only if a trustworthy source labels a true opener or historical snapshots support the earliest quote the provider actually holds. A first recorded quote is called `FIRST_OBSERVED`, not `OPEN`.
2. **Line movement:** For the same game, market, selection and **same book**, preserve every usable quote with timestamp, spread or total and odds. Derive first-observed to current movement plus intraweek changes; do not attribute shifts automatically to injuries or sharp money. Cross-book comparisons are separate features, never a synthetic FanDuel movement.
3. **Decision-time price:** Freshest FanDuel quote whose capture/publisher timestamps precede the model's as-of cutoff and kickoff. Record quote age; if stale/missing or different from a displayed betting slip, request/accept the displayed price and timestamp, mark the mismatch and refresh. Never treat the model's run time as proof that the book price is executable.

Each moneyline, side of the spread and side of the total has its own American price. Alternate spreads/totals, player props, same-game parlay payouts and promotions are **not** covered by the initial featured markets feed.

## Parlay decision process (planned, not active)

- Get the exact FanDuel markets and timestamped quotes for eligible events.
- Run the actual validated model at an explicit pregame as-of cutoff, using only then-available team/game/context information. The existing score-only baseline is not a validated wagering model.
- Produce independently estimated moneyline/spread/total outcome probabilities, including uncertainty and confidence/pass thresholds; compare against FanDuel's implied probabilities and vig-adjusted baseline.
- Present price-specific estimated EV only when forecast calibration and validation support it. A team's likelihood of winning is not, by itself, evidence that a moneyline offers value.
- For multi-game parlays, test independence rather than blindly multiplying leg probabilities. Shared risk factors and same-game legs require joint-outcome modeling or conservative rejection. Actual FanDuel parlay/same-game-parlay quoted payout must be checked before displaying value; cannot infer SGP price from standalone odds.
- Recheck prices at the actual decision time. Do not submit bets, invent bet slips, or claim a leg was placed by the research pipeline.

## What is implemented so far

- `scripts/market_quotes.py`: pure parser for provider-v4 featured markets, validating event identity, two-sided spreads/totals, exact source timestamps and bookmaker-specific prices; quarantine invalid events, missing historical timestamps, post-kickoff snapshots and incomplete markets. Assign `UNMATCHED_PROVIDER_EVENT` until a separate vetted ESPN crosswalk exists.
- `scripts/market_quotes.py:movement`: first and latest observed prices for same provider game/book/market/selection, under an explicit cutoff. It never calls the first observed price an official opener.
- `scripts/market_client.py`: **opt-in** read-only FanDuel quote fetch. Uses `ODDS_API_KEY` environment variable; does not expose keys in returned JSON, user-facing errors, or source control. Offline fixtures are supported by its `provider_response` test argument. No scheduled calls or API keys are presently set by this project.
- Tests: `tests/test_market_quotes.py` and `tests/test_market_client.py`. CI is required to pass before adding future ingestion and backtest jobs.

## Implementation queue

**5A (current):** Validate candidate provider terms/coverage and historical timestamp behavior on a small licensed sample; choose an appropriate plan only if coverage and quota support the project. Do not buy credits automatically or ask for secrets in chat. Confirm response field types and FBS/FCS coverage.

**5B:** Build an explicit audited `provider_event_id -> ESPN game_id` crosswalk with home/away and kickoff consistency. Archive source snapshots and checksums in the project research store according to the provider's licensing; avoid committing proprietary or licensed bulk odds to the public `main` branch.

**5C:** Enable a bounded quote cadence after a provider is connected (e.g., daily baseline, several times per game day, and manual refresh on demand), with quota and error tracking. Preserve opening, early-week movement, pre-kickoff close, and decision-time quotes only when actually observed.

**5D:** Integrate calibrated opponent-adjusted matchups, historical markets, walk-forward baseline comparisons, SU/ATS/O-U grading, CLV diagnostics, and joint-parlay probability/correlation tests. Maintain frozen versions, ablations and strict `PASS_UNVALIDATED` until out-of-sample results are reliable.

## Public repo controls

Never commit API secrets, keys in URLs/logs, personal information, user location, wagering account data, unreleased/licensed provider data, or private conversations. Authentication is via secure environment/CI secrets only. Provider use must respect licensing and historical attribution. The provider's API quote may not match a region-specific or account-specific FanDuel slip; label this explicitly.

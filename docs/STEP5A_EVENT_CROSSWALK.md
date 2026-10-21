# Step 5A — Verified game identity and market coverage audit

**Status: implemented and offline-tested. No licensed historical market data or live FanDuel quotes have been retrieved.** The code is research-only and all outputs retain `PASS_UNVALIDATED`.

## Why an event crosswalk comes before odds ingestion

The Odds API uses its own `provider_event_id`; the model's schedule, scores, opponent-adjusted profiles and kickoff-safe snapshots use ESPN `game_id`. These identifiers are unrelated. The same teams may appear under different abbreviations, naming conventions, locations or neutral-site listings, and a postponed game's kickoff can move. A mistaken join produces misleading market features even if every quote is otherwise accurate.

## Current implementation

- `scripts/market_event_crosswalk.py`: loads the public 2026 alias registry `data/archive/2026_team_aliases.csv`, resolves **only exact curated aliases** or exact ESPN display names, and quarantines ambiguous aliases, name collisions, reversed home/away pairs and uncertain game identity. The incoming event must agree on both opponent identities, kickoff within a configurable 15-minute default tolerance, distinct ESPN team IDs and a unique provider-to-ESPN game link.
- As-of protection: the ESPN context snapshot must have been observed **no later than** the market quote's historical or live timestamp. Using an ESPN snapshot fetched after an earlier odds timestamp is quarantined, not counted as a verified historical as-of match. Post-kickoff/in-play quotes and completed-game context are not accepted.
- `scripts/market_coverage_audit.py`: reads a locally available v4 provider sample and timestamped ESPN snapshot, runs the strict quote parser and crosswalk, and writes **aggregate counts, source hash and quarantine reason codes only**. It does not export raw FanDuel lines or paid market prices.
- `tests/test_market_event_crosswalk.py` and `tests/test_market_coverage_audit.py`: offline fixtures for names, home/away, kickoff drift, missing ESPN as-of timestamps, duplicate events, historic leakage, alias collisions, bookmaker source filtering and no-price audit output.

## Example: audit a locally held, permitted sample

```bash
python -m scripts.market_coverage_audit \
  --provider-payload /tmp/odds_sample.json \
  --espn-context /tmp/espn_context_snapshot.json \
  --alias-registry data/archive/2026_team_aliases.csv \
  --retrieved-at-utc 2026-10-21T19:00:00Z \
  --bookmakers fanduel \
  --output /tmp/fanduel_coverage_audit.json
```

Add `--historical` only for a **real** v4 historical response with a provider `timestamp` and a compatible actual pre-cutoff ESPN snapshot. The `--retrieved-at-utc` records when that sample was downloaded; historical `observed_at_utc` comes from the provider's historical snapshot envelope and is not replaced with the download date. These example paths represent local input files, not data already in the repo.

If a school or kickoff cannot be uniquely matched, the quote is quarantined rather than attached to a different team. An audit with zero matches is a valid negative result; it does not establish that FanDuel lacks coverage.

## Provider facts to verify before enabling live or paid snapshots

The [official v4 API documentation](https://the-odds-api.com/liveapi/guides/v4/) lists sport key `americanfootball_ncaaf`, bookmaker key `fanduel`, featured markets `h2h`, `spreads` and `totals`, and historic odds snapshot endpoints. Its [historical data guide](https://the-odds-api.com/historical-odds-data/) says a requested historical date returns the closest snapshot **at or before** the specified time, with actual timestamp metadata, and requires a paid plan. Neither documentation nor an endpoint existing proves actual FanDuel coverage for a given NCAAF game or a specific date.

The source audit is still pending: obtain a small legitimately accessed provider sample, check the paid plan and license conditions, verify NCAAF game count and FanDuel availability across representative 2025/2026 slates and observe publisher timestamps. Do not commit proprietary market rows, API keys or provider responses to this public repository. Use a secret for `ODDS_API_KEY`, never enter it into a public issue or README.

## What comes next

**5B:** verify price stream coverage on an authenticated sample, create a permission-safe timestamped snapshot store, and design bounded manual/on-demand polling with credit accounting, source outages and data-retention rules.

**5C:** derive true market movement only from *observed* same-book snapshots, then implement cutoff-safe joins and closing-line comparisons. Do not identify the first scraped quote as a true opener.

**5D:** validated model probabilities and walk-forward ATS/O-U grading, vig-aware selection EV, correlated-leg analysis and parlay-price checks. No genuine model picks or betting-value claims until full testing passes.

See [FanDuel market plan](STEP5_FANDUEL_MARKET_PLAN.md) for the consumer-facing workflow. All current outputs remain `PASS_UNVALIDATED`.

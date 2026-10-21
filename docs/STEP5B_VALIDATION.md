# Step 5B validation checkpoint — 2026-10-21

**Result: synthetic validation passed; real FanDuel source acceptance remains blocked.**

## Verified CI evidence

[GitHub Actions CFB Data Intake validation run 39678475173](https://github.com/The-Caves/cfb-model/actions/runs/39678475173) completed with **178 unit tests, 0 failures**. The `ingest` job was intentionally skipped for this code-only commit, so this is *not* evidence of live sportsbook API ingestion.

The no-network full-path synthetic smoke is `python -m scripts.market_validation` and is covered in CI by `tests/test_market_validation.py`. It exercises a **fabricated** The Odds API v4-style FanDuel event, strict as-of ESPN crosswalk, and an ephemeral local private SQLite vault. Results:

| Synthetic validation check | Result |
| --- | --- |
| Matched synthetic provider events across three observations | 3 |
| Append-only snapshots stored | 3 |
| Two-sided moneyline/spread/total selection rows stored | 18 |
| Repeated snapshot deduplicated | Yes |
| Reversed home/away fixture rejected | Yes |
| Same-book first-observed-to-later spread movement | Correct (mock -4.5 to -5.5) |
| Backfilled later provider snapshot prevented from replacing live as-of quote | Yes |
| Post-kickoff quote suppressed | Yes |
| Actual provider API calls / charged credits | 0 / 0 |
| Market-model betting clearance | `PASS_UNVALIDATED` |

Only aggregate synthetic results are emitted. The test's local temporary database is discarded. No real, licensed sportsbook odds are included in the public repository.

## API credit estimate and hard preflight

`python -m scripts.market_preflight --bookmakers fanduel --requests 10` does **not** contact the provider. For one bookmaker and `h2h,spreads,totals`, the provider's current featured-market pricing implies up to 3 credits per live snapshot or 30 per historical snapshot; actual billing varies with market availability, and these estimates are not a billed receipt.

`scripts/market_capture.py` now refuses an explicit live network request if the conservative estimated cost exceeds `--max-estimated-credits`, default **3**. Historical queries already require `--acknowledge-paid-historical` and now also require consciously raising the ceiling, usually to **30** for a single full featured-market historical request. This is a **software request-cost cap**, not a provider-account spending limit or financial guarantee.

Offline fixture runs do not fetch odds or use credits. Provider API credentials must be supplied privately through `ODDS_API_KEY` when—and only when—the source is legitimately obtained and configured. No provider key is currently connected.

## Point-in-time correctness

- Quotes downloaded live and available by decision cutoff take precedence over an apparently newer *historical* quote retrieved after that cutoff.
- A historical-only reconstruction remains marked `HISTORICAL_RECONSTRUCTION_NOT_LIVE`; it must not be described as a quote we could actually have placed.
- The first recorded quote is only `FIRST_OBSERVED`, not necessarily a true sportsbook opener. A closing line similarly requires verified pre-kickoff observation coverage.
- Matchups without exact canonical aliases and kickoff-side consistency are quarantined, not guessed.
- All selection prices are research-only; the provider's quote may differ from a bettor's regional or account-specific FanDuel display.

## Remaining real-world validation gate

Before Step 5B can be called **live operational**, obtain an appropriately licensed small FanDuel NCAAF snapshot from a supported provider without posting keys or raw odds in this public repository; verify the provider response, FanDuel bookmaker presence, spreads/totals/moneylines, timestamps, event-to-ESPN coverage, quota headers and permitted retention. Compare at least one actual displayed FanDuel selection and price at a clearly recorded time when possible. Avoid claiming that the provider exposes a true opening line until historically verified.

The current SQLite vault is local and **not encrypted**. Reliable unattended collection additionally requires private persistent encrypted hosting, secure backups, access controls and retention terms outside public GitHub Actions.

Step 5C line movement and historical model evaluation may proceed in offline design, but no genuine sportsbook-backed model picks or value assertions may be issued. Status: `PASS_UNVALIDATED`.

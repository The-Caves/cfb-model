# Step 5B — Private sportsbook quote vault and opt-in capture

**Status as of 2026-10-21:** Local implementation and synthetic tests exist in the public code repository. **No FanDuel provider key is connected, no actual paid historical odds or current FanDuel quotes have been fetched, and no market poll is scheduled.** Model output remains `PASS_UNVALIDATED`.

## Public source code, private market data

- The repo is PUBLIC. Code, synthetic tests and aggregate quality reports may reside on `main`. Do **not** push paid odds, FanDuel account information, exported bookmaker prices or API keys into commits, public GitHub Actions artifacts or public branches (`context-state` is also public).
- `scripts/market_vault.py`: local SQLite market history stored **strictly outside the repository**, default `~/.local/share/cfb-model/market_quotes.sqlite3`, in a private 0700 directory with a 0600 file. Symlinks and public checkout paths are rejected. Quote/snapshot UPDATE and DELETE operations are blocked by SQLite triggers, and reimporting the same captured snapshot does not duplicate rows.
- Records retain provider source SHA-256, source observation time, retrieval time, bookmaker, event, market, selection, line, American price, published update time (if available), and credit usage headers. No quote is called the verified opener or closer. A quote fetched retrospectively from historical API remains identifiable as retrospective.
- **SQLite is not encrypted.** A 0600 mode protects only within the operating system's access-control model, not against a compromised login, lost unencrypted drive, backups or a malicious root user. Use an encrypted volume/private secrets manager for the actual persistent store, and apply retention/license terms.
- `.gitignore` ignores common market DB extensions, local quote folders and `.env` secrets as a second defense. Ignore rules alone cannot make a public artifact safe: do not commit/export odds with forced add or upload licensed market data in public Actions.

## Manual offline proof without API charges

Clone the repository to your own computer, create a private directory, and use a local data sample obtained under applicable licensing. This command uses a **local file only**; it makes **zero network requests**:

```sh
python -m scripts.market_capture \
  --offline-json /private/path/provider_sample.json \
  --vault /private/path/market_quotes.sqlite3
```

`/private/path` must be a directory with owner-only access (0700 on Unix), outside the repository. The sample should follow The Odds API v4 NCAAF payload format. It is not included in the public repo. The console prints safe counts, provider quota numbers when supplied, and whether the capture was inserted or duplicated; it does **not** print credentials or line prices. Tests use invented sample values, not actual FanDuel prices.

## Opt-in live quote collection — not enabled

An authorized local operator can set `ODDS_API_KEY` as an environment secret **in their own system** (never paste it into a public repo, issue, chat message, CI log or artifact), then explicitly request:

```sh
python -m scripts.market_capture --execute-network
```

Without `--execute-network`, the live fetch is refused. The script also refuses real provider collection while `GITHUB_ACTIONS=true`, to avoid mixing licensed data with this public repository's runner.

Paid historical API calls require a second acknowledgement and a precise UTC timestamp, e.g.:

```sh
python -m scripts.market_capture --execute-network \
  --historical-date 2026-10-10T19:00:00Z \
  --acknowledge-paid-historical
```

**This paid call consumes provider credits if run on a subscribed account.** Historical retrieval is not automated; there is no background schedule, no API key embedded in code, and no purchase or charge is being made by the repository. Before use, review the provider's [rate and quota documentation](https://the-odds-api.com/liveapi/guides/v4/) and [historical access requirements](https://the-odds-api.com/historical-odds-data/), as well as exact FanDuel/NCAAF coverage. Feature pricing and provider response shape may change.

## Query and safety semantics

`scripts/market_vault.py:asof_quotes(...)` can find the most recent observed bookmaker quote for a provider event/market/selection before a requested cutoff, but:

- It always returns `price_executable_verified=false`; a regional FanDuel betting slip may have a different quote.
- It returns `NO_OBSERVED_QUOTE` if nothing was observed before the cutoff, and `STALE_PRICE` when the observation age exceeds the configured maximum.
- It returns `GAME_ALREADY_STARTED` rather than displaying a pregame quote as actionable at or after kickoff.
- It distinguishes `HISTORICAL_RECONSTRUCTION_NOT_LIVE` for a historical provider observation retrieved **after** the simulated decision time.
- This vault stores provider events. The audited ESPN game crosswalk and betting evaluation must be applied before use by the prediction engine; an event ID alone is not an automatically validated match.

## Next release gates

1. Obtain a legally accessible and rate-limited **small real FanDuel NCAAF sample**; verify actual market coverage and the official timestamp envelope using `scripts/market_coverage_audit.py`. Do not extrapolate historical coverage from the provider's general documentation.
2. Choose private persistent hosting and encrypted storage for unattended capture (not public GitHub Actions). Verify snapshots survive machine/worker restarts, enforce provider licensing, secure logs, encryption/backups and retention.
3. Set a bounded polling cadence after access is explicitly enabled; record quota usage and handle provider outages, suspended markets and line changes. Historical point-in-time correctness requires both market and game-context timestamps.
4. Advance to Step 5C only once real quotes, safe retention and the verified ESPN crosswalk are working together. Then validate opening-vs-first-observed, movement, CLV and honest decision-time pricing. Bet recommendations remain disabled until walk-forward out-of-sample testing.

## Tests

`tests/test_market_vault.py`, `tests/test_market_capture.py`, and `tests/test_market_client.py` cover append-only snapshots, private permissions, duplicate captures, credit headers, market timing, later-retrospective history, no-network defaults, paid-historical acknowledgement and refusal to write normalized bookmaker prices inside the public repository.

Run:
```sh
python -m unittest discover -s tests -v
```

Only synthetic test data lives on GitHub. No private information or provider access has been introduced.

# Historical NCAAF props: source coverage and no-charge ingestion

As of October 30, 2026, the repository has real ESPN-derived 2026 player
statistics but **does not have a historical sportsbook player prop odds archive**.
1,126 matched team/drive budgets are NOT 1,126 historical book props.

The Odds API (the-odds-api.com) paid v4 `historical event odds` endpoint
offers historical player prop snapshots (additional markets after May 2023).
Actual game/market/book coverage must still be proven:
https://the-odds-api.com/historical-odds-data/

SportsDataIO lists archived college-football props but requires its historical
data entitlement:
https://sportsdata.io/developers/api-documentation/ncaa-football

These are different services from `theoddsapi.com`. No subscription or
API access is activated by this code.

`scripts/player_prop_historical_market.py` is an OFFLINE loader only. It
can ingest already-licensed The Odds API historical event response envelopes
(`timestamp`, `data`), requiring explicit reviewed ESPN fixture/event and
athlete-ID mappings dated before each quote snapshot. It saves the provider-
asserted historical snapshot time separately from the actual later retrieval
time; source hashes do NOT independently prove original publication timing.
It never promotes retroactive quotes into prospectively frozen forecasts.

Sample gap report (no API charges):

```sh
python -m scripts.player_prop_historical_market \
  --history data/player_props/espn_player_game_history.json \
  --asof 2026-10-30T22:00:00Z \
  --output data/player_props/historical_book_prop_coverage.json
```

Once historical event-response files are legitimately available, add
`--imports snapshots.json --fixtures fixtures.json --athletes identities.json`.
Never place licensed full provider payloads or API keys in a public repo.

The published historic provider data is not proven to cover every school,
player, matchup, market or bookmaker. The fraction of all offered props
remains null until an independent market-offer universe is documented.
A player missing from historical book markets is not an Under, DNP, zero,
or evidence no sportsbook had offered a prop. Historical imports may support
retrospective research, but cannot manufacture past source observations or
genuine prospective prediction receipts.

Live V03 remains unchanged and no betting-prop superiority is claimed.

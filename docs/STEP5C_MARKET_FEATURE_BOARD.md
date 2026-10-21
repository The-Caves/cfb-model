# Step 5C — Point-in-time FanDuel research market board

**Implementation checkpoint — October 21, 2026.** Code and synthetic GitHub CI tests only. No authenticated FanDuel market ingestion has been enabled, no actual FanDuel odds have been archived, and **no bet recommendations or validated market-based projections exist**. All outputs are `PASS_UNVALIDATED`.

## Purpose

`scripts/market_features.py:market_board` reads an existing **private** SQLite vault produced by `scripts/market_capture.py`. It prepares bookmaker-specific game-market features at a requested decision timestamp. It does **not** retrieve odds itself, authenticate live FanDuel prices, calculate matchup probabilities, or recommend wagers. It makes **no network requests**.

The result is keyed by vetted ESPN game ID plus provider event ID and bookmaker. Each eligible market (MONEYLINE, SPREAD, TOTAL) includes:

- The **first recorded eligible** and latest eligible source timestamps (not proof of an authentic sportsbook opening or closing line).
- Reference **home-side spread** or **over-side total** movement, in points, within one bookmaker and market only.
- Both distinct market sides, their American prices and line values, standard raw implied probabilities, two-way overround and normalized no-vig book probabilities. **No-vig market estimates are not model-predicted hit probabilities**.
- Capture time, optional publication-update age, freshness status, and explicit flags that the price has **not** been verified executable on an account-specific FanDuel slip.
- Missing/contradictory markets and rejected game IDs. A team is never assigned a sportsbook opponent through fuzzy or swapped-site guessing.

`all_three_markets_recent` requires all three complete markets and sufficiently recent source updates, but **is not a validation or betting-clearance signal**.

## Strict decision-time guards

The function fails closed if the chosen ESPN game-context snapshot was collected after the decision timestamp. It refuses any quote observed **or retrieved** after the cutoff, a quote before its available ESPN context, or a price for a game already started. This distinguishes live observations from historical provider data downloaded days afterward.

Moneyline and two-sided spreads/totals must be internally consistent and from the **same source snapshot**; it never assembles half a market from different collection times. Contradictory prices with an identical observation timestamp quarantine the affected market, while unaffected markets may remain research-visible with missing coverage called out. If separate provider events both match one ESPN game, the entire duplicate matchup is excluded. Missing source-published timestamps prevent a price being labeled recent even if it was captured recently.

Stale or partially available markets may appear for diagnostics but are explicitly labeled `STALE_OR_UNTIMED_PRICE` or missing. Never interpret a visible price as authorization to wager.

## Private-only usage

A downstream **private** research runner may call:

```python
from scripts.market_event_crosswalk import load_market_registry
from scripts.market_features import market_board

aliases, conflicts = load_market_registry(
    "data/archive/2026_team_aliases.csv",
    "data/archive/2026_market_provider_aliases.csv",
)
board = market_board(
    vault_path="/private/market_quotes.sqlite3",
    espn_context=historically_valid_espm_context,
    aliases=aliases,
    conflicts=conflicts,
    decision_utc="2026-10-21T19:00:00Z",
    bookmaker="fanduel",
)
# board may contain sensitive/licensed market prices.
# Do NOT save it to public GitHub, a public Actions artifact, or a log.
```

`historically_valid_espm_context` in this example is a caller-supplied dictionary (replace with a genuinely timestamped context snapshot); this example is illustrative and does not suggest a real provider connection.

A public GitHub CI test constructs an **ephemeral, synthetic** private vault and asserts correct point-in-time matching, vig math, movement, source-update staleness, conflicting market pairs, post-kickoff rejection, cross-book isolation and backfill handling. The test data are invented, not real sportsbook prices.

## Step 5 completion dependencies

- **Still blocked by provider access:** authenticated real FanDuel bookmaker-key NCAAF odds, validated historical availability, actual opening/closing quote provenance and secure long-term private encrypted storage.
- **Still blocked by model work:** game-level joining to 2026 opponent-adjusted and historical-as-of team features; calibrated SU/ATS/O-U probabilities and actual out-of-sample walk-forward evaluation.
- **Future parlay evaluator:** needs price-specific expected values, vig and correlation analysis, and verified FanDuel combined payout; multiplying individual-leg probabilities is not valid for correlated picks.

Until these are validated, the price board is an engineering research feature and the overarching model remains `PASS_UNVALIDATED`. See [Step 5B private storage](STEP5B_PRIVATE_MARKET_STORAGE.md) and [FanDuel plan](STEP5_FANDUEL_MARKET_PLAN.md).

# Step 5B — Limited public FanDuel odds smoke test (2026-10-21)

**Result: IDENTITY-ONLY PARTIAL PASS — 10/10 public-source matchups identified; 0 source-validated sportsbook API records. NOT a full real-data API acceptance test.**

This document contains only public fixture identities, timestamps, result counts, and source references, not bookmaker price histories, API keys, wagering credentials, or account data. The repository is public.

## Public observed source

- Third-party [AgentBets public FanDuel NCAAF odds page](https://agentbets.ai/odds/fanduel/ncaaf) (as displayed without trailing slash), showing a snapshot labeled **2026-10-21 20:00:00 UTC (4:00 p.m. EDT)**. The publisher states that its sportsbook prices originate from The Odds API, updated hourly. It is **not the raw provider v4 JSON endpoint, the FanDuel sportsbook itself, or an authenticated quote with a provider-event ID**. Its page may change and must not be mistaken for an immutable licensed history source.
- The source page listed **54 total NCAAF events** but showed a visible table of **40** games in its rendered output at the time examined. Do not assume that every event has all three market types, or infer missing games from the displayed table.
- Repository [saved upcoming-context review](https://github.com/The-Caves/cfb-model/blob/context-state/state/qb_review_latest.json), captured **2026-10-21 20:39:05.224953 UTC**, was used for a cross-check of public game metadata and ESPN IDs. That snapshot is **39 minutes 5 seconds later** than the odds-page timestamp and therefore **cannot be treated as pre-existing ESPN state at the 20:00 UTC betting decision**.

### Strict team identity and kickoff comparison (public fixture metadata only)

| Third-party public-source matchup (away @ home) | ESPN game ID | Identity + kickoff |
| --- | --- | --- |
| New Mexico State @ Sam Houston State | `401871070` | Match after curated alias |
| James Madison @ Appalachian State | `401869845` | Match after curated alias |
| Liberty @ Kennesaw State | `401871056` | Matched |
| East Carolina @ Memphis | `401862807` | Matched |
| Duke @ Virginia | `401858271` | Matched |
| UMass @ UConn | `401861965` | Match after curated alias |
| Army @ Tulsa | `401862808` | Matched |
| Air Force @ Wyoming | `401864525` | Matched |
| NC State @ Stanford | `401858272` | Matched |
| LSU @ Auburn | `401856728` | Matched |

**10 / 10 unique fixture identities and kickoff times identified.** Initially 7 / 10 matched and three explicit source-name variants were missing. Added only these observed, uniquely verified sportsbook aliases to `data/archive/2026_market_provider_aliases.csv`:

- `Sam Houston State Bearkats` -> `Sam Houston Bearkats`
- `Appalachian State Mountaineers` -> `App State Mountaineers`
- `UMass Minutemen` -> `Massachusetts Minutemen`

`scripts/market_event_crosswalk.py:load_market_registry` now merges those **specific** aliases with the original 2026 FBS aliases, refusing unknown canonical schools, ambiguous names and overrides of another registered team. The public-source name tests pass in GitHub Actions. Do not enable fuzzy matching.

## Why full Step 5B acceptance remains BLOCKED

1. **No authenticated odds payload or credentials.** The public webpage is a third-party representation. No raw The Odds API v4 event IDs, response JSON, source update metadata/HTTP headers, live FanDuel quotes or actual quota counters have been received by this project.
2. **No point-in-time ESPN evidence for 20:00 UTC.** The inspected context was collected at 20:39 UTC. A strictly historical-as-of join must reject use of this later snapshot for a 20:00 UTC quote. Ten recognized identities **are not ten accepted market features**.
3. **No provider-level line history or validated true opener.** A mutable website and isolated public snapshots cannot establish comprehensive opening, closing or intraday FanDuel markets. `FIRST_OBSERVED` remains distinct from a verified sportsbook open.
4. **No verified local price persistence of this real page.** The synthetic pipeline and SQLite vault have passed tests, but it would be misleading to fabricate missing provider IDs and pretend the webpage itself passed our native v4 parser or private-vault live capture test.
5. **No licensed, encrypted persistent host configured.** Public GitHub Actions artifacts are not the destination for proprietary sportsbook quote histories.

**Next full acceptance action:** use one locally authorized real The Odds API current NCAAF FanDuel response (and optionally a paid historical sample, after cost approval), store it only in the private vault, inspect an aggregate audit, and verify exact ESPN mappings with a snapshot timestamp no later than the quote. Record observed price timestamp, FanDuel bookmaker key, source event ID, available markets, response quarantine counts, quota usage and whether the source permits local history retention. Keep `PASS_UNVALIDATED`.

## Verification pointers

- [Crosswalk tests and current code](https://github.com/The-Caves/cfb-model/blob/main/tests/test_market_event_crosswalk.py)
- [2026 market-specific alias registry](https://github.com/The-Caves/cfb-model/blob/main/data/archive/2026_market_provider_aliases.csv)
- [Private collector runbook](STEP5B_PRIVATE_MARKET_STORAGE.md)
- [Synthetic 178-test checkpoint](STEP5B_VALIDATION.md)

**Public sources:** [third-party timestamped FanDuel page](https://agentbets.ai/odds/fanduel/ncaaf), [The Odds API v4 documentation](https://the-odds-api.com/liveapi/guides/v4/). This test is **not a guarantee** of FanDuel price accuracy or API data availability.

# Step 3: Advanced-statistics intake — v0.1

Provider: SportsDataverse 2026 ESPN-derived play-by-play release \`espn_cfb_pbp\`.
URL: https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/espn_cfb_pbp

Provider advanced drive release \`espn_cfb_adv_drives\` is downloaded and source-audited, but **drive stats are not merged yet** because we have not verified the independently-derived per-game team-id mapping. No points/drive, drive scoring attribution, or defensive scores are fabricated.

## What counts as real

- EPA is provider-supplied only; it's never estimated from score margin or total yards.
- For every accepted game, ESPN game IDs, both final scores, and two distinct home/away team IDs must match a previously completed game in the canonical ledger.
- Both offenses must have at least 20 classified scrimmage plays; suspect games are quarantined.
- EPA per play, success (provider flag only), passing/rushing splits, explosive plays (20+ pass / 12+ rush), observed hurry/sack rates, opponent EPA allowed are aggregated separately.
- Profiles are for the 138-school 2026 registry. FCS games can contribute to an FBS team's history.
- A game on or after the as-of day is excluded, and today's current Parquet snapshot may include retroactive corrections. **These releases are not historical pregame snapshots**.
- Repeated pipeline runs save retrieved timestamp and SHA256 for each source in \`advanced_manifest.json\`. No missing feature is substituted with zero.

Outputs: \`data/advanced/team_game_advanced_2026.csv\`, \`team_profiles_advanced_2026.csv\`, \`advanced_manifest.json\`. The release downloads are archived as a short-lived GitHub Actions artifact; neither 2026 data nor EPA metrics are pushed into Git history.

The ingestion is a **research feature builder**. It does not enable betting picks; all predictions remain \`PASS_UNVALIDATED\`.

Next: verify source drive IDs and map to the canonical game/team IDs before adding drive efficiency, analyze play coverage by school, add historical priors and temporally correct validation, then QB status/injuries/weather/market data.

## Unified team profiles

`scripts/combine_profiles.py` joins the existing as-of 2026 score profile with the new advanced profile under strict equal-team, equal-season and equal-asof rules. Outputs `data/enriched/team_profiles_2026_enriched.csv` and `enriched_manifest.json` (artifact only). Legacy unpopulated score EPA placeholders are omitted; provider EPA fields are explicitly labeled. The unified file is a **research feature store**, not a trained model, and publication-time accuracy is not yet certified.

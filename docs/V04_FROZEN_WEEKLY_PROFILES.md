# v0.4 Step 1 — Checksummed weekly profiles

The new scripts/weekly_profiles.py creates research-only files asof-YYYY-MM-DD.json for every Saturday anchor and each observed ESPN game date in 2026, across all 138 canonical FBS schools. It uses the same shared history updater as scripts/model_v03.py. Team records list earlier game IDs, recent EPA and opponent-adjusted form, missing-data indicators, and do not export game results as labels.

Each cutoff file has a deterministic SHA-256 and cannot be silently overwritten by a different reconstruction. The capture_manifest.json records original input hashes, source retrieval timestamp, capture limitations and individual snapshot checksums. Modifying October games does not change a September cutoff's profile. Modifying a source game used by that September snapshot changes the reconstructed contents and is detected as drift if replayed into the original capture directory.

Run with: python -m scripts.weekly_profiles --games data/games_2026.csv --advanced data/advanced/team_game_advanced_2026.csv --manifest data/advanced/advanced_manifest.json --registry data/archive/2026_team_aliases.csv --through-date 2026-10-21 --output data/weekly_profiles

The CFB Data Intake workflow performs this task after advanced ingestion. Its output is an artifact retained for 30 days; public repository commits contain only code and tests, not research source data. A durable, append-only external snapshot store is still a future requirement.

**Critical**: Retrospective snapshots built now are NOT authentic historical pregame captures. The original SportsDataverse release was retrieved after the games and may have been revised. Every profile is RETROSPECTIVE_RECONSTRUCTION_UNVERIFIED and PASS_UNVALIDATED. Injury/QB provenance, 2025 priors and bookmaker prices still require separate work.

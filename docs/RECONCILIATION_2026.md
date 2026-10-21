# Archived 2026 v0.9 vs live ESPN reconciliation

Audit conducted 2026-10-21 (UTC) using the first confirmed GitHub Actions ESPN scoreboard artifact, run 39534529114.

| Data | Games |
|---|---:|
| Archived v0.9 2026 ledger | 388 |
| Live ESPN completed games (includes games outside FBS registry) | 512 |
| Archived games exactly matched by date/home/away and both final scores | 311 |
| Archived games not matched | 77 |
| Matched games with different final scores | 0 |
| ESPN-only games not matched to archive | 201 |

The source archive's score rows were previously labeled `SCORE_ONLY_UNVERIFIED_ASOF` or `RETROSPECTIVE_OCT17_SCORE_AUDIT_NOT_ASOF_ARCHIVED`.
**Do not treat archived data as pregame-available or independently verified.** An exact matching result is not proof of historical availability, historical market odds, injury data, or team-statistical completeness.

## Safe data handling

- `data/archive/2026_v09_scores_unverified.csv` is a **quarantined reference input**. Never add its unmatched rows to the canonical training ledger without further verification.
- `data/archive/2026_team_aliases.csv` maps the 138 archived school names to ESPN display names explicitly; no silent fuzzy matching.
- `data/snapshots/espn_completed_2026_asof_2026-10-21.csv` is a frozen replay input for deterministic continuous integration, **not** a current/live dataset.
- Each scheduled ingestion builds the live completed-game CSV, score-based profiles, and a new reconciliation audit.
- Every push validates audit code against the frozen reference snapshot and publishes audit artifacts.
- Audit `REVIEW_REQUIRED` does not mean ESPN ingestion failed; it means historical archive remains quarantined.
- The audit report's `archive_training_cleared` remains false until historical availability/provenance and missing records are resolved.

## Source and provenance

Source v0.9 local research archive: `CFB_2026_v0_9_Data_Intake_GitHub_Ready.zip`, score ledger under `v09/output/`.
The archived ledger contains per-row source URLs and quality flags. It is copied as research data only.
ESPN snapshot was extracted from GitHub Actions run 39534529114, artifact 12317016866.
Scoreboard feed: `site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard`.

Run locally:
```sh
python scripts/reconcile_scores.py \
  --archive data/archive/2026_v09_scores_unverified.csv \
  --live data/snapshots/espn_completed_2026_asof_2026-10-21.csv \
  --aliases data/archive/2026_team_aliases.csv \
  --output data/reconciliation_snapshot
```

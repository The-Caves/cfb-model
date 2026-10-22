import csv
import tempfile
import unittest
from pathlib import Path
from scripts.injury_history import observe
from scripts.injury_review_export import export

NOW="2026-10-22T16:00:00Z"
CONTEXT={"asof_utc":"2026-10-22T14:00:00Z",
 "captured_at_utc":"2026-10-22T15:00:00Z","betting_status":"PASS_UNVALIDATED",
 "games":[{"game_id":"123","home":"Home","away":"Away",
 "kickoff_utc":"2026-10-24T20:00:00Z",
 "injury_coverage_by_team":{"Home":"VERIFIED_REPORT_REVIEWED"},
 "injury_reports":[{"team":"Home","player":"Player One","position":"QB",
 "signal_kind":"AVAILABILITY","status":"QUESTIONABLE",
 "published_at_utc":"2026-10-22T12:00:00Z",
 "captured_at_utc":"2026-10-22T13:00:00Z",
 "source_url":"https://school.edu/availability"}]}]}

class InjuryExportTests(unittest.TestCase):
    def test_unknown_opponent_and_qb_priority(self):
        snapshot=observe(CONTEXT,NOW)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"review.csv"
            result=export(snapshot,path)
            with path.open(newline="") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(result["unknown_team_slots"],1)
            self.assertEqual(len(rows),2)
            home=next(r for r in rows if r["team"]=="Home")
            away=next(r for r in rows if r["team"]=="Away")
            self.assertEqual(home["review_priority"],"REVIEW_QB")
            self.assertEqual(away["reported_status"],"UNKNOWN")
            self.assertEqual(away["review_priority"],"MISSING_VERIFIED_REPORT")

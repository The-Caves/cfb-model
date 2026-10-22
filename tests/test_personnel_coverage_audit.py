import copy
import unittest
from scripts.personnel_coverage_audit import audit

C = {"betting_status": "PASS_UNVALIDATED", "asof_utc": "2026-10-22T12:00:00Z",
     "captured_at_utc": "2026-10-22T12:01:00Z", "games": [
         {"game_id": "1", "home": "A", "away": "B",
          "kickoff_utc": "2026-10-24T12:00:00Z",
          "injury_coverage_by_team": {"A": "VERIFIED_REPORT_REVIEWED", "B": "UNKNOWN"},
          "verified_qb_starters": {"A": {"player": "Starter",
              "published_at_utc": "2026-10-22T10:00:00Z",
              "captured_at_utc": "2026-10-22T11:00:00Z",
              "reviewed_at_utc": "2026-10-22T11:30:00Z"}}}]}

class CoverageTests(unittest.TestCase):
    def test_missing_never_healthy(self):
        x = audit(C)
        self.assertEqual(x["summary"]["verified_report_slots"], 1)
        self.assertEqual(x["summary"]["reviewed_qb_slots"], 1)
        self.assertEqual(x["games"][0]["teams"][1]["qb_status"], "UNKNOWN")
        self.assertFalse(x["games"][0]["complete_reports"])
    def test_missing_sources(self):
        c = copy.deepcopy(C)
        c["games"][0].pop("injury_coverage_by_team")
        c["games"][0].pop("verified_qb_starters")
        self.assertEqual(audit(c)["summary"]["verified_report_slots"], 0)
    def test_future_qb_blocked(self):
        c = copy.deepcopy(C)
        c["games"][0]["verified_qb_starters"]["A"]["reviewed_at_utc"] = "2026-10-23T00:00:00Z"
        with self.assertRaises(ValueError):
            audit(c)
    def test_unverified_label_blocked(self):
        c = copy.deepcopy(C)
        c["games"][0]["injury_coverage_by_team"]["B"] = "HEALTHY"
        with self.assertRaises(ValueError):
            audit(c)
    def test_duplicate_blocked(self):
        c = copy.deepcopy(C)
        c["games"].append(copy.deepcopy(c["games"][0]))
        with self.assertRaises(ValueError):
            audit(c)

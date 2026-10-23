import copy
import unittest
from scripts.injury_source_readiness import audit

BASE = {
    "asof_utc": "2026-10-24T10:00:00Z",
    "captured_at_utc": "2026-10-24T10:01:00Z",
    "betting_status": "PASS_UNVALIDATED",
    "safe_for_betting": False,
    "games": [{"game_id": "100", "home": "Home", "away": "Away",
               "kickoff_utc": "2026-10-24T15:00:00Z",
               "injury_coverage_by_team": {"Home": "VERIFIED_REPORT_REVIEWED",
                                           "Away": "UNKNOWN"}}]
}

class InjurySourceReadinessTests(unittest.TestCase):
    def test_urgent_missing_not_healthy(self):
        result = audit(copy.deepcopy(BASE))
        self.assertEqual(result["summary"]["team_slots"], 2)
        self.assertEqual(result["summary"]["verified_report_slots"], 1)
        self.assertEqual(result["summary"]["urgent_missing_slots"], 1)
        self.assertFalse(result["replacement_values_validated"])
        self.assertFalse(result["safe_for_betting"])
        self.assertEqual(next(r for r in result["rows"] if r["team"] == "Away")["priority"], "URGENT")

    def test_early_and_game_day_triage(self):
        ctx = copy.deepcopy(BASE)
        ctx["games"][0]["kickoff_utc"] = "2026-10-26T15:00:00Z"
        self.assertEqual(audit(ctx)["rows"][0]["window"], "EARLY")
        ctx["games"][0]["kickoff_utc"] = "2026-10-25T04:00:00Z"
        self.assertEqual(audit(ctx)["rows"][0]["window"], "GAME_DAY_24H")

    def test_missing_coverage_not_healthy(self):
        ctx = copy.deepcopy(BASE)
        ctx["games"][0].pop("injury_coverage_by_team")
        result = audit(ctx)
        self.assertEqual(result["summary"]["missing_report_slots"], 2)

    def test_future_and_invalid_capture_fail_closed(self):
        ctx = copy.deepcopy(BASE)
        ctx["captured_at_utc"] = "2026-10-24T09:00:00Z"
        with self.assertRaises(ValueError):
            audit(ctx)
        ctx = copy.deepcopy(BASE)
        ctx["safe_for_betting"] = True
        with self.assertRaises(ValueError):
            audit(ctx)

    def test_duplicate_and_bad_status_fail_closed(self):
        ctx = copy.deepcopy(BASE)
        ctx["games"].append(copy.deepcopy(ctx["games"][0]))
        with self.assertRaises(ValueError):
            audit(ctx)
        ctx = copy.deepcopy(BASE)
        ctx["games"][0]["injury_coverage_by_team"]["Away"] = "HEALTHY"
        with self.assertRaises(ValueError):
            audit(ctx)

    def test_kicked_off_game_excluded(self):
        ctx = copy.deepcopy(BASE)
        ctx["games"][0]["kickoff_utc"] = "2026-10-24T09:00:00Z"
        result = audit(ctx)
        self.assertEqual(result["summary"]["team_slots"], 0)
        self.assertIsNone(result["summary"]["verified_fraction"])

if __name__ == "__main__":
    unittest.main()

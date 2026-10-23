import unittest
from unittest.mock import patch
from scripts.personnel_replacement_capture import build

class ReplacementCaptureTests(unittest.TestCase):
    def test_rejects_future_context(self):
        joined = {"captured_at_utc": "2026-10-23T12:00:00Z"}
        context = {"asof_utc": "2026-10-23T12:01:00Z",
                   "captured_at_utc": "2026-10-23T12:02:00Z"}
        with patch("scripts.personnel_replacement_capture.verify_joined", return_value=None):
            with self.assertRaises(ValueError):
                build(joined, context)

    def test_builds_missing_report_as_null_not_zero(self):
        joined = {"run_id": "1", "captured_at_utc": "2026-10-23T12:00:00Z",
                  "games": [{"game_id": "1", "home": "Home", "away": "Away",
                             "kickoff_utc": "2026-10-24T16:00:00Z"}]}
        context = {"asof_utc": "2026-10-23T11:59:00Z",
                   "captured_at_utc": "2026-10-23T12:00:00Z",
                   "betting_status": "PASS_UNVALIDATED", "games": [
                       {"game_id": "1", "home": "Home", "away": "Away",
                        "kickoff_utc": "2026-10-24T16:00:00Z",
                        "injury_coverage_by_team": {"Home": "UNKNOWN", "Away": "UNKNOWN"},
                        "injury_reports": []}]}
        with patch("scripts.personnel_replacement_capture.verify_joined", return_value=None):
            result = build(joined, context)
        self.assertEqual(result["summary"]["both_reports"], 0)
        self.assertIsNone(result["games"][0]["absence_differentials"])
        self.assertFalse(result["trained_replacement_points"])

if __name__ == "__main__":
    unittest.main()

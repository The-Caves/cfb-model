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
        self.assertEqual(result["summary"]["verified_team_slots"], 0)
        self.assertIsNone(result["games"][0]["absence_differentials"])
        self.assertEqual(result["games"][0]["home_report_by_position"]["coverage"], "UNKNOWN")
        self.assertIsNone(result["games"][0]["home_report_by_position"]["absences"])
        self.assertFalse(result["games"][0]["injury_adjustment_applied_to_live_model"])
        self.assertFalse(result["trained_replacement_points"])

    def test_keep_verified_side_when_opponent_report_missing(self):
        joined = {"run_id": "2", "captured_at_utc": "2026-10-23T12:00:00Z",
                  "games": [{"game_id": "2", "home": "Home", "away": "Away",
                             "kickoff_utc": "2026-10-24T16:00:00Z"}]}
        context = {"asof_utc": "2026-10-23T11:59:00Z",
                   "captured_at_utc": "2026-10-23T12:00:00Z",
                   "betting_status": "PASS_UNVALIDATED", "games": [{
                       "game_id": "2", "home": "Home", "away": "Away",
                       "kickoff_utc": "2026-10-24T16:00:00Z",
                       "injury_coverage_by_team": {
                           "Home": "VERIFIED_REPORT_REVIEWED", "Away": "UNKNOWN"},
                       "injury_reports": [{
                           "team": "Home", "player": "Example Lineman",
                           "position": "OL", "signal_kind": "AVAILABILITY",
                           "status": "OUT", "source_url": "https://example.edu/report",
                           "published_at_utc": "2026-10-23T11:00:00Z",
                           "captured_at_utc": "2026-10-23T11:30:00Z"
                       }, {
                           "team": "Home", "player": "Example Receiver",
                           "position": "WR", "signal_kind": "AVAILABILITY",
                           "status": "QUESTIONABLE", "source_url": "https://example.edu/report",
                           "published_at_utc": "2026-10-23T11:00:00Z",
                           "captured_at_utc": "2026-10-23T11:30:00Z"
                       }]}]}
        with patch("scripts.personnel_replacement_capture.verify_joined", return_value=None):
            result = build(joined, context)
        game = result["games"][0]
        self.assertEqual(game["coverage"], "INCOMPLETE")
        self.assertIsNone(game["absence_differentials"])
        self.assertIsNone(game["replacement_points"])
        self.assertEqual(game["home_report_by_position"]["absences"]["OL"], 1)
        self.assertEqual(game["home_report_by_position"]["uncertain"]["WR"], 1)
        self.assertIsNone(game["away_report_by_position"]["absences"])
        self.assertEqual(result["summary"]["verified_team_slots"], 1)
        self.assertEqual(result["summary"]["partially_covered_games"], 1)
        self.assertEqual(result["summary"]["observed_absences"], 1)
        self.assertEqual(result["summary"]["observed_uncertain"], 1)
        self.assertEqual(result["summary"]["live_injury_adjustments_applied"], 0)
        self.assertFalse(game["injury_adjustment_applied_to_live_model"])

if __name__ == "__main__":
    unittest.main()

import unittest
from scripts.reconcile_scores import audit, load_aliases


class ReconcileTests(unittest.TestCase):
    A = {"date": "2026-09-01", "away": "Team A", "home": "Team B", "away_score": "21", "home_score": "28"}
    B = {"date": "2026-09-01", "away": "Team A Wildcats", "home": "Team B Bears", "away_score": "21", "home_score": "28", "game_id": "123"}
    M = {"Team A": "Team A Wildcats", "Team B": "Team B Bears"}

    def test_exact_score_match(self):
        _, summary = audit([self.A], [self.B], self.M)
        self.assertEqual(summary["counts"]["SCORE_MATCH"], 1)
        self.assertFalse(summary["archive_training_cleared"])

    def test_score_disagreement_quarantined(self):
        row = {**self.B, "away_score": "22"}
        result, summary = audit([self.A], [row], self.M)
        self.assertEqual(result[0]["status"], "SCORE_MISMATCH")
        self.assertEqual(summary["status"], "REVIEW_REQUIRED")

    def test_unmatched_archived_date(self):
        result, summary = audit([self.A], [{**self.B, "date": "2026-09-02"}], self.M)
        self.assertEqual(summary["counts"]["ARCHIVE_UNMATCHED"], 1)
        self.assertEqual(summary["counts"]["LIVE_ONLY"], 1)

    def test_duplicate_archive_rejected(self):
        with self.assertRaises(ValueError):
            audit([self.A, self.A], [self.B], self.M)

    def test_duplicate_game_id_rejected(self):
        with self.assertRaises(ValueError):
            audit([self.A], [self.B, self.B], self.M)

    def test_missing_alias_rejected_for_match(self):
        result, _ = audit([self.A], [self.B], {"Team A": "Team A Wildcats"})
        self.assertEqual(result[0]["status"], "MISSING_TEAM_ALIAS")


if __name__ == "__main__":
    unittest.main()

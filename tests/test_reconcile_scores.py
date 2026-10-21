import unittest
from scripts.reconcile_scores import audit

class ReconcileTests(unittest.TestCase):
    A = {"date":"2026-09-01", "away":"Team A", "home":"Team B", "away_score":"21", "home_score":"28", "neutral":"False"}
    B = {"date":"2026-09-01", "away":"Team A Wildcats", "home":"Team B Bears", "away_score":"21", "home_score":"28", "neutral":"False", "game_id":"123"}
    M = {"Team A":"Team A Wildcats", "Team B":"Team B Bears"}

    def test_exact_match(self):
        _,s=audit([self.A],[self.B],self.M)
        self.assertEqual(s["counts"].get("SCORE_MATCH"),1)
        self.assertFalse(s["archive_training_cleared"])

    def test_score_disagreement(self):
        r,_=audit([self.A],[{**self.B,"away_score":"22"}],self.M)
        self.assertEqual(r[0]["status"],"SCORE_MISMATCH")

    def test_date_shift(self):
        r,s=audit([self.A],[{**self.B,"date":"2026-09-02"}],self.M)
        self.assertEqual(r[0]["status"],"DATE_SHIFT_MATCH")
        self.assertEqual(s["counts"].get("LIVE_ONLY",0),0)

    def test_neutral_disagreement(self):
        r,_=audit([self.A],[{**self.B,"neutral":"True"}],self.M)
        self.assertEqual(r[0]["status"],"NEUTRAL_SITE_MISMATCH")

    def test_home_away_conflict(self):
        b={**self.B,"away":self.B["home"],"home":self.B["away"]}
        r,_=audit([self.A],[b],self.M)
        self.assertEqual(r[0]["status"],"HOME_AWAY_SCORE_CONFLICT")

    def test_home_away_reversed_correct_scores(self):
        b={**self.B,"away":self.B["home"],"home":self.B["away"],"away_score":"28","home_score":"21"}
        r,_=audit([self.A],[b],self.M)
        self.assertEqual(r[0]["status"],"HOME_AWAY_REVERSED")

    def test_duplicate_archive(self):
        with self.assertRaises(ValueError):audit([self.A,self.A],[self.B],self.M)

    def test_duplicate_live_id(self):
        with self.assertRaises(ValueError):audit([self.A],[self.B,self.B],self.M)

    def test_missing_alias(self):
        r,_=audit([self.A],[self.B],{"Team A":"Team A Wildcats"})
        self.assertEqual(r[0]["status"],"MISSING_TEAM_ALIAS")
if __name__=="__main__":unittest.main()

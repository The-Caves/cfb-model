"""Frozen V03 home-margin audit and opponent rating fail-closed tests."""
import unittest
from scripts.site_home_bias_guard import apply,MODEL

def board(n=20):
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED",
      "model":"V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1",
      "forecast_observed_utc":"2026-10-31T15:19:57Z",
      "generated_at_utc":"2026-10-31T15:24:18Z",
      "games":[{"game_id":str(1000+i),"home_team":"Navy Midshipmen",
        "away_team":"Notre Dame Fighting Irish",
        "kickoff_utc":"2026-10-31T20:00:00Z",
        "model_home_margin":3.16947,"model_home_points":31.39755,
        "model_away_points":28.22808,"model_total":59.62563,
        "research_home_win_probability":.56114,
        "market_home_spread":31.5,"market_total":55.5,
        "model_ats_side":"HOME","ats_edge_points":34.66947,
        "model_ou_side":"OVER","ou_edge_points":4.12563} for i in range(n)]}

def completed():
    return [{"game_id":str(5000+i),"date":"2026-10-03",
       "kickoff_utc":"2026-10-03T19:00:00Z",
       "home":"Notre Dame Fighting Irish" if i%2==0 else "Navy Midshipmen",
       "away":"Navy Midshipmen" if i%2==0 else "Notre Dame Fighting Irish",
       "home_score":"30","away_score":"17","neutral":"False"} for i in range(120)]

def context(n=20):
    return {"captured_at_utc":"2026-10-31T15:18:30Z",
      "games":[{"game_id":str(1000+i),"home":"Navy Midshipmen",
        "away":"Notre Dame Fighting Irish",
        "kickoff_utc":"2026-10-31T20:00:00Z","neutral":False}
        for i in range(n)]}

def manifest():
    return {"status":"SUCCESS","failures":[],"requested_start":"2026-08-01",
      "scoreboard_date_timezone":"America/New_York",
      "retrieved_at_utc":"2026-10-31T15:14:50Z"}

class SiteHomeBiasTests(unittest.TestCase):
    def test_bias_quarantine_preserves_original_and_withholds_atsside(self):
        d=apply(board(),completed(),manifest(),context())
        audit=d["home_bias_audit"]
        self.assertEqual(audit["status"],"V03_HOME_BIAS_QUARANTINED")
        self.assertEqual(audit["training_raw_mean_home_margin"],13.)
        self.assertEqual(audit["quarantined_ats_lines"],20)
        self.assertEqual(audit["opponent_rating_games"],20)
        self.assertFalse(audit["automatic_model_promotion"])
        g=d["games"][0]
        self.assertEqual(g["model_home_margin"],3.16947)
        self.assertEqual(g["model_home_points"],31.39755)
        self.assertEqual(g["model_ou_side"],"OVER")
        self.assertEqual(g["model_ats_side"],"PASS")
        self.assertIsNone(g["ats_edge_points"])
        self.assertEqual(g["opponent_rating"]["model"],MODEL)
        self.assertEqual(g["opponent_rating"]["home_field_allowance"],2.5)
        self.assertTrue(g["opponent_rating"]["not_prospectively_calibrated"])
    def test_1_game_left_today_still_quarantines_from_training_evidence(self):
        d=apply(board(1),completed(),manifest(),context(1))
        self.assertEqual(d["home_bias_audit"]["status"],"V03_HOME_BIAS_QUARANTINED")
        self.assertEqual(d["games"][0]["model_ats_side"],"PASS")
    def test_missing_source_no_fake_challenger(self):
        d=apply(board())
        self.assertEqual(d["home_bias_audit"]["status"],"V03_HOME_BIAS_QUARANTINED")
        self.assertIsNone(d["games"][0]["opponent_rating"])
        self.assertFalse(d["home_bias_audit"]["source_same_forecast_training_run_verified"])
    def test_wrong_game_identity_fails_instead_of_guessing(self):
        ctx=context();ctx["games"][0]["away"]="Another Team"
        with self.assertRaisesRegex(ValueError,"differs"):
            apply(board(),completed(),manifest(),ctx)
    def test_same_day_game_scores_not_used(self):
        rows=completed();rows[-1]["date"]="2026-10-31"
        with self.assertRaisesRegex(ValueError,"strictly before"):
            apply(board(),rows,manifest(),context())
    def test_duplicate_source_games_fail(self):
        rows=completed();rows.append(rows[0].copy())
        with self.assertRaisesRegex(ValueError,"Duplicated"):
            apply(board(),rows,manifest(),context())
    def test_source_observed_after_frozen_forecast_fails(self):
        m=manifest();m["retrieved_at_utc"]="2026-10-31T15:23:00Z"
        with self.assertRaisesRegex(ValueError,"unverified"):
            apply(board(),completed(),m,context())

if __name__=="__main__":unittest.main()

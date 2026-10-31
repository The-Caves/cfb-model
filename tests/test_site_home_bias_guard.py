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
        self.assertEqual(audit["v04_direct_score_games"],20)
        self.assertFalse(audit["v04_score_uses_v03_total"])
        self.assertFalse(audit["automatic_model_promotion"])
        g=d["games"][0]
        self.assertEqual(g["model_home_margin"],3.16947)
        self.assertEqual(g["model_home_points"],31.39755)
        self.assertEqual(g["model_ou_side"],"OVER")
        self.assertEqual(g["model_ats_side"],"PASS")
        self.assertIsNone(g["ats_edge_points"])
        self.assertEqual(g["opponent_rating"]["model"],MODEL)
        v04=g["v04_direct_scores"]
        self.assertEqual(v04["status"],"SOURCE_OBSERVED_DIRECT_TEAM_SCORE_MODEL_RESEARCH_ONLY")
        self.assertAlmostEqual(v04["home_points"]+v04["away_points"],v04["total_points"],delta=.02)
        self.assertAlmostEqual(v04["home_points"]-v04["away_points"],v04["home_margin"],delta=.02)
        self.assertFalse(v04["direct_scoring_fit_uses_v03_total"])
        self.assertEqual(g["model_total"],59.62563)
        self.assertEqual(g["opponent_rating"]["home_field_allowance"],2.5)
        self.assertTrue(g["opponent_rating"]["not_prospectively_calibrated"])
    def test_score_illustration_uses_independent_r1_margin_and_unchanged_v03_total(self):
        d=apply(board(),completed(),manifest(),context())
        g=d["games"][0]
        out=g["opponent_rating"]
        self.assertEqual(out["score_scenario_status"],
            "HYBRID_R1_MARGIN_WITH_FROZEN_V03_TOTAL_UNVALIDATED")
        self.assertAlmostEqual(out["scenario_home_points"]+out["scenario_away_points"],
                               g["model_total"],delta=.02)
        self.assertAlmostEqual(out["scenario_home_points"]-out["scenario_away_points"],
                               out["predicted_home_margin"],delta=.02)
        self.assertEqual(out["scenario_total_source"],"FROZEN_UNVALIDATED_V03_TOTAL")
        self.assertFalse(out["score_scenario_is_jointly_trained_or_calibrated"])
        self.assertTrue(out["original_v03_scores_and_margin_unchanged"])
        self.assertEqual(g["model_home_points"],31.39755)
        self.assertEqual(g["model_away_points"],28.22808)

    def test_no_fake_score_when_r1_margin_would_make_negative_points(self):
        b=board()
        b["games"][0]["model_total"]=2.
        d=apply(b,completed(),manifest(),context())
        out=d["games"][0]["opponent_rating"]
        self.assertEqual(out["score_scenario_status"],"NO_VALID_SCORE_SPLIT")
        self.assertIsNone(out["scenario_home_points"])
        self.assertIsNone(out["scenario_away_points"])

    def test_1_game_left_today_still_quarantines_from_training_evidence(self):
        d=apply(board(1),completed(),manifest(),context(1))
        self.assertEqual(d["home_bias_audit"]["status"],"V03_HOME_BIAS_QUARANTINED")
        self.assertEqual(d["games"][0]["model_ats_side"],"PASS")
    def test_missing_source_no_fake_challenger(self):
        d=apply(board())
        self.assertEqual(d["home_bias_audit"]["status"],"V03_HOME_BIAS_SOURCE_MISSING_FAIL_CLOSED")
        self.assertIsNone(d["games"][0]["opponent_rating"])
        self.assertIsNone(d["games"][0]["v04_direct_scores"])
        self.assertFalse(d["home_bias_audit"]["source_same_forecast_training_run_verified"])
    def test_wrong_game_identity_fails_instead_of_guessing(self):
        ctx=context();ctx["games"][0]["away"]="Another Team"
        with self.assertRaisesRegex(ValueError,"differs"):
            apply(board(),completed(),manifest(),ctx)
    def test_same_day_final_is_embargoed_from_both_models(self):
        rows=completed()
        rows[-1]["date"]="2026-10-31"
        rows[-1]["kickoff_utc"]="2026-10-31T12:00:00Z"
        d=apply(board(),rows,manifest(),context())
        self.assertEqual(d["home_bias_audit"]["same_day_final_scores_embargoed"],1)
        self.assertEqual(d["home_bias_audit"]["training_game_count"],119)
        self.assertEqual(d["games"][0]["opponent_rating"]["source_training_games"],119)
        self.assertEqual(d["games"][0]["v04_direct_scores"]["source_training_games"],119)
        self.assertEqual(d["games"][0]["model_home_margin"],3.16947)
        self.assertEqual(d["games"][0]["model_ats_side"],"PASS")

    def test_same_day_purported_future_final_fails_closed(self):
        rows=completed()
        rows[-1]["date"]="2026-10-31"
        rows[-1]["kickoff_utc"]="2026-10-31T20:00:00Z"
        with self.assertRaisesRegex(ValueError,"after forecast cutoff"):
            apply(board(),rows,manifest(),context())

    def test_future_day_source_score_fails_closed(self):
        rows=completed()
        rows[-1]["date"]="2026-11-01"
        rows[-1]["kickoff_utc"]="2026-11-01T20:00:00Z"
        with self.assertRaisesRegex(ValueError,"after forecast cutoff"):
            apply(board(),rows,manifest(),context())

    def test_duplicate_embargoed_source_game_fails_closed(self):
        rows=completed()
        rows[-1]["date"]="2026-10-31"
        rows[-1]["kickoff_utc"]="2026-10-31T12:00:00Z"
        rows.append(rows[-1].copy())
        with self.assertRaisesRegex(ValueError,"Duplicated"):
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

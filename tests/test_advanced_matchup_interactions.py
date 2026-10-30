import unittest
from scripts.advanced_matchup_interactions import build,interactions

class AdvancedInteractionTests(unittest.TestCase):
    def test_pressure_times_pass_usage_is_asymmetric(self):
        h={"pass_rate":.8,"pressure_allowed":.4,"pressure_generated":.2,
           "run_off":.3,"run_def_allowed":.1,"pass_explosive_off":.2,"pass_def_allowed":.4}
        a={"pass_rate":.5,"pressure_allowed":.3,"pressure_generated":.6,
           "run_off":.1,"run_def_allowed":-.1,"pass_explosive_off":.1,"pass_def_allowed":.3}
        x=interactions(h,a)
        self.assertAlmostEqual(x["home_pressure_times_pass_reliance"],.192)
        self.assertAlmostEqual(x["away_pressure_times_pass_reliance"],.03)
        self.assertAlmostEqual(x["pressure_reliance_gap"],.162)
        self.assertAlmostEqual(x["home_run_off_vs_away_run_def"],-.03)

    def test_missingness_is_never_healthy_or_zero(self):
        x=interactions({"pass_rate":.5},{})
        self.assertTrue(all(v is None for v in x.values()))

    def test_board_cannot_promote_predictions(self):
        profile={"pass_rate":.5,"pressure_allowed":.1,"pressure_generated":.2,
            "run_off":.1,"run_def_allowed":.1,"pass_explosive_off":.1,"pass_def_allowed":.1}
        board={"status":"TEAM_OPPONENT_MATCHUP_STYLE_RESEARCH_ONLY",
            "betting_status":"PASS_UNVALIDATED",
            "model_promoted":False,"historical_publication_authenticated":False,
            "profiles":{"A":profile,"B":profile},
            "games":[{"game_id":"2","home":"A","away":"B","kickoff_utc":"2026-11-01T10:00:00Z"}]}
        result=build(board)
        self.assertIsNone(result["games"][0]["model_forecast_margin_adjustment"])
        self.assertFalse(result["model_promoted"])
        board["betting_status"]="CLEARED"
        with self.assertRaises(ValueError):build(board)

if __name__=="__main__":
    unittest.main()

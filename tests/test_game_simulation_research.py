import copy
import unittest
from scripts.game_simulation_research import simulate

DECISION="2026-10-30T18:00:00Z"

def fit():
    outcomes={"zone":[{"points":0,"explosive":False,"weight":1.0}]}
    return {
        "status":"FROZEN_PREDECISION_DRIVE_DISTRIBUTIONS_RESEARCH_ONLY",
        "game_id":"99","home":"A","away":"B",
        "trained_through_utc":"2026-10-25T12:00:00Z",
        "source_captured_at_utc":"2026-10-30T17:00:00Z",
        "kickoff_utc":"2026-10-31T16:00:00Z",
        "distributions":{
            "possessions":[{"count":10,"weight":1}],
            "field_position":[{"zone":"zone","weight":1}],
            "outcomes":{"home":copy.deepcopy(outcomes),"away":copy.deepcopy(outcomes)}
        },
        "safe_for_betting":False,"model_promoted":False,
        "betting_status":"PASS_UNVALIDATED"
    }

class DriveSimTests(unittest.TestCase):
    def test_zero_score_and_regulation_tie(self):
        result=simulate(fit(), DECISION, trials=200, seed=1)
        self.assertEqual(result["home_points_mean"],0)
        self.assertEqual(result["regulation_tie_probability"],1)
        self.assertIsNone(result["home_cover_probability"])
        self.assertIsNone(result["over_probability"])

    def test_away_and_home_scoring_reconcile(self):
        obj=fit()
        obj["distributions"]["outcomes"]["home"]["zone"]=[{"points":7,"explosive":True,"weight":1}]
        x=simulate(obj,DECISION,trials=100)
        self.assertEqual(x["home_margin_mean"],70)
        self.assertEqual(x["total_mean"],70)
        self.assertEqual(x["explosive_drives_mean"],10)
        self.assertEqual(x["home_win_regulation_probability"],1)

    def test_team_specific_empirical_field_position_coverage_required(self):
        obj=fit()
        obj["distributions"]["field_position_by_side"]={
            "home":[{"zone":"zone","weight":1}],
            "away":[{"zone":"zone","weight":1}]}
        self.assertEqual(simulate(obj,DECISION,trials=100)["total_mean"],0)
        obj["distributions"]["field_position_by_side"]["away"]=[]
        with self.assertRaises(ValueError):
            simulate(obj,DECISION,trials=100)

    def test_real_observed_market_only(self):
        market={"status":"OBSERVED_PREDECISION_MARKET","source_url":"https://example.edu/lines",
                "observed_at_utc":DECISION,"home_spread":-2.5,"total":3.5}
        obj=fit()
        x=simulate(obj, DECISION,market,trials=100)
        self.assertEqual(x["under_probability"],1)
        self.assertEqual(x["home_cover_probability"],0)
        future=dict(market,observed_at_utc="2026-11-01T10:00:00Z")
        with self.assertRaises(ValueError):simulate(obj,DECISION,future,trials=100)

    def test_future_training_and_invalid_drive_distribution_rejected(self):
        obj=fit()
        obj["trained_through_utc"]="2026-11-01T00:00:00Z"
        with self.assertRaises(ValueError):simulate(obj,DECISION,trials=100)
        obj=fit()
        obj["distributions"]["outcomes"]["away"]["zone"][0]["weight"]=-1
        with self.assertRaises(ValueError):simulate(obj,DECISION,trials=100)

if __name__=="__main__":
    unittest.main()

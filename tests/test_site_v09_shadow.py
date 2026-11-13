import copy,unittest
from scripts.site_v09_shadow import attach,STATUS
NOW="2026-11-13T14:00:00Z"
def earlier(i,date):
    return {"game_id":str(i),"home":"Home","away":"Away",
      "kickoff_utc":date+"T18:00:00Z","forecast_utc":date+"T14:00:00Z",
      "home_points":28.,"away_points":20.,"final_home":25,"final_away":17,
      "result_known_utc":date+"T23:00:00Z"}
def board():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED",
      "forecast_observed_utc":"2026-11-13T12:00:00Z",
      "prospective_records":{"wins":12},
      "games":[{
          "game_id":"999","home_team":"Home","away_team":"Away",
          "kickoff_utc":"2026-11-14T23:00:00Z",
          "home_bias_quarantined":True,
          "v04_direct_scores":{
            "status":"SOURCE_OBSERVED_DIRECT_TEAM_SCORE_MODEL_RESEARCH_ONLY",
            "model":"V04_INDEPENDENT_OPPONENT_ADJUSTED_SCORES_RESEARCH_ONLY",
            "home_points":31.,"away_points":20.,
            "home_margin":11.,"total_points":51.,
            "model_promoted":False,
            "no_market_lines_in_training":True,
            "direct_scoring_fit_uses_v03_total":False},
          "model_home_margin":100.,"model_total":101.,
          "model_ats_side":"PASS","model_ou_side":"PASS",
          "market_home_spread":-10.5,"market_total":48.5,
          "market_provider":"DraftKings","market_observed_utc":"2026-11-13T13:00:00Z",
      }]}
class ShadowTests(unittest.TestCase):
    def test_pre_match_simulation_frozen_and_explicitly_uncalibrated(self):
        history=[earlier(i,"2026-11-07" if i%2 else "2026-10-31") for i in range(32)]
        b=board();before=copy.deepcopy(b)
        out=attach(b,history,NOW,min_train=24,trials=150)
        v=out["games"][0]["v09_score_shadows"]
        self.assertEqual(out["v09_shadow_display"]["ready"],1)
        self.assertEqual(v["status"],STATUS)
        self.assertEqual(v["earlier_settled_v04_games"],32)
        self.assertFalse(v["model_promoted"])
        self.assertFalse(v["calibrated_betting_probability"])
        self.assertEqual(out["games"][0]["v04_direct_scores"],
                         before["games"][0]["v04_direct_scores"])
        self.assertEqual(out["prospective_records"],before["prospective_records"])
        self.assertIsNotNone(v["projections"]["team_form"]["over_probability"])
    def test_no_fictional_probabilities_for_no_source(self):
        out=attach(board(),[],NOW,min_train=24,trials=150)
        self.assertIsNone(out["games"][0]["v09_score_shadows"])
        self.assertEqual(out["v09_shadow_display"]["insufficient_history"],1)
    def test_future_outcome_not_used(self):
        h=[earlier(i,"2026-10-31" if i%2 else "2026-11-07") for i in range(32)]
        h[0]["result_known_utc"]="2026-11-15T12:00:00Z"
        out=attach(board(),h,NOW,min_train=24,trials=150)
        self.assertEqual(out["games"][0]["v09_score_shadows"]["earlier_settled_v04_games"],31)
    def test_current_board_not_retrained_after_start(self):
        b=board();b["games"][0]["kickoff_utc"]="2026-11-13T09:00:00Z"
        out=attach(b,[],NOW,min_train=24,trials=150)
        self.assertEqual(out["v09_shadow_display"]["kicked_off"],1)
        self.assertIsNone(out["games"][0]["v09_score_shadows"])
if __name__=="__main__":unittest.main()

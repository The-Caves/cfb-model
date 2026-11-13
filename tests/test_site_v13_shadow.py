"""Source-gated V13 site overlay tests; V04 originals must remain unchanged."""
import copy
import unittest
from scripts.site_v13_shadow import attach,STATUS
from scripts.v13_v04_probabilities import STATUS as PRED_STATUS

NOW="2026-11-13T17:00:00Z"


def record(i,day):
    return {"game_id":str(i),"home":"H","away":"A",
        "forecast_utc":day+"T13:00:00Z",
        "capture_utc":day+"T14:00:00Z",
        "kickoff_utc":day+"T18:00:00Z",
        "result_known_utc":day+"T23:00:00Z",
        "home_points":27.,"away_points":24.,
        "final_home":31,"final_away":24,
        "snapshot_sha256":"a"*64}


def board():
    return {
        "schema_version":2,"betting_status":"PASS_UNVALIDATED",
        "forecast_observed_utc":"2026-11-13T15:00:00Z",
        "forecast_run_id":"90001","prospective_records":{"wins":2},
        "games":[{"game_id":"1001","home_team":"Home","away_team":"Away",
            "kickoff_utc":"2026-11-14T18:00:00Z",
            "home_bias_quarantined":True,
            "v04_direct_scores":{
                "status":"SOURCE_OBSERVED_DIRECT_TEAM_SCORE_MODEL_RESEARCH_ONLY",
                "model":"V04_INDEPENDENT_OPPONENT_ADJUSTED_SCORES_RESEARCH_ONLY",
                "home_points":30.,"away_points":21.,
                "home_margin":9.,"total_points":51.,
                "model_promoted":False,"no_market_lines_in_training":True,
                "direct_scoring_fit_uses_v03_total":False},
            "model_home_margin":-100.,"model_total":13.,
            "model_ats_side":"PASS","model_ou_side":"PASS",
            "market_provider":"DraftKings","market_observed_utc":"2026-11-13T16:00:00Z",
            "market_home_spread":-7.5,"market_total":53.,
            "v04_market_research":None}]}


class V13SiteAcceptance(unittest.TestCase):
    def _history(self):
        return [record(i,"2026-10-31" if i%2 else "2026-11-07")
                for i in range(40)]

    def test_v13_shadow_published_as_probabilities_not_score_replacement(self):
        original=board();copy_orig=copy.deepcopy(original)
        out=attach(original,self._history(),NOW,min_train=35)
        assert out["v13_probability_display"]["ready"]==1
        p=out["games"][0]["v13_probability_shadow"]
        self.assertEqual(p["status"],PRED_STATUS)
        self.assertEqual(p["site_status"],STATUS)
        self.assertEqual(p["margin_mean"],9.)
        self.assertEqual(p["total_mean"],51.)
        self.assertTrue(p["v04_mean_scores_unchanged"])
        self.assertTrue(p["research_probability_not_certified_betting_edge"])
        self.assertFalse(p["model_promoted"])
        self.assertIsNotNone(p["home_cover_probability"])
        self.assertIsNotNone(p["over_probability"])
        self.assertEqual(out["games"][0]["v04_direct_scores"],
                         copy_orig["games"][0]["v04_direct_scores"])
        self.assertEqual(out["games"][0]["model_home_margin"],
                         copy_orig["games"][0]["model_home_margin"])
        self.assertEqual(out["games"][0]["model_ats_side"],
                         copy_orig["games"][0]["model_ats_side"])
        self.assertEqual(out["prospective_records"],
                         copy_orig["prospective_records"])

    def test_earlier_result_finalized_after_frozen_forecast_not_used(self):
        hist=self._history()
        hist[0]["result_known_utc"]="2026-11-13T16:00:00Z"
        out=attach(board(),hist,NOW,min_train=35)
        self.assertEqual(out["v13_probability_display"]["source_frozen_earlier_settled_games"],39)
        self.assertEqual(out["v13_probability_display"]["ready"],1)
        late=copy.deepcopy(hist)
        for row in late:
            row["result_known_utc"]="2026-11-14T12:00:00Z"
        out=attach(board(),late,NOW,min_train=35)
        self.assertEqual(out["v13_probability_display"]["ready"],0)
        self.assertEqual(out["v13_probability_display"]["not_enough_prior_games"],1)

    def test_same_day_and_unverified_source_not_a_history(self):
        hist=self._history();hist[0]["kickoff_utc"]="2026-11-13T09:00:00Z"
        result=attach(board(),hist,NOW,min_train=35)
        self.assertEqual(result["v13_probability_display"]["ready"],1)
        for r in hist:r["snapshot_sha256"]=None
        result=attach(board(),hist,NOW,min_train=35)
        self.assertEqual(result["v13_probability_display"]["source_frozen_earlier_settled_games"],0)

    def test_no_pregame_projection_after_kickoff(self):
        b=board();b["games"][0]["kickoff_utc"]="2026-11-13T14:00:00Z"
        result=attach(b,self._history(),NOW)
        self.assertEqual(result["v13_probability_display"]["kicked_off"],1)
        self.assertIsNone(result["games"][0]["v13_probability_shadow"])

    def test_quote_appearing_future_is_withheld(self):
        b=board();b["games"][0]["market_observed_utc"]="2026-11-14T13:00:00Z"
        result=attach(b,self._history(),NOW)
        pred=result["games"][0]["v13_probability_shadow"]
        self.assertIsNone(pred["home_cover_probability"])
        self.assertIsNone(pred["over_probability"])
        self.assertFalse(pred["market_quote_eligible"])

if __name__=="__main__":
    unittest.main()

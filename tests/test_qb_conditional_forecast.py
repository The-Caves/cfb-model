"""Player production, NOT depth rank, determines direction of QB adjustment."""
import unittest,datetime as dt
import numpy as np
from scripts.qb_conditional_forecast import _condition,scenario,MAX_SINGLE_QB_MARGIN_CHANGE

def passer(name,epa,plays=100):
    return {"game_id":"past","date":"2026-10-20","team":"A",
      "opponent":"C","player":name,"pass_tagged_plays":str(plays),
      "pass_epa_sum":str(epa*plays),"pass_epa_plays":str(plays),
      "source_retrieved_at_utc":"2026-10-21T12:00:00Z",
      "historical_source_time_verified":"False","betting_status":"PASS_UNVALIDATED"}
class ConditionalQBTests(unittest.TestCase):
    def test_more_efficient_qb2_can_improve_margin(self):
        rows=[passer("QB One",-0.3),passer("QB Two",0.4)]
        a=_condition(rows,"A","QB Two","2026-10-31",
                      dt.datetime.fromisoformat("2026-10-29T12:00:00+00:00"),0.,8.)
        b=_condition(rows,"A","QB One","2026-10-31",
                      dt.datetime.fromisoformat("2026-10-29T12:00:00+00:00"),0.,8.)
        self.assertGreater(a["margin_impact"],0)
        self.assertLess(b["margin_impact"],0)
        self.assertTrue(a["no_depth_chart_rank_penalty"])
    def test_absent_historical_qb_has_no_forced_penalty(self):
        x=_condition([],"A","New Starter","2026-10-31",
                     dt.datetime.fromisoformat("2026-10-29T12:00:00+00:00"),0.,7.)
        self.assertEqual(x["margin_impact"],0)
        self.assertIn("PASS",x["status"])
    def test_missing_team_epa_unknown_not_zero(self):
        x=_condition([passer("Player One",0.2)],"A","Player One","2026-10-31",
                     dt.datetime.fromisoformat("2026-10-29T12:00:00+00:00"),None,7.)
        self.assertEqual(x["margin_impact"],0)
        self.assertIn("PASS",x["status"])
    def test_shrink_and_cap_large_performance_effect(self):
        a=_condition([passer("Player One",3.5)],"A","Player One","2026-10-31",
                     dt.datetime.fromisoformat("2026-10-29T12:00:00+00:00"),-1,100.)
        self.assertLessEqual(a["margin_impact"],MAX_SINGLE_QB_MARGIN_CHANGE)
    def test_future_source_excluded_from_prior_and_no_downgrade(self):
        late=passer("Player One",0.4);late["source_retrieved_at_utc"]="2026-11-03T12:00:00Z"
        x=_condition([late],"A","Player One","2026-10-31",
                     dt.datetime.fromisoformat("2026-10-29T12:00:00+00:00"),0.,7.)
        self.assertEqual(x["margin_impact"],0)
    def test_usage_mixture_can_disagree_with_projected_qb_scenario(self):
        from scripts.personnel_features import BASE_FIELDS
        forecasts={"home":"A","away":"B","kickoff_utc":"2026-10-31T20:00:00Z",
            "projection":{"predicted_home_margin":3.,"predicted_total_points":48.}}
        profiles={"team_profiles":{"home":{"recent_form":{"epa_pass":0.}},
                                  "away":{"recent_form":{"epa_pass":0.}}}}
        sources={"home":{"starter":"A Two","starter_status":"PROJECTED_DEPTH_CHART_ONLY",
            "confidence":"LOW_UNCONFIRMED","depth_rank":2,
            "is_confirmed_starter":False,"availability_by_player":{},
            "betting_status":"PASS_UNVALIDATED",
            "scenarios":[{"player":"A One","depth_rank":1},{"player":"A Two","depth_rank":2}]},
            "away":{"starter":None,"starter_status":"UNKNOWN",
            "confidence":"UNKNOWN","depth_rank":None,
            "is_confirmed_starter":False,"availability_by_player":{},
            "betting_status":"PASS_UNVALIDATED","scenarios":[]}}
        def record(gid,name,plays,epa):
            return {"game_id":gid,"date":"2026-10-20" if gid=="past1" else "2026-10-27",
              "team":"A","opponent":"C","player":name,"pass_tagged_plays":str(plays),
              "team_pass_tagged_plays":"40","pass_epa_plays":str(plays),
              "pass_epa_sum":str(plays*epa),"source_retrieved_at_utc":"2026-10-28T12:00:00Z",
              "historical_source_time_verified":"False","betting_status":"PASS_UNVALIDATED"}
        rows=[record(gid,"A One",30,.4) for gid in ("past1","past2")]+[
              record(gid,"A Two",10,-.3) for gid in ("past1","past2")]
        n=len(BASE_FIELDS)
        coefs=np.zeros((n+1,1));coefs[BASE_FIELDS.index("pass_epa_form")+1,0]=8.
        params=(coefs,np.zeros(n),np.ones(n),None)
        decision=dt.datetime.fromisoformat("2026-10-29T18:00:00+00:00")
        result=scenario(forecasts,profiles,sources,rows,params,decision)
        self.assertEqual(result["status"],"QB_PLAYER_CONDITIONAL_SHADOW")
        self.assertEqual(result["usage_weighted_status"],"QB_EMPIRICAL_EXPOSURE_SHADOW")
        self.assertLess(result["adjusted_home_margin"],result["baseline_margin"])
        self.assertGreater(result["usage_weighted_home_margin"],result["baseline_margin"])
        self.assertAlmostEqual(result["empirical_pass_exposure_by_side"]["home"]["weights"]["A One"],.75)
        self.assertEqual(result["empirical_pass_exposure_by_side"]["away"]["unknown_weight"],1.)
        self.assertTrue(result["exposure_not_calibrated_next_game_starter_probabilities"])
    def test_missing_qb_usage_does_not_invent_shadow_effect(self):
        from scripts.personnel_features import BASE_FIELDS
        forecasts={"home":"A","away":"B","kickoff_utc":"2026-10-31T20:00:00Z",
          "projection":{"predicted_home_margin":3.,"predicted_total_points":48.}}
        profiles={"team_profiles":{"home":{"recent_form":{"epa_pass":None}},
                                  "away":{"recent_form":{"epa_pass":None}}}}
        slot=lambda:{"starter":None,"starter_status":"UNKNOWN","confidence":"UNKNOWN",
          "depth_rank":None,"is_confirmed_starter":False,
          "availability_by_player":{},"betting_status":"PASS_UNVALIDATED","scenarios":[]}
        n=len(BASE_FIELDS)
        params=(np.zeros((n+1,1)),np.zeros(n),np.ones(n),None)
        r=scenario(forecasts,profiles,{"home":slot(),"away":slot()},[],params,
                   dt.datetime.fromisoformat("2026-10-29T18:00:00+00:00"))
        self.assertEqual(r["usage_weighted_home_margin"],3.)
        self.assertEqual(r["usage_weighted_status"],"PASS_NO_RELIABLE_QB_EXPOSURE_AND_PASS_EPA")

if __name__=="__main__":unittest.main()

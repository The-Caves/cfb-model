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
if __name__=="__main__":unittest.main()

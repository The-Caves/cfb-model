"""V14 newly scored research is archived only as first authentic pregame receipt."""
import copy
import datetime as dt
import unittest

from scripts.site_decision_archive import freeze
from scripts.site_v14_shadow import attach
from tests.test_site_decision_archive import board as canonical_board
from tests.test_site_v14_shadow import contexts,NOW


def board():
    b=canonical_board()
    g=b["games"][0]
    b["forecast_observed_utc"]="2026-11-13T15:00:00Z"
    g["kickoff_utc"]="2026-11-14T18:00:00Z"
    g["market_observed_utc"]="2026-11-13T16:00:00Z"
    g["home_bias_quarantined"]=True
    g["model_ats_side"]="PASS"
    g["model_ou_side"]="OVER"
    g["v04_direct_scores"]={
        "status":"SOURCE_OBSERVED_DIRECT_TEAM_SCORE_MODEL_RESEARCH_ONLY",
        "model":"V04_INDEPENDENT_OPPONENT_ADJUSTED_SCORES_RESEARCH_ONLY",
        "home_points":30.,"away_points":20.,
        "home_margin":10.,"total_points":50.,
        "direct_scoring_fit_uses_v03_total":False,
        "no_market_lines_in_training":True,"model_promoted":False}
    score,market,dated=contexts()
    return attach(b,score,market,dated,NOW)


class V14ArchiveTests(unittest.TestCase):
    def test_archive_separate_score_receipt(self):
        b=board()
        result=freeze(b,dt.datetime.fromisoformat(NOW.replace("Z","+00:00")),"888")
        row=result["rows"][0]
        s=row["v14_frozen_matchup_shadow"]
        self.assertEqual(s["site_status"],"V14_SOURCE_TIMED_OPPONENT_MATCHUP_SCORE_SHADOW")
        self.assertEqual(s["variant"],"joint_close")
        self.assertFalse(s["model_promoted"])
        self.assertFalse(s["safe_for_betting"])
        self.assertEqual(row["v04_direct_home_margin"],10.)
        self.assertEqual(row["frozen_forecast_home_margin"],10.)
        self.assertEqual(row["displayed_ats_side"],"PASS")

    def test_forged_new_model_or_source_receipt_cannot_freeze(self):
        b=board()
        for k,value in (("margin",100.),("total",5.),("home_points",500.),
                        ("v04_margin",18.),("model_promoted",True),
                        ("source_observed_utc","2026-11-15T12:00:00Z"),
                        ("margin_adjustment",20.)):
            tamper=copy.deepcopy(b)
            tamper["games"][0]["v14_matchup_shadow"][k]=value
            with self.subTest(field=k),self.assertRaises(ValueError):
                freeze(tamper,dt.datetime.fromisoformat(
                    NOW.replace("Z","+00:00")),"888")

if __name__=="__main__":
    unittest.main()

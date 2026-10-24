import datetime as dt
import copy
import unittest
from scripts.site_decision_archive import freeze
NOW=dt.datetime(2026,10,24,15,45,tzinfo=dt.timezone.utc)
def board():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED",
      "forecast_sha256":"a"*64,"forecast_run_id":"555",
      "forecast_observed_utc":"2026-10-24T14:05:00Z",
      "games":[{"game_id":"3","home_team":"Home","away_team":"Away",
        "kickoff_utc":"2026-10-24T17:00:00Z",
        "model_home_margin":10.0,"model_total":55.0,
        "market_home_spread":-7.5,"market_total":49.0,
        "model_ats_side":"HOME","model_ou_side":"OVER",
        "market_provider":"DraftKings","market_observed_utc":"2026-10-24T15:00:00Z",
        "qb_starters_verified":0}]}
class ProspectiveDashboardArchiveTests(unittest.TestCase):
    def test_preserves_separate_pregame_model_market_clocks(self):
        snap=freeze(board(),NOW,"888")
        row=snap["rows"][0]
        self.assertEqual(row["market_home_spread"],-7.5)
        self.assertEqual(row["frozen_forecast_home_margin"],10)
        self.assertEqual(row["displayed_ats_side"],"HOME")
        self.assertEqual(row["displayed_ou_side"],"OVER")
        self.assertEqual(snap["summary"]["ats_decisions"],1)
        self.assertEqual(snap["rows"][0]["model_market_margin_disagreement"],2.5)
        self.assertEqual(snap["summary"]["model_market_high_disagreements"],0)
        self.assertFalse(snap["market_publication_time_authenticated"])
        self.assertNotEqual(row["market_observed_utc"],snap["model_forecast_observed_utc"])
    def test_larger_than_ten_point_model_market_gap_is_flagged(self):
        b=board()
        b["games"][0]["model_home_margin"]=28.0
        g=freeze(b,NOW,"888")
        self.assertEqual(g["summary"]["model_market_high_disagreements"],1)
        self.assertEqual(g["rows"][0]["calibration_review_flag"],"HIGH_MODEL_MARKET_DISAGREEMENT")
        self.assertAlmostEqual(g["rows"][0]["model_market_margin_disagreement"],20.5)
    def test_future_collection_not_accepted(self):
        b=board();b["games"][0]["market_observed_utc"]="2026-10-24T16:00:00Z"
        with self.assertRaises(ValueError):freeze(b,NOW,"888")
    def test_bad_ats_side_fails_closed(self):
        b=board();b["games"][0]["model_ats_side"]="AWAY"
        with self.assertRaises(ValueError):freeze(b,NOW,"888")
    def test_unsourced_odds_cannot_be_recorded(self):
        b=board();b["games"][0]["market_provider"]=None
        with self.assertRaises(ValueError):freeze(b,NOW,"888")
    def test_previously_kicked_game_excluded(self):
        b=board();early=copy.deepcopy(b["games"][0]);early["game_id"]="2"
        early["kickoff_utc"]="2026-10-24T15:00:00Z"
        b["games"].append(early)
        self.assertEqual(len(freeze(b,NOW,"888")["rows"]),1)
        b["games"]= [early]
        with self.assertRaises(ValueError):freeze(b,NOW,"888")
    def test_no_quote_records_no_ats_grade(self):
        b=board();g=b["games"][0]
        for field in ["market_home_spread","market_total","market_provider","market_observed_utc","model_ats_side","model_ou_side"]:
            g[field]=None
        x=freeze(b,NOW,"888")
        self.assertEqual(x["summary"]["games_with_line"],0)
        self.assertIsNone(x["rows"][0]["displayed_ats_side"])
    def test_original_model_forecast_is_never_rewritten(self):
        b=board();g=b["games"][0];g["model_home_margin"]=-4;g["model_ats_side"]="AWAY"
        z=freeze(b,NOW,"888")
        self.assertEqual(z["rows"][0]["frozen_forecast_home_margin"],-4)
        self.assertEqual(z["rows"][0]["displayed_ats_side"],"AWAY")
    def test_duplicate_ids_not_allowed(self):
        b=board();b["games"].append(copy.deepcopy(b["games"][0]))
        with self.assertRaises(ValueError):freeze(b,NOW,"888")
if __name__=="__main__":unittest.main()

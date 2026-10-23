import unittest
from copy import deepcopy
from scripts.free_market_performance import report,stats

class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.match={"forecast_run_id":"10","game_id":"1","provider":"ESPN",
            "status":"MATCHED_VERIFIED_FINAL","home_score":31,"away_score":24,
            "kickoff_utc":"2026-10-24T20:00:00Z",
            "forecast_observed_utc":"2026-10-23T18:00:00Z",
            "market_observed_utc":"2026-10-23T17:00:00Z",
            "market_home_spread":-3.5,"market_total":50,
            "ats_selection":"HOME","total_selection":"OVER"}
        self.grade={"forecast_run_id":"10","game_id":"1","provider":"ESPN",
            "match_status":"MATCHED_VERIFIED_FINAL","ats":"WIN","total":"WIN"}
        self.matches={"status":"VERIFIED_MARKET_FINAL_MATCH_RESEARCH_ONLY",
            "safe_for_betting":False,"rows":[self.match]}
        self.grades={"status":"VERIFIED_PROSPECTIVE_MARKET_GRADES_RESEARCH_ONLY",
            "safe_for_betting":False,"asof_utc":"2026-10-25T00:00:00Z","rows":[self.grade]}
    def run_report(self):
        return report(self.matches,self.grades,[1,0,None])
    def test_summary_and_su(self):
        r=self.run_report()
        self.assertEqual(r["summary"]["su"]["decisions"],2)
        self.assertEqual(r["summary"]["ats"]["wins"],1)
        self.assertEqual(r["summary"]["total"]["wins"],1)
        self.assertEqual(r["benchmarks"]["ats_always_home"]["wins"],1)
    def test_repeated_forecast_not_double_counted(self):
        m=deepcopy(self.match);g=deepcopy(self.grade)
        m["forecast_run_id"]=g["forecast_run_id"]="11"
        m["forecast_observed_utc"]="2026-10-23T19:00:00Z"
        g["ats"]="LOSS";g["total"]="LOSS"
        self.matches["rows"].append(m);self.grades["rows"].append(g)
        r=self.run_report()
        self.assertEqual(r["summary"]["ats"]["wins"],1)
        self.assertEqual(r["summary"]["ats"]["losses"],0)
        self.assertEqual(r["summary"]["duplicates_excluded"]["ats"],1)
    def test_missing_grade_rejected(self):
        self.grades["rows"]=[]
        with self.assertRaises(ValueError):self.run_report()
    def test_duplicate_rejected(self):
        self.grades["rows"].append(deepcopy(self.grade))
        with self.assertRaises(ValueError):self.run_report()
    def test_zero_sample(self):
        self.assertIsNone(stats([])["win_rate"])
    def test_unverified_grade_rejected(self):
        self.match["status"]="AWAITING_VERIFIED_FINAL"
        with self.assertRaises(ValueError):self.run_report()

if __name__=="__main__":unittest.main()

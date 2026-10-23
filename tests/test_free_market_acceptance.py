import unittest
from copy import deepcopy
from scripts.free_market_final_grade import settle
from scripts.free_market_performance import report
from scripts.free_market_acceptance import audit

class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.row={"forecast_run_id":"10","game_id":"1","provider":"ESPN",
            "home":"Home","away":"Away",
            "status":"MATCHED_VERIFIED_FINAL","home_score":31,"away_score":24,
            "kickoff_utc":"2026-10-24T20:00:00Z",
            "forecast_observed_utc":"2026-10-23T18:00:00Z",
            "market_observed_utc":"2026-10-23T17:00:00Z",
            "final_observed_at_utc":"2026-10-25T00:00:00Z",
            "final_archive_path":"research_2026/observed_finals/1.json.gz",
            "final_record_sha256":"a"*64,
            "market_home_spread":-3.5,"market_total":50,
            "ats_selection":"HOME","total_selection":"OVER"}
        self.matches={"status":"VERIFIED_MARKET_FINAL_MATCH_RESEARCH_ONLY",
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
            "asof_utc":"2026-10-26T00:00:00Z",
            "rows":[self.row],"summary":{"total":1,"MATCHED_VERIFIED_FINAL":1}}
        self.refresh()
    def refresh(self):
        self.grades=settle(self.matches)
        self.performance=report(self.matches,self.grades,[1,0,None])
    def check(self):
        return audit(self.matches,self.grades,self.performance,[1,0,None])
    def test_full_lifecycle(self):
        a=self.check()
        self.assertEqual(a["evidence"]["ats_unique_games"],1)
        self.assertEqual(a["checks"]["independent_grade_recalculation"],"PASS")
    def test_repeated_audit_is_identical(self):
        self.assertEqual(self.check(),self.check())
    def test_tampered_grade_rejected(self):
        self.grades["rows"][0]["ats"]="LOSS"
        with self.assertRaises(ValueError):self.check()
    def test_tampered_performance_rejected(self):
        self.performance["summary"]["ats"]["wins"]=99
        with self.assertRaises(ValueError):self.check()
    def test_invalid_chronology_rejected(self):
        self.row["market_observed_utc"]="2026-10-24T21:00:00Z"
        with self.assertRaises(ValueError):self.check()
    def test_bad_final_digest_rejected(self):
        self.row["final_record_sha256"]="bad"
        with self.assertRaises(ValueError):self.check()
    def test_duplicate_forecast_excluded(self):
        other=deepcopy(self.row);other["forecast_run_id"]="11"
        other["forecast_observed_utc"]="2026-10-23T19:00:00Z"
        self.matches["rows"].append(other)
        self.matches["summary"]={"total":2,"MATCHED_VERIFIED_FINAL":2}
        self.refresh()
        self.assertEqual(self.check()["evidence"]["ats_unique_games"],1)
        self.assertEqual(self.performance["summary"]["duplicates_excluded"]["ats"],1)
    def test_unverified_final_not_graded(self):
        self.row["status"]="AWAITING_VERIFIED_FINAL"
        self.matches["summary"]={"total":1,"AWAITING_VERIFIED_FINAL":1}
        self.refresh()
        self.assertEqual(self.check()["evidence"]["ats_unique_games"],0)
    def test_missing_grade_rejected(self):
        self.grades["rows"]=[]
        with self.assertRaises(ValueError):self.check()

if __name__=="__main__":unittest.main()

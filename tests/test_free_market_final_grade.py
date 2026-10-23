import unittest
from copy import deepcopy
from scripts.free_market_final_grade import settle

class MarketGradeTests(unittest.TestCase):
    def setUp(self):
        self.row={"forecast_run_id":"100","game_id":"123","provider":"ESPN",
            "status":"MATCHED_VERIFIED_FINAL",
            "final_archive_path":"research_2026/outcomes/x.json.gz",
            "final_record_sha256":"digest","final_observed_at_utc":"2026-10-25T01:00:00Z",
            "home_score":31,"away_score":24,"ats_selection":"HOME",
            "total_selection":"OVER","market_home_spread":-3.5,"market_total":50}
        self.board={"status":"VERIFIED_MARKET_FINAL_MATCH_RESEARCH_ONLY",
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
            "asof_utc":"2026-10-26T00:00:00Z","rows":[self.row]}
    def grade(self):
        return settle(self.board)["rows"][0]
    def test_home_and_over_win(self):
        self.assertEqual((self.grade()["ats"],self.grade()["total"]),("WIN","WIN"))
    def test_away_and_under_win(self):
        self.row.update(ats_selection="AWAY",total_selection="UNDER")
        self.assertEqual((self.grade()["ats"],self.grade()["total"]),("LOSS","LOSS"))
    def test_push_both(self):
        self.row.update(market_home_spread=-7,market_total=55)
        self.assertEqual((self.grade()["ats"],self.grade()["total"]),("PUSH","PUSH"))
    def test_pass_both(self):
        self.row.update(ats_selection="PASS",total_selection="PASS",
            market_home_spread=None,market_total=None)
        self.assertIsNone(self.grade()["ats"])
        self.assertIsNone(self.grade()["total"])
    def test_missing_final_never_graded(self):
        self.row["status"]="AWAITING_VERIFIED_FINAL"
        self.assertEqual(self.grade()["status"],"NOT_GRADED")
    def test_rescheduled_never_graded(self):
        self.row["status"]="KICKOFF_CHANGED_NO_AUTOMATIC_MATCH"
        self.assertIsNone(self.grade()["ats"])
    def test_no_line_rejected(self):
        self.row["market_home_spread"]=None
        with self.assertRaises(ValueError):self.grade()
    def test_duplicate_rejected(self):
        self.board["rows"].append(deepcopy(self.row))
        with self.assertRaises(ValueError):settle(self.board)
    def test_bad_provenance_rejected(self):
        self.row.pop("final_record_sha256")
        with self.assertRaises(ValueError):self.grade()
    def test_invalid_status_rejected(self):
        self.row["status"]="UNVERIFIED"
        with self.assertRaises(ValueError):self.grade()

if __name__=="__main__":unittest.main()

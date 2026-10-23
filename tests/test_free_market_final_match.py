import unittest
from unittest.mock import patch
from scripts.free_market_final_match import match

class FinalMatchingTests(unittest.TestCase):
    def setUp(self):
        self.row={"game_id":"123","provider":"ESPN","home":"Home","away":"Away",
          "kickoff_utc":"2026-10-24T20:00:00+00:00",
          "market_observed_utc":"2026-10-23T18:00:00+00:00",
          "forecast_observed_utc":"2026-10-23T19:00:00+00:00",
          "ats_selection":"HOME","total_selection":"OVER",
          "market_home_spread":-3.5,"market_total":50,
          "status":"FROZEN_RESEARCH_COMPARISON_NOT_BETTING_VALIDATED"}
        self.boards={"12":{"status":"PROSPECTIVE_MARKET_RESEARCH",
          "betting_status":"PASS_UNVALIDATED","rows":[self.row]}}
        self.final={"game_id":"123","home":"Home","away":"Away",
          "kickoff_utc":self.row["kickoff_utc"],"home_score":35,"away_score":28,
          "observed_at_utc":"2026-10-25T02:00:00+00:00",
          "outcome_known_at_utc":"2026-10-25T01:00:00+00:00"}
        self.index={"status":"ASOF_OUTCOME_ARCHIVE_RESEARCH_ONLY",
          "season":2026,"safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
          "games":{"123":{"archive_path":"research_2026/outcomes/123.json.gz",
            "home":"Home","away":"Away","home_score":35,"away_score":28,
            "kickoff_utc":self.row["kickoff_utc"],"record_sha256":"hash",
            "selected_pregame":{}}}}
        self.finals={"research_2026/outcomes/123.json.gz":self.final}
    def check(self):
        with patch("scripts.free_market_final_match.safe_path"),patch(
          "scripts.free_market_final_match._check_label",return_value=True):
            return match(self.boards,self.index,self.finals,"2026-10-26T00:00:00+00:00")
    def test_verified_match(self):
        row=self.check()["rows"][0]
        self.assertEqual(row["status"],"MATCHED_VERIFIED_FINAL")
        self.assertEqual(row["home_score"],35)
    def test_team_swap_quarantined(self):
        self.row["home"]="Wrong"
        self.assertEqual(self.check()["rows"][0]["status"],"IDENTITY_MISMATCH")
    def test_reschedule_quarantined(self):
        self.row["kickoff_utc"]="2026-10-24T21:00:00+00:00"
        self.assertEqual(self.check()["rows"][0]["status"],"KICKOFF_CHANGED_NO_AUTOMATIC_MATCH")
    def test_unobserved(self):
        self.index["games"]={}
        self.finals={}
        self.assertEqual(self.check()["rows"][0]["status"],"AWAITING_VERIFIED_FINAL")
    def test_tampered_score_rejected(self):
        self.final["home_score"]=40
        with self.assertRaises(ValueError):self.check()

if __name__=="__main__":unittest.main()

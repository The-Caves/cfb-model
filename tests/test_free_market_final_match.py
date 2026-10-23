import unittest
from copy import deepcopy
from scripts import context_archive as store
from scripts.market_finals_archive import empty,plan
from scripts.free_market_final_match import match
import hashlib

class IndependentFinalTests(unittest.TestCase):
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
        self.score={"game_id":"123","home":"Home","away":"Away",
          "kickoff_utc":self.row["kickoff_utc"],"home_score":"35","away_score":"28"}
        self.manifest={"status":"SUCCESS","failures":[],
          "scoreboard_date_timezone":"America/New_York",
          "retrieved_at_utc":"2026-10-25T01:00:00+00:00"}
        self.now="2026-10-25T01:01:00+00:00"
    def archive(self):
        index,new,_=plan(empty(),[self.score],self.manifest,b"source",self.now)
        return index,{new[0][0]:new[0][1]}
    def check(self,index=None,finals=None):
        if index is None:index,finals=self.archive()
        return match(self.boards,index,finals,"2026-10-26T00:00:00+00:00")
    def test_independent_final_matches_without_personnel_capture(self):
        self.assertEqual(self.check()["rows"][0]["status"],"MATCHED_VERIFIED_FINAL")
    def test_replay_does_not_add_duplicate(self):
        index,finals=self.archive()
        next_index,new,conflicts=plan(index,[self.score],self.manifest,b"source",self.now)
        self.assertEqual(len(new),0)
        self.assertEqual(index,next_index)
    def test_score_revision_requires_review(self):
        index,_=self.archive()
        self.score["home_score"]="36"
        _,new,conflicts=plan(index,[self.score],self.manifest,b"source",self.now)
        self.assertEqual(len(new),0)
        self.assertEqual(conflicts["123"],"CHANGED_FINAL_REQUIRES_REVIEW")
    def test_mismatched_team_not_graded(self):
        self.row["home"]="Wrong"
        self.assertEqual(self.check()["rows"][0]["status"],"IDENTITY_MISMATCH")
    def test_kickoff_change_not_graded(self):
        self.row["kickoff_utc"]="2026-10-24T21:00:00+00:00"
        self.assertEqual(self.check()["rows"][0]["status"],"KICKOFF_CHANGED_NO_AUTOMATIC_MATCH")
    def test_missing_final_remains_pending(self):
        self.assertEqual(self.check(empty(),{})["rows"][0]["status"],"AWAITING_VERIFIED_FINAL")
    def test_tampered_score_fails_closed(self):
        index,finals=self.archive()
        finals[next(iter(finals))]["home_score"]=40
        with self.assertRaises(ValueError):self.check(index,finals)
    def test_stale_scoreboard_rejected(self):
        with self.assertRaises(ValueError):
            plan(empty(),[self.score],self.manifest,b"source","2026-10-26T01:00:00+00:00")
    def test_empty_index_is_valid(self):
        self.assertEqual(self.check(empty(),{})["summary"]["AWAITING_VERIFIED_FINAL"],1)
    def test_future_score_rejected(self):
        self.score["kickoff_utc"]="2026-10-26T20:00:00+00:00"
        with self.assertRaises(ValueError):self.archive()

if __name__=="__main__":unittest.main()

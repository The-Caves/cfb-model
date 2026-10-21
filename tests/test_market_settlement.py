"""Synthetic market settlement with strict pregame/label separation."""
import copy
import tempfile
import unittest
from pathlib import Path

from scripts.market_quotes import normalize
from scripts.market_vault import store
from scripts.market_features import market_board
from scripts.market_event_crosswalk import norm
from scripts.market_settlement import exact_score, grade_selection, settle_markets

HOME="Fictional Home College"
AWAY="Fictional Away College"
KICK="2026-10-24T20:00:00Z"
CAPTURE="2026-10-21T17:00:00Z"
DECISION="2026-10-21T18:00:00Z"
FINAL_FETCH="2026-10-25T03:00:00Z"
PRE={"game_id":"test-espn-101","home":HOME,"away":AWAY,
     "home_id":"10","away_id":"11","kickoff_utc":KICK,"completed":False}
ALIASES={norm(HOME):HOME,norm(AWAY):AWAY}

def context():
    return {"asof_utc":"2026-10-21T16:00:00Z","games":[PRE]}

def final(home=27,away=24):
    return {"game_id":PRE["game_id"],"home":HOME,"away":AWAY,
            "kickoff_utc":KICK,"home_score":home,"away_score":away}

def provider():
    return [{"id":"source-101","sport_key":"americanfootball_ncaaf",
       "commence_time":KICK,"home_team":HOME,"away_team":AWAY,
       "bookmakers":[{"key":"fanduel","markets":[
          {"key":"h2h","last_update":CAPTURE,"outcomes":[
              {"name":HOME,"price":-150},{"name":AWAY,"price":130}]},
          {"key":"spreads","last_update":CAPTURE,"outcomes":[
              {"name":HOME,"point":-3.0,"price":-110},
              {"name":AWAY,"point":3.0,"price":-110}]},
          {"key":"totals","last_update":CAPTURE,"outcomes":[
              {"name":"Over","point":51.0,"price":-112},
              {"name":"Under","point":51.0,"price":-108}]}]}]}]

class MarketSettlementTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db=Path(temp.name)/"quotes.sqlite3"
        store(db,normalize(provider(),CAPTURE))
        self.board=market_board(db,context(),ALIASES,DECISION)
        self.assertEqual(self.board["qa"]["matched_events"],1)
    def settle(self,finals=None,**kwargs):
        return settle_markets(self.board,context(),
             [final()] if finals is None else finals,
             kwargs.get("retrieved_at",FINAL_FETCH))
    def test_moneyline_and_spread_total_pushes(self):
        result=self.settle()
        self.assertEqual(len(result["features"]),6)
        self.assertEqual(len(result["postgame_labels"]),6)
        lookup={(x["market"],x["selection"]):x["settlement"]
                for x in result["postgame_labels"]
                for f in result["features"] if f["row_id"]==x["row_id"]}
        self.assertEqual(lookup[("MONEYLINE","HOME")],"WIN")
        self.assertEqual(lookup[("MONEYLINE","AWAY")],"LOSS")
        for key in (("SPREAD","HOME"),("SPREAD","AWAY"),
                    ("TOTAL","OVER"),("TOTAL","UNDER")):
            self.assertEqual(lookup[key],"PUSH")
        self.assertEqual(result["status"],"PRE_AND_POSTGAME_SEPARATED_RESEARCH")
        self.assertEqual(result["betting_status"],"PASS_UNVALIDATED")
        self.assertFalse(result["safe_for_betting"])
    def test_final_results_cannot_appear_in_feature_records(self):
        result=self.settle()
        for feature in result["features"]:
            for private_key in ("home_score","away_score","settlement","outcome_known_at_utc",
                                "winner","profit","roi"):
                self.assertNotIn(private_key,feature)
            self.assertEqual(feature["market_source_sha256"],
                             self.board["events"][0]["markets"][feature["market"]]
                                       ["latest_observed_source_sha256"])
        for outcome in result["postgame_labels"]:
            self.assertNotIn("american_odds",outcome)
            self.assertNotIn("home_score",outcome)
            self.assertEqual(outcome["outcome_known_at_utc"],FINAL_FETCH)
    def test_moneyline_tie_is_push(self):
        self.assertEqual(grade_selection("MONEYLINE","HOME",None,28,28),"PUSH")
        self.assertEqual(grade_selection("MONEYLINE","AWAY",None,28,28),"PUSH")
    def test_spread_and_total_win_loss(self):
        self.assertEqual(grade_selection("SPREAD","HOME",-4.5,27,24),"LOSS")
        self.assertEqual(grade_selection("SPREAD","AWAY",4.5,27,24),"WIN")
        self.assertEqual(grade_selection("TOTAL","OVER",50.5,27,24),"WIN")
        self.assertEqual(grade_selection("TOTAL","UNDER",50.5,27,24),"LOSS")
    def test_invalid_final_scores_are_skipped(self):
        for invalid in (-1,True,2.5,"27.5",None,999):
            with self.subTest(invalid=invalid):
                result=self.settle([final(home=invalid)])
                self.assertEqual(result["features"],[])
                self.assertEqual(result["qa"]["invalid_final_score"],1)
    def test_unmatched_final_does_not_generate_training_labels(self):
        r=self.settle([])
        self.assertEqual(r["features"],[])
        self.assertEqual(r["qa"]["final_not_available"],1)
    def test_reversed_final_team_names_are_quarantined(self):
        r=self.settle([{**final(),"home":AWAY,"away":HOME}])
        self.assertEqual(r["features"],[])
        self.assertEqual(r["qa"]["final_team_mismatch"],1)
    def test_changed_kickoff_is_quarantined(self):
        r=self.settle([{**final(),"kickoff_utc":"2026-10-24T22:00:00Z"}])
        self.assertEqual(r["features"],[])
        self.assertEqual(r["qa"]["final_kickoff_mismatch"],1)
    def test_final_retrieval_before_kickoff_is_quarantined(self):
        r=self.settle(retrieved_at="2026-10-24T19:00:00Z")
        self.assertEqual(r["features"],[])
        self.assertEqual(r["qa"]["final_retrieval_before_kickoff"],1)
    def test_publication_before_prediction_cannot_be_final(self):
        with self.assertRaises(ValueError):
            self.settle(retrieved_at="2026-10-21T17:00:00Z")
    def test_market_decision_after_kickoff_does_not_get_labels(self):
        board=copy.deepcopy(self.board)
        board["decision_asof_utc"]="2026-10-24T21:00:00Z"
        r=settle_markets(board,context(),[final()],FINAL_FETCH)
        self.assertEqual(r["features"],[])
        self.assertEqual(r["qa"]["decision_not_before_kickoff"],1)
    def test_post_decision_quote_cannot_be_retrospectively_added(self):
        board=copy.deepcopy(self.board)
        board["events"][0]["markets"]["SPREAD"]["latest_retrieved_at_utc"]="2026-10-26T17:00:00Z"
        with self.assertRaises(ValueError):
            settle_markets(board,context(),[final()],FINAL_FETCH)
    def test_result_identity_cannot_be_duplicated(self):
        with self.assertRaises(ValueError):
            self.settle([final(),final()])
    def test_invalid_research_flag_fails_closed(self):
        board=copy.deepcopy(self.board)
        board["safe_for_betting"]=True
        with self.assertRaises(ValueError):
            settle_markets(board,context(),[final()],FINAL_FETCH)
    def test_no_vig_is_not_an_actual_model_prediction(self):
        r=self.settle()
        self.assertFalse(any("model_probability" in row for row in r["features"]))
        self.assertFalse(any("calibrated" in row for row in r["postgame_labels"]))

if __name__=="__main__":
    unittest.main()

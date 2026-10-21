"""Walk-forward market folds must not use future outcome information."""
import copy
import unittest
from scripts.market_walkforward import build_folds

CUTS=["2026-10-15T00:00:00Z","2026-10-22T00:00:00Z",
      "2026-10-29T00:00:00Z"]
ASOF="2026-10-30T12:00:00Z"
def feature(game,decision,kickoff,market="SPREAD",side="HOME"):
    rid="|".join((game,"fanduel",market,side,decision))
    return {"row_id":rid,"espn_game_id":game,"bookmaker":"fanduel",
            "market":market,"selection":side,"line_points":-3.5,
            "american_odds":-110,"decision_asof_utc":decision,
            "kickoff_utc":kickoff,
            "pregame_context_asof_utc":"2026-10-01T00:00:00Z",
            "market_observed_at_utc":decision,
            "market_retrieved_at_utc":decision,
            "market_source_sha256":"a"*64,
            "status":"PREGAME_RESEARCH_FEATURE_ONLY"}
def label(row,known,settlement="WIN"):
    return {"row_id":row["row_id"],"espn_game_id":row["espn_game_id"],
            "outcome_known_at_utc":known,
            "settlement":settlement,"status":"POSTGAME_LABEL_ONLY"}
def sample():
    a=feature("a","2026-10-09T17:00:00Z","2026-10-10T20:00:00Z")
    b=feature("b","2026-10-16T17:00:00Z","2026-10-17T20:00:00Z")
    c=feature("c","2026-10-23T17:00:00Z","2026-10-24T20:00:00Z")
    return [a,b,c],[label(a,"2026-10-11T00:00:00Z"),
                    label(b,"2026-10-18T00:00:00Z","PUSH"),
                    label(c,"2026-10-25T00:00:00Z","LOSS")]
class WalkForwardTests(unittest.TestCase):
    def build(self,features=None,labels=None,**opts):
        f,l=sample()
        return build_folds(f if features is None else features,
                           l if labels is None else labels,CUTS,
                           opts.get("asof",ASOF))
    def test_chronological_train_and_test_are_disjoint(self):
        f,l=sample()
        r=self.build(f,l)
        self.assertEqual(r["status"],"WALK_FORWARD_SPLITS_ONLY")
        self.assertEqual(len(r["folds"]),2)
        first,second=r["folds"]
        self.assertEqual(first["train_row_ids"],[f[0]["row_id"]])
        self.assertEqual(first["test_labeled_row_ids"],[f[1]["row_id"]])
        self.assertEqual(second["train_row_ids"],sorted([f[0]["row_id"],f[1]["row_id"]]))
        self.assertEqual(second["test_labeled_row_ids"],[f[2]["row_id"]])
        self.assertEqual(first["status"],"READY_FOR_RESEARCH_EVALUATION")
        self.assertFalse(r["safe_for_betting"])
        self.assertEqual(r["betting_status"],"PASS_UNVALIDATED")
        self.assertFalse(second["prediction_engine_validated"])
    def test_delayed_label_does_not_enter_train_early(self):
        f,l=sample()
        l[1]["outcome_known_at_utc"]="2026-10-23T18:00:00Z"
        r=self.build(f,l)
        self.assertEqual(r["folds"][1]["train_row_ids"],[f[0]["row_id"]])
        self.assertEqual(r["folds"][1]["excluded"]
                         ["historical_label_not_known_at_training_cutoff"],1)
    def test_future_unknown_result_remains_pending(self):
        f,l=sample()
        r=self.build(f,l[:2])
        self.assertEqual(r["folds"][1]["test_pending_row_ids"],[f[2]["row_id"]])
        self.assertEqual(r["folds"][1]["test_labeled_row_ids"],[])
        self.assertEqual(r["folds"][1]["status"],
                         "INSUFFICIENT_TRAINING_OR_TEST_LABELS")
    def test_evaluation_asof_before_last_label_is_pending(self):
        f,l=sample()
        r=self.build(f,l,asof="2026-10-24T22:00:00Z")
        self.assertEqual(r["folds"][1]["test_pending_row_ids"],[f[2]["row_id"]])
    def test_repeated_game_selection_rejected(self):
        f,l=sample()
        repeated=copy.deepcopy(f[0])
        repeated["row_id"]="other-row-id"
        with self.assertRaisesRegex(ValueError,"Repeated game"):
            self.build(f+[repeated],l)
    def test_postdecision_market_capture_rejected(self):
        f,l=sample()
        f[1]["market_retrieved_at_utc"]="2026-10-18T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"Future pregame"):
            self.build(f,l)
    def test_future_espn_features_rejected(self):
        f,l=sample()
        f[1]["pregame_context_asof_utc"]="2026-10-17T22:00:00Z"
        with self.assertRaisesRegex(ValueError,"Future pregame"):
            self.build(f,l)
    def test_postgame_score_in_features_rejected(self):
        f,l=sample()
        f[1]["away_score"]=20
        with self.assertRaisesRegex(ValueError,"outcome leaked"):
            self.build(f,l)
    def test_game_kickoff_before_decision_rejected(self):
        f,l=sample()
        f[2]["decision_asof_utc"]="2026-10-25T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"Decision cannot"):
            self.build(f,l)
    def test_unreconciled_or_mismatched_outcome_rejected(self):
        f,l=sample()
        l[0]["espn_game_id"]="wrong"
        with self.assertRaisesRegex(ValueError,"wrong ESPN"):
            self.build(f,l)
    def test_outcome_timestamp_before_kickoff_rejected(self):
        f,l=sample()
        l[0]["outcome_known_at_utc"]="2026-10-09T10:00:00Z"
        with self.assertRaisesRegex(ValueError,"early final"):
            self.build(f,l)
    def test_duplicate_labels_rejected(self):
        f,l=sample()
        with self.assertRaisesRegex(ValueError,"Duplicate settlement"):
            self.build(f,l+l[:1])
    def test_labels_for_nonexistent_features_rejected(self):
        f,l=sample()
        l.append({"row_id":"unknown","espn_game_id":"unknown",
                  "outcome_known_at_utc":ASOF,"settlement":"WIN",
                  "status":"POSTGAME_LABEL_ONLY"})
        with self.assertRaisesRegex(ValueError,"without matching"):
            self.build(f,l)
    def test_nonchronological_boundaries_rejected(self):
        f,l=sample()
        with self.assertRaisesRegex(ValueError,"increasing"):
            build_folds(f,l,CUTS[::-1],ASOF)
    def test_pregame_decision_before_test_window_is_not_regraded_as_new_pick(self):
        f,l=sample()
        f[1]["decision_asof_utc"]="2026-10-14T19:00:00Z"
        f[1]["market_observed_at_utc"]="2026-10-14T19:00:00Z"
        f[1]["market_retrieved_at_utc"]="2026-10-14T19:00:00Z"
        r=self.build(f,l)
        self.assertEqual(r["folds"][0]["test_labeled_row_ids"],[])
        self.assertEqual(r["folds"][0]["excluded"]
                         ["decision_before_test_window"],1)
if __name__=="__main__":
    unittest.main()

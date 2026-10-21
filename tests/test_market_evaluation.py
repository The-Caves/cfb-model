"""Synthetic-only walk-forward probability scoring; no wagering predictions."""
import copy
import unittest
from scripts.market_walkforward import build_folds
from scripts.market_evaluation import evaluate_folds,binary_metrics

CUTS=["2026-10-15T00:00:00Z","2026-10-22T00:00:00Z",
      "2026-10-29T00:00:00Z"]
LAST="2026-10-30T12:00:00Z"
def game(gid,decision,kickoff,known,home_result="WIN"):
    data=[];labels=[];forecasts=[]
    outcomes={"HOME":home_result,"AWAY":
              "PUSH" if home_result=="PUSH" else
              "LOSS" if home_result=="WIN" else "WIN"}
    for side in ("HOME","AWAY"):
        rid="|".join((gid,"fanduel","SPREAD",side,decision))
        row={"row_id":rid,"espn_game_id":gid,"bookmaker":"fanduel",
             "market":"SPREAD","selection":side,
             "line_points":-3.5 if side=="HOME" else 3.5,
             "american_odds":-110,
             "decision_asof_utc":decision,"kickoff_utc":kickoff,
             "pregame_context_asof_utc":"2026-10-01T00:00:00Z",
             "market_observed_at_utc":decision,
             "market_retrieved_at_utc":decision,
             "market_source_sha256":gid.zfill(64)[-64:],
             "status":"PREGAME_RESEARCH_FEATURE_ONLY"}
        data.append(row)
        labels.append({"row_id":rid,"espn_game_id":gid,
              "outcome_known_at_utc":known,"settlement":outcomes[side],
              "status":"POSTGAME_LABEL_ONLY"})
        forecasts.append({"row_id":rid,
             "selection_win_probability":.65 if side=="HOME" else .35,
             "issued_at_utc":decision,
             "training_data_cutoff_utc":
                "2026-10-15T00:00:00Z" if gid=="b" else
                "2026-10-22T00:00:00Z",
             "model_version":"synthetic-research-version"})
    return data,labels,forecasts
def sample():
    specs=[
      ("a","2026-10-09T17:00:00Z","2026-10-10T20:00:00Z",
       "2026-10-11T00:00:00Z","WIN"),
      ("b","2026-10-16T17:00:00Z","2026-10-17T20:00:00Z",
       "2026-10-18T00:00:00Z","WIN"),
      ("c","2026-10-23T17:00:00Z","2026-10-24T20:00:00Z",
       "2026-10-25T00:00:00Z","PUSH")
    ]
    data=[];labels=[];forecasts=[]
    for spec in specs:
        d,l,f=game(*spec)
        data+=d;labels+=l;forecasts+=f
    return data,labels,forecasts
class EvaluationTests(unittest.TestCase):
    def evaluate(self,data=None,labels=None,forecasts=None):
        d,l,f=sample()
        d=d if data is None else data
        l=l if labels is None else labels
        f=f if forecasts is None else forecasts
        folds=build_folds(d,l,CUTS,LAST)
        return evaluate_folds(d,l,f,folds)
    def test_grade_actual_test_only_and_book_price_baseline(self):
        r=self.evaluate()
        self.assertEqual(r["status"],"METRIC_PIPELINE_RESEARCH_ONLY")
        first=r["fold_metrics"][0]
        second=r["fold_metrics"][1]
        self.assertEqual(first["overall"]["graded_nonpush_selections"],2)
        self.assertAlmostEqual(first["overall"]["model_brier"],.1225)
        self.assertAlmostEqual(first["overall"]["market_baseline_brier"],.25)
        self.assertEqual(second["qa"]["push_excluded_from_binary_score"],2)
        self.assertIsNone(second["overall"])
        self.assertFalse(r["model_validated"])
        self.assertEqual(r["betting_status"],"PASS_UNVALIDATED")
    def test_missing_forecast_counted_not_imputed(self):
        d,l,f=sample()
        f=[x for x in f if not (x["row_id"].startswith("b|") and
              x["row_id"].split("|")[3]=="AWAY")]
        r=self.evaluate(d,l,f)
        self.assertEqual(r["fold_metrics"][0]["overall"]
                         ["graded_nonpush_selections"],1)
        self.assertEqual(r["fold_metrics"][0]["qa"]["missing_model_probability"],1)
    def test_probability_not_valid_range_is_refused(self):
        d,l,f=sample()
        f[2]["selection_win_probability"]=1.5
        with self.assertRaisesRegex(ValueError,"Probability"):
            self.evaluate(d,l,f)
    def test_training_cutoff_after_fold_start_is_refused(self):
        d,l,f=sample()
        for forecast in f:
            if forecast["row_id"].startswith("b|"):
                forecast["training_data_cutoff_utc"]="2026-10-18T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"training cutoff"):
            self.evaluate(d,l,f)
    def test_forecast_cannot_be_issued_after_decision(self):
        d,l,f=sample()
        f[2]["issued_at_utc"]="2026-10-18T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"issued after"):
            self.evaluate(d,l,f)
    def test_missing_pair_is_not_market_baseline(self):
        d,l,f=sample()
        d=[x for x in d if not (x["espn_game_id"]=="b" and x["selection"]=="AWAY")]
        l=[x for x in l if x["row_id"] in {x["row_id"] for x in d}]
        f=[x for x in f if x["row_id"] in {x["row_id"] for x in d}]
        r=self.evaluate(d,l,f)
        self.assertIsNone(r["fold_metrics"][0]["overall"])
        self.assertEqual(r["fold_metrics"][0]["qa"]["missing_opposing_market_price"],1)
    def test_opposing_market_quote_with_different_snapshot_is_rejected(self):
        d,l,f=sample()
        for x in d:
            if x["espn_game_id"]=="b" and x["selection"]=="AWAY":
                x["market_source_sha256"]="d"*64
        r=self.evaluate(d,l,f)
        self.assertIsNone(r["fold_metrics"][0]["overall"])
        self.assertEqual(r["fold_metrics"][0]["qa"]
                         ["opposing_price_from_different_snapshot"],2)
    def test_late_label_cannot_be_used_for_evaluation(self):
        d,l,f=sample()
        for x in l:
            if x["espn_game_id"]=="b":
                x["outcome_known_at_utc"]="2026-10-31T00:00:00Z"
        folds=build_folds(d,l,CUTS,LAST)
        self.assertEqual(folds["folds"][0]["test_labeled_row_ids"],[])
    def test_stray_forecast_without_features_is_rejected(self):
        d,l,f=sample()
        f.append({"row_id":"invented","selection_win_probability":.5,
                  "issued_at_utc":"2026-10-17T10:00:00Z",
                  "training_data_cutoff_utc":CUTS[0],
                  "model_version":"synthetic"})
        with self.assertRaisesRegex(ValueError,"without"):
            self.evaluate(d,l,f)
    def test_metric_does_not_prove_statistical_significance(self):
        result=binary_metrics([(1,.9,.5),(0,.1,.5)])
        self.assertLess(result["model_brier"],result["market_baseline_brier"])
        self.assertFalse(result["statistical_significance_established"])
    def test_empty_scoring_is_not_success(self):
        self.assertIsNone(binary_metrics([]))
if __name__=="__main__":
    unittest.main()

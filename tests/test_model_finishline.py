"""Completion gate must fail closed, including zero-finale off-season runs."""
import copy
import unittest

from scripts.model_finishline import build, grade_diagnostics, wilson_interval
from scripts.personnel_validation_readiness import STATUS as READY
from scripts.personnel_forecast_grade import STATUS as GRADED

R={"status":READY,"betting_status":"PASS_UNVALIDATED",
   "safe_for_betting":False,"model_promoted":False,"model_ready_for_promotion":False,
   "valid_paired_game_ids":0,"policy_eligible_game_ids":49,
   "checks":{
     "independent_historical_pbp_publication_verified":False,
     "authentic_predecision_market_spreads_totals_verified":False,
     "at_least_3_nonoverlapping_evaluated_folds":False,
     "at_least_60_matched_heldout_games":False,
     "at_least_25pct_qb_slots_reviewed":False,
     "at_least_60pct_two_team_reports_verified":False,
     "out_of_sample_statistical_significance_verified":False}}
G={"status":GRADED,"betting_status":"PASS_UNVALIDATED",
   "safe_for_betting":False,"model_promoted":False,
   "indexed_final_games":0,"total_frozen_graded_games":0}

def one_grade():
    return {"game_id":"123","status":"OBSERVED_FORECAST_GRADED_RESEARCH_ONLY",
      "safe_for_betting":False,"model_validated":False,"betting_status":"PASS_UNVALIDATED",
      "ats_grade":None,"over_under_grade":None,
      "predicted_margin":3.0,"predicted_total":50.0,
      "actual_margin":7,"actual_total":47,"actual_home_score":27,"actual_away_score":20,
      "uncalibrated_win_probability":0.6,"su_correct":1,
      "uncalibrated_brier_diagnostic":0.16,
      "margin_abs_error":4.0,"total_abs_error":3.0}

class FinishLineTests(unittest.TestCase):
    def test_empty_real_archive_has_no_fake_performance(self):
        result=build(R,G,[])
        self.assertEqual(result["observed"]["frozen_prospective_graded_games"],0)
        self.assertIsNone(result["prospective_research_metrics"]["su_accuracy"])
        self.assertFalse(result["model_promoted"])
        self.assertIn("AUTHENTIC_MARKET_LINES",result["unresolved_requirements"])
    def test_real_grade_arithmetic_and_uncertainty(self):
        r=copy.deepcopy(R);g=copy.deepcopy(G)
        r["valid_paired_game_ids"]=1
        g["indexed_final_games"]=1;g["total_frozen_graded_games"]=1
        result=build(r,g,[one_grade()])
        self.assertEqual(result["prospective_research_metrics"]["margin_mae"],4)
        self.assertEqual(result["prospective_research_metrics"]["uncalibrated_brier"],0.16)
        self.assertEqual(result["prospective_research_metrics"]["su_accuracy"],1)
        self.assertFalse(result["model_validated"])
    def test_duplications_rejected(self):
        v=one_grade()
        with self.assertRaises(ValueError):grade_diagnostics([v,v])
    def test_invented_market_grade_rejected(self):
        v=one_grade();v["ats_grade"]="WIN"
        with self.assertRaises(ValueError):grade_diagnostics([v])
    def test_tampered_final_rejected(self):
        v=one_grade();v["actual_total"]=60
        with self.assertRaises(ValueError):grade_diagnostics([v])
    def test_tampered_brier_rejected(self):
        v=one_grade();v["uncalibrated_brier_diagnostic"]=0.05
        with self.assertRaises(ValueError):grade_diagnostics([v])
    def test_conflicting_su_label_rejected(self):
        v=one_grade();v["su_correct"]=0
        with self.assertRaises(ValueError):grade_diagnostics([v])
    def test_tie_has_no_brier_grade(self):
        v=one_grade()
        v["actual_home_score"]=24;v["actual_away_score"]=24
        v["actual_total"]=48;v["actual_margin"]=0
        v["margin_abs_error"]=3;v["total_abs_error"]=2;v["su_correct"]=None
        v["uncalibrated_brier_diagnostic"]=None
        self.assertEqual(grade_diagnostics([v])["su_graded_games"],0)
    def test_archived_count_discrepancy_rejected(self):
        g=copy.deepcopy(G);g["total_frozen_graded_games"]=1
        with self.assertRaises(ValueError):build(R,g,[])
    def test_unsafe_readiness_fails_closed(self):
        r=copy.deepcopy(R);r["model_promoted"]=True
        with self.assertRaises(ValueError):build(r,G,[])
    def test_malformed_preregistered_checks_rejected(self):
        r=copy.deepcopy(R);r["checks"]["at_least_25pct_qb_slots_reviewed"]="yes"
        with self.assertRaises(ValueError):build(r,G,[])
    def test_wilson_interval_nontrivial(self):
        self.assertIsNone(wilson_interval(0,0))
        self.assertEqual(wilson_interval(100,100)[1],1.0)
        self.assertLess(wilson_interval(10,20)[0],0.5)

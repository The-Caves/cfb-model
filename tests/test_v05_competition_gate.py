"""Hard-stop model competition: historical improvement never authorizes deployment."""
import copy
import unittest
from scripts.v05_competition_gate import assess,STATUS
from scripts.v05_score_benchmark import STATUS as BENCH


def report(v05_better=False):
    return {
        "status":BENCH,"season":2026,"matched_games":301,"n_folds":5,
        "same_team_and_game_ids_for_all_models":True,
        "score_model_promoted":False,"betting_status":"PASS_UNVALIDATED",
        "historical_market_lines_used":False,
        "models":{
            "v04":{"games":301,"margin_mae":13.20,"total_mae":13.48,
                   "su_accuracy":.668},
            "v05_full":{"games":301,
                "margin_mae":12.40 if v05_better else 13.35,
                "total_mae":12.45 if v05_better else 13.32,
                "su_accuracy":.69 if v05_better else .654,
                "predicted_home_fraction":.60 if v05_better else .714}},
        "naive_home_winner_control":{"games":301,"su_accuracy":.581},
        "v05_interval_diagnostics":{
            "calibrated_games":172,"margin_coverage":.855,
            "total_coverage":.82 if v05_better else .721,
            "only_prior_heldout_week_residuals":True}}
        
        
class GateTests(unittest.TestCase):
    def test_realistic_mixed_v05_outcomes_do_not_get_promoted(self):
        g=assess(report())
        self.assertEqual(g["status"],STATUS)
        self.assertFalse(g["historical_screening_all_passed"])
        self.assertFalse(g["research_candidate_ready_for_manual_review"])
        self.assertFalse(g["automatic_model_promotion"])
        self.assertFalse(g["model_promoted"])
        self.assertIn("margin_improvement_at_least_2pct",g["nonpassing_checks"])
        self.assertIn("both_intervals_75pct_or_better",g["nonpassing_checks"])
        self.assertIn("prospective_independently_frozen",g["nonpassing_checks"])

    def test_even_successful_backtest_without_real_prospective_evidence_stays_hold(self):
        g=assess(report(True))
        self.assertTrue(g["historical_screening_all_passed"])
        self.assertFalse(g["verified_prospective_cohort_complete"])
        self.assertFalse(g["research_candidate_ready_for_manual_review"])
        self.assertFalse(g["model_promoted"])

    def test_complete_evidence_only_permits_human_review_not_auto_promotion(self):
        p={"immutable_pregame_forecasts_verified":True,"paired_games":300,
           "completed_weeks":5,
           "market_quotes_at_decision_time_authenticated":True,
           "independent_final_outcomes_verified":True,
           "historical_publication_authentication":True}
        g=assess(report(True),p)
        self.assertTrue(g["research_candidate_ready_for_manual_review"])
        self.assertFalse(g["automatic_model_promotion"])
        self.assertFalse(g["model_promoted"])

    def test_untrusted_forged_or_unpaired_source_is_rejected(self):
        b=report()
        b["same_team_and_game_ids_for_all_models"]=False
        with self.assertRaisesRegex(ValueError,"Unverified"):
            assess(b)
        b=report();b["models"]["v05_full"]["games"]=300
        with self.assertRaisesRegex(ValueError,"Incomplete"):
            assess(b)
        b=report();b["models"]["v05_full"]["total_mae"]=float("nan")
        with self.assertRaisesRegex(ValueError,"Incomplete"):
            assess(b)
        b=report();b["score_model_promoted"]=True
        with self.assertRaisesRegex(ValueError,"Unverified"):
            assess(b)


if __name__=="__main__":unittest.main()

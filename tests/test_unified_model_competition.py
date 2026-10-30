import copy
import unittest
from scripts.unified_model_competition import evaluate

def shadow():
    return {"status":"SHADOW_PROSPECTIVE_PAIRED_GRADING_RESEARCH_ONLY",
        "season":2026,"betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
        "model_promoted":False,"per_game":[{
            "game_id":"101","shadow_run_id":"12345","home":"A","away":"B",
            "actual_margin":10,
            "models":{
                "active_v03":{"predicted_margin":8,"margin_abs_error":2},
                "recency_14d":{"predicted_margin":10,"margin_abs_error":0}
            }
        }]}

def candidates():
    return {"status":"QB_VENUE_TRAVEL_PROSPECTIVE_PAIRED_GRADE_RESEARCH_ONLY",
            "season":2026,"betting_status":"PASS_UNVALIDATED",
            "safe_for_betting":False,"model_promoted":False,"per_game":[{
                "game_id":"101","run_id":"12345","home":"A","away":"B",
                "actual_home_margin":10,"baseline_v03_margin":8,
                "baseline_v03_abs_error":2,
                "model_results":{"qb_conditional":{"prediction":9,"abs_error":1}}
            }]}

class UnifiedModelCompetitionTests(unittest.TestCase):
    def test_consistent_same_game_cohorts_and_no_promotion(self):
        report=evaluate(shadow(),candidates(),min_pairs=2)
        self.assertEqual(report["unique_compared_games"],1)
        self.assertEqual(report["challengers"]["shadow:recency_14d"]["paired_delta_margin_mae"],-2)
        self.assertEqual(report["challengers"]["personnel:qb_conditional"]["paired_delta_margin_mae"],-1)
        self.assertEqual(report["challengers"]["personnel:qb_conditional"]["paired_games"],1)
        self.assertFalse(report["model_promoted"])
        self.assertTrue(report["no_cross_model_ranking_different_cohorts"])

    def test_baseline_disagreement_quarantined(self):
        wrong=candidates()
        wrong["per_game"][0]["baseline_v03_margin"]=11
        wrong["per_game"][0]["baseline_v03_abs_error"]=1
        with self.assertRaises(ValueError):evaluate(shadow(),wrong,min_pairs=2)

    def test_future_model_not_fabricated_from_missing_candidate(self):
        other=candidates();other["per_game"]=[]
        r=evaluate(shadow(),other,min_pairs=2)
        self.assertEqual(r["challenger_count"],1)
        self.assertNotIn("personnel:qb_conditional",r["challengers"])

    def test_mismatch_on_same_game_run_identity(self):
        other=candidates()
        other["per_game"][0]["run_id"]="999999"
        with self.assertRaises(ValueError):evaluate(shadow(),other,min_pairs=2)

    def test_market_stats_are_not_compared_on_different_cohort(self):
        market={"status":"CUMULATIVE_PROSPECTIVE_PERFORMANCE_RESEARCH_ONLY",
                "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
                "model_validated":False,"profitability_calculated":False,
                "summary":{"ats":{"wins":1,"losses":1}},
                "benchmarks":{"ats_always_home":{"wins":1,"losses":1}}}
        report=evaluate(shadow(),candidates(),market,min_pairs=2)
        self.assertFalse(report["market_stats_separate_cohort"]["cross_market_comparison_eligible"])
        bad=copy.deepcopy(market);bad["profitability_calculated"]=True
        with self.assertRaises(ValueError):evaluate(shadow(),candidates(),bad,min_pairs=2)

if __name__=="__main__":
    unittest.main()

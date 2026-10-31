import copy
import unittest

from scripts.site_player_stat_performance import overlay,STATUS,UNAVAILABLE

def board():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED",
        "games":[{"game_id":"100","model_home_margin":3.0,"model_total":49.5,
            "model_home_points":26.1,"model_away_points":23.4}]}
def summary():
    return {"status":"PROSPECTIVE_FROZEN_PLAYER_STAT_MAE_GRADE_RESEARCH_ONLY",
        "season":2026,"betting_status":"PASS_UNVALIDATED",
        "model_promoted":False,"safe_for_betting":False,
        "no_bookmaker_prop_lines_or_return_calculated":True,
        "first_valid_pregame_snapshot_only":True,
        "missing_player_or_category_is_not_zero_or_assumed_dnp":True,
        "graded_at_utc":"2026-11-02T19:00:00Z",
        "archive_verification":{"archive_status":"VALID_PREKICKOFF_PLAYER_STAT_ARCHIVES",
            "archived_forecasts_across_runs":1800},
        "eligible_unique_pre_kickoff_player_forecasts":900,
        "graded_recorded_player_stat_samples":12,
        "player_category_coverage_rate":.01333,
        "metrics":{
          "passing_yards":{"graded_recorded_player_games":4,
             "playerform_conditional_mae":68.2,"playerform_mean_signed_error":5.1,
             "paired_with_frozen_recent_four_baseline":3,"paired_mae_improvement":-.9},
          "rushing_yards":{"graded_recorded_player_games":5,
             "playerform_conditional_mae":19.7,"playerform_mean_signed_error":-2.0,
             "paired_with_frozen_recent_four_baseline":5,"paired_mae_improvement":1.2},
          "receiving_yards":{"graded_recorded_player_games":3,
             "playerform_conditional_mae":14.7,"playerform_mean_signed_error":1.4,
             "paired_with_frozen_recent_four_baseline":0,"paired_mae_improvement":None}}}

class SitePerformanceTests(unittest.TestCase):
    def test_none_before_first_grade_is_honest_and_score_unaffected(self):
        b=board();original=copy.deepcopy(b["games"])
        r=overlay(b,None,now="2026-10-31T19:00:00Z")
        self.assertEqual(r["player_stat_performance"]["status"],UNAVAILABLE)
        self.assertEqual(r["games"],original)

    def test_good_grade_shows_each_stat_as_separate_research_cohort(self):
        b=board();r=overlay(b,summary(),now="2026-11-03T19:00:00Z")
        self.assertEqual(r["player_stat_performance"]["status"],STATUS)
        self.assertEqual(r["player_stat_performance"]["graded_recorded_player_stat_samples"],12)
        self.assertEqual(r["player_stat_performance"]["metrics"]["rushing_yards"]["paired_mae_improvement"],1.2)
        self.assertTrue(r["player_stat_performance"]["player_stat_accuracy_not_market_betting_prop_accuracy"])
        self.assertEqual(r["games"][0]["model_home_margin"],3.0)

    def test_future_or_fake_sportsbook_grades_fail(self):
        x=summary()
        with self.assertRaises(ValueError):overlay(board(),x,now="2026-10-31T19:00:00Z")
        x=summary();x["no_bookmaker_prop_lines_or_return_calculated"]=False
        with self.assertRaises(ValueError):overlay(board(),x,now="2026-11-03T19:00:00Z")

    def test_unmatched_cohort_and_fabricated_baseline_fail(self):
        x=summary();x["graded_recorded_player_stat_samples"]=10
        with self.assertRaises(ValueError):overlay(board(),x,now="2026-11-03T19:00:00Z")
        x=summary()
        x["metrics"]["receiving_yards"]["paired_mae_improvement"]=0.0
        with self.assertRaises(ValueError):overlay(board(),x,now="2026-11-03T19:00:00Z")

if __name__=="__main__":
    unittest.main()

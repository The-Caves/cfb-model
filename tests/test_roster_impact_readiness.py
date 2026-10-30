import copy
import unittest

from scripts.player_replacement import POSITIONS
from scripts.roster_impact_readiness import evaluate

NOW="2026-10-30T18:00:00Z"
KICK="2026-10-31T16:00:00Z"

def side(coverage="VERIFIED_REPORT_REVIEWED",position="OL"):
    counts = {p:0 for p in POSITIONS}
    if coverage == "VERIFIED_REPORT_REVIEWED":
        counts[position] = 1
    return {
        "coverage":coverage,
        "absences":counts if coverage=="VERIFIED_REPORT_REVIEWED" else None,
        "uncertain":{p:0 for p in POSITIONS} if coverage=="VERIFIED_REPORT_REVIEWED" else None,
        "partial_absences":{p:0 for p in POSITIONS} if coverage=="VERIFIED_REPORT_REVIEWED" else None
    }

def bundle(away=None):
    other=away or side()
    return {"status":"OBSERVED_REPLACEMENT_COUNT_FEATURES_RESEARCH_ONLY",
       "season":2026,"run_id":"123456","captured_at_utc":NOW,
       "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
       "trained_replacement_points":False,
       "games":[{
           "game_id":"101","home":"A","away":"B","kickoff_utc":KICK,
           "decision_asof_utc":NOW,
           "home_report_by_position":side(),
           "away_report_by_position":other,
           "coverage":"BOTH_REPORTS" if other["coverage"]=="VERIFIED_REPORT_REVIEWED" else "INCOMPLETE",
           "injury_adjustment_applied_to_live_model":False
       }]}

class RosterImpactReadinessTests(unittest.TestCase):
    def test_all_positions_are_covered_not_just_quarterbacks(self):
        report=evaluate(bundle(), NOW)
        self.assertEqual(report["summary"]["position_report_counts"]["OL"]["reported_absent"],2)
        self.assertEqual(report["summary"]["valid_learned_player_impacts"],0)
        self.assertIsNone(report["games"][0]["candidate_home_margin_adjustment"])
        self.assertFalse(report["model_promoted"])

    def test_first_half_out_not_counted_as_full_absence(self):
        b=bundle()
        b["games"][0]["home_report_by_position"]["partial_absences"]["OL"]=1
        r=evaluate(b,NOW)
        self.assertEqual(r["summary"]["position_report_counts"]["OL"]["reported_out_first_half"],1)
        self.assertEqual(r["summary"]["position_report_counts"]["OL"]["reported_absent"],2)
        self.assertIsNone(r["games"][0]["candidate_home_margin_adjustment"])

    def test_unknown_opponent_is_not_zero_absences(self):
        report=evaluate(bundle(side("UNKNOWN")), NOW)
        self.assertIsNone(report["games"][0]["teams"]["away"]["reported_out_or_suspended"])
        self.assertEqual(report["summary"]["games_without_complete_injury_coverage"],1)

    def test_bad_count_and_future_capture_rejected(self):
        altered=bundle()
        altered["games"][0]["home_report_by_position"]["absences"]["OL"]=-1
        with self.assertRaises(ValueError):evaluate(altered,NOW)
        with self.assertRaises(ValueError):
            evaluate(bundle(),"2026-10-30T17:00:00Z")

    def test_coverage_disagreement_and_postkickoff_rejected(self):
        altered=bundle(side("UNKNOWN"))
        altered["games"][0]["coverage"]="BOTH_REPORTS"
        with self.assertRaises(ValueError):evaluate(altered,NOW)
        with self.assertRaises(ValueError):evaluate(bundle(),"2026-11-01T10:00:00Z")

if __name__=="__main__":
    unittest.main()

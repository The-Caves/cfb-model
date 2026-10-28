"""Prospective shadow comparison must match the exact original V03 archive."""
import copy
import unittest
from unittest.mock import patch

from scripts.model_shadow_grade import evaluate, STATUS
from scripts.model_shadow_forecast import build_shadow
from tests.test_model_shadow_forecast import fixture

def inputs():
    frozen,games,training=fixture()
    with patch("scripts.model_shadow_forecast.verify_baseline"):
        shadow=build_shadow(frozen,games,{},training,"2026-10-28T12:05:00Z")
    grades=[]
    for row in shadow["games"]:
        grades.append({
            "status":"OBSERVED_FORECAST_GRADED_RESEARCH_ONLY",
            "betting_status":"PASS_UNVALIDATED","model_validated":False,
            "safe_for_betting":False,
            "ats_grade":None,"over_under_grade":None,
            "forecast_run_id":"12345","game_id":row["game_id"],
            "home":row["home"],"away":row["away"],
            "kickoff_utc":row["kickoff_utc"],
            "forecast_bundle_sha256":shadow["baseline_forecast_sha256"],
            "frozen_forecast_row_sha256":row["baseline_row_sha256"],
            "predicted_margin":5.,"predicted_total":54.,
            "actual_margin":10.,"final_outcome_known_at_utc":"2026-11-01T10:00:00Z",
            "observation_policy":"LATEST_ACTUALLY_OBSERVED_FORECAST_24_TO_72_HOURS_BEFORE_KICKOFF"})
    return shadow,grades

class ShadowGradeTests(unittest.TestCase):
    def test_paired_grades_and_incomplete_latent_coverage(self):
        shadow,grades=inputs()
        report=evaluate([shadow],grades,"2026-11-02T12:00:00Z")
        self.assertEqual(report["status"],STATUS)
        self.assertEqual(report["report_summary"]["shadow_linked_eligible_games"],2)
        self.assertEqual(report["report_summary"]["four_way_matched_games"],1)
        self.assertEqual(report["metrics"]["active_v03"]["games"],2)
        self.assertEqual(report["metrics"]["recency_14d"]["games"],2)
        self.assertEqual(report["metrics"]["latent_only"]["games"],1)
        self.assertEqual(report["metrics"]["recency_plus_latent"]["games"],1)
        self.assertEqual(report["four_way_paired"]["active_v03"]["games"],1)
        self.assertEqual(report["four_way_paired"]["recency_plus_latent"]["games"],1)
        self.assertEqual(report["latent_feature_incremental_ablation"]["games"],1)
        self.assertTrue(all("paired_v03_mae" in week["models"]["recency_14d"]
                            for week in report["weekly_paired"].values()))
        self.assertFalse(report["model_promoted"])
        for name,summary in report["metrics"].items():
            self.assertEqual(summary["paired_delta_margin_mae_vs_v03"],
                             round(summary["margin_mae"]-summary["paired_v03_margin_mae"],5))

    def test_missing_selected_run_does_not_backfill_history(self):
        shadow,grades=inputs()
        for item in grades:
            item["forecast_run_id"]="old-run-not-produced"
        report=evaluate([shadow],grades,"2026-11-02T12:00:00Z")
        self.assertEqual(report["report_summary"]["shadow_linked_eligible_games"],0)
        self.assertEqual(report["metrics"]["recency_14d"]["games"],0)
        self.assertEqual(report["report_summary"]["unmatched_reasons"]
                         ["no_shadows_for_selected_baseline_run"],2)

    def test_reference_mismatch_fails_closed(self):
        shadow,grades=inputs()
        changed=copy.deepcopy(grades)
        changed[0]["forecast_bundle_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"Wrong baseline archive"):
            evaluate([shadow],changed,"2026-11-02T12:00:00Z")
        changed=copy.deepcopy(grades)
        changed[0]["frozen_forecast_row_sha256"]="b"*64
        with self.assertRaisesRegex(ValueError,"identity mismatch"):
            evaluate([shadow],changed,"2026-11-02T12:00:00Z")
        changed=copy.deepcopy(grades)
        changed[0]["predicted_margin"]=-7.
        with self.assertRaisesRegex(ValueError,"differs from immutable"):
            evaluate([shadow],changed,"2026-11-02T12:00:00Z")

    def test_postkickoff_and_future_label_refused(self):
        shadow,grades=inputs()
        with self.assertRaisesRegex(ValueError,"chronology"):
            evaluate([shadow],grades,"2026-10-30T10:00:00Z")
        tampered=copy.deepcopy(shadow)
        tampered["shadow_observed_utc"]="2026-11-02T01:00:00Z"
        with self.assertRaisesRegex(ValueError,"postkickoff"):
            evaluate([tampered],grades,"2026-11-02T12:00:00Z")

    def test_bad_grade_or_duplicate_rejected(self):
        shadow,grades=inputs()
        with self.assertRaisesRegex(ValueError,"Duplicate real reference"):
            evaluate([shadow],grades+grades[:1],"2026-11-02T12:00:00Z")
        changed=copy.deepcopy(grades)
        changed[0]["betting_status"]="READY"
        with self.assertRaisesRegex(ValueError,"valid independently"):
            evaluate([shadow],changed,"2026-11-02T12:00:00Z")

if __name__=="__main__":
    unittest.main()

"""Post-instrumentation prospective QB model competition without hiding legacy gaps."""
import copy
import unittest
from test_qb_m1_completion import inputs
from scripts.qb_m1_completion import assess

NOW="2026-11-29T19:00:00Z"


def evidence(eligible=110,paired=100,v04_error=9.,qb_error=7.5,v03_error=8.):
    args=list(inputs())
    for r in args[0]["games"]:r["is_confirmed_starter"]=True
    for r in args[1]["rows"]:r["confirmed_starter"]=True
    args[0]["summary"]["confirmed_starters"]=2
    args[1]["summary"]["confirmed"]=2
    args[3].update({"ready_to_train_injury_qb_model":True,
                    "checks":{"labeled":True},"blocking_reasons":[]})
    args[3]["summary"]["independently_labeled_in_game_qb_replacements"]=25
    # Preserve all old 45 V03-only game grades visibly as unpaired.
    rows=[{"game_id":"old"+str(i),
           "model_results":{"qb_conditional":{"abs_error":11.4}},
           "baseline_v03_abs_error":11.6,
           "v04_same_intake_instrumented":False,"v04_paired_reference":None}
          for i in range(45)]
    for i in range(eligible):
        has_score=i<paired
        pair=({
          "v04_source_kind":"SAME_INTAKE_BEFORE_QB_SHADOW",
          "v04_source_receipt_sha256":"1"*64,
          "kickoff_utc":["2026-11-07T20:00:00Z",
                         "2026-11-14T20:00:00Z",
                         "2026-11-21T20:00:00Z"][i%3],
          "capture_utc":"2026-11-05T15:30:00Z",
          "qb_shadow_observed_utc":"2026-11-05T16:00:00Z",
          "site_snapshot_run_id":None,"site_snapshot_sha256":None,
          "v04_abs_error":v04_error,"qb_conditional_abs_error":qb_error,
          "source_hashed_before_qb_decision":True,
          "market_odds_not_used":True,
          "no_hindsight_recalculation":True}
          if has_score else None)
        rows.append({"game_id":"new"+str(i),
             "model_results":{"qb_conditional":{"abs_error":qb_error}},
             "baseline_v03_abs_error":v03_error,
             "v04_same_intake_instrumented":True,
             "v04_paired_reference":pair})
    group=args[4]["metrics"]["qb_conditional"]
    group.update({"games":len(rows),
       "post_instrumentation_eligible_qb_games":eligible,
       "post_instrumentation_paired_qb_games":paired,
       "post_instrumentation_qb_mae":qb_error if paired else None,
       "post_instrumentation_v04_mae":v04_error if paired else None,
       "post_instrumentation_no_qb_v03_mae":v03_error if paired else None,
       "post_instrumentation_distinct_game_dates":3 if paired>=3 else paired})
    args[4]["per_game"]=rows
    args[4]["v04_comparison_audit"]={
        "status":"QB_SHADOW_EARLIER_WEBSITE_V04_PAIRED_AUDIT_RESEARCH_ONLY",
        "qb_candidate_games":len(rows),
        "same_game_v04_pair_count":paired,
        "distinct_paired_football_dates":3 if paired>=3 else paired,
        "fully_matched_cohort":False,
        "predecision_source_hashed_no_hindsight":True,
        "post_instrumentation_eligible_games":eligible,
        "post_instrumentation_paired_games":paired,
        "post_instrumentation_distinct_game_dates":3 if paired>=3 else paired,
        "post_instrumentation_pair_fraction":round(paired/eligible,5) if eligible else None}
    return args


class ProperProspectiveCohortTests(unittest.TestCase):
    def test_legacy_games_remain_visible_but_do_not_veto_new_100_pair_cohort(self):
        r=assess(*evidence(),now=NOW)
        self.assertTrue(r["milestone_1_evidence_complete"])
        self.assertFalse(r["milestone_1_ready_for_model_promotion"])
        self.assertFalse(r["model_promoted"])
        a=r["sections"]["1D_prospective_qb_validation"]
        self.assertEqual(a["paired_qb_games"],155)
        self.assertEqual(a["post_instrumentation_eligible_games"],110)
        self.assertEqual(a["post_instrumentation_v04_paired_games"],100)
        self.assertEqual(a["post_instrumentation_distinct_football_dates"],3)
        self.assertGreater(a["post_instrumentation_pair_fraction"],.90)
        self.assertTrue(a["post_instrumentation_won_same_game_both_baselines"])

    def test_post_registration_missingness_fails_closed(self):
        r=assess(*evidence(eligible=125,paired=100),now=NOW)
        self.assertFalse(r["milestone_1_evidence_complete"])
        self.assertFalse(r["sections"]["1D_prospective_qb_validation"]["evidence_ready"])
        self.assertLess(r["sections"]["1D_prospective_qb_validation"][
            "post_instrumentation_pair_fraction"],.9)

    def test_no_claimed_lift_if_qb_does_not_beat_both_frozen_controls(self):
        self.assertFalse(assess(*evidence(qb_error=9.1),now=NOW)["milestone_1_evidence_complete"])
        self.assertFalse(assess(*evidence(qb_error=8.1),now=NOW)["milestone_1_evidence_complete"])

    def test_grade_cohort_identity_or_integrity_tampering_is_rejected(self):
        args=evidence()
        args[4]["v04_comparison_audit"]["post_instrumentation_eligible_games"]=109
        with self.assertRaisesRegex(ValueError,"source cohort count"):
            assess(*args,now=NOW)
        args=evidence()
        args[4]["per_game"][45]["v04_paired_reference"]["capture_utc"] = "2026-11-05T16:01:00Z"
        with self.assertRaisesRegex(ValueError,"Untrusted predecision"):
            assess(*args,now=NOW)
        args=evidence()
        args[4]["metrics"]["qb_conditional"]["post_instrumentation_v04_mae"]=8.
        with self.assertRaisesRegex(ValueError,"same-cohort MAE mismatch"):
            assess(*args,now=NOW)

    def test_cannot_exclude_an_instrumented_qb_miss_from_denominator(self):
        args=evidence()
        args[4]["per_game"][45]["v04_same_intake_instrumented"]=False
        with self.assertRaisesRegex(ValueError,"source cohort count"):
            assess(*args,now=NOW)


if __name__=="__main__":unittest.main()

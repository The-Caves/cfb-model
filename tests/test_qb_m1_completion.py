"""Milestone acceptance distinguishes functionality from missing real evidence."""
import copy
import unittest
from scripts.qb_m1_completion import assess, STATUS
from scripts.qb_expected_starters import STATUS as EXPECTED
from scripts.qb_confirmation_coverage import STATUS as COVERAGE
from scripts.qb_conditional_forecast import STATUS as SHADOW
from scripts.qb_trainability_audit import STATUS as TRAINABILITY
from scripts.candidate_shadow_grade import STATUS as GRADE

NOW="2026-11-05T16:05:00Z"
KICK="2026-11-07T20:00:00Z"
ISSUE="2026-11-05T16:00:00Z"


def inputs():
    exp={
        "status":EXPECTED,"season":2026,"observed_at_utc":ISSUE,
        "betting_status":"PASS_UNVALIDATED","model_promoted":False,
        "team_slots":2,"summary":{"confirmed_starters":0},
        "games":[{"game_id":"12","team":t,"opponent":o,"kickoff_utc":KICK,
                  "is_confirmed_starter":False,"starter":t+" QB"}
                 for t,o in (("Home","Away"),("Away","Home"))]}
    coverage={
        "status":COVERAGE,"season":2026,"observed_at_utc":ISSUE,
        "betting_status":"PASS_UNVALIDATED","model_promoted":False,
        "summary":{"confirmed":0},
        "rows":[{"game_id":"12","team":r["team"],"opponent":r["opponent"],
                 "kickoff_utc":KICK,"confirmed_starter":False,
                 "expected_starter":r["starter"]} for r in exp["games"]]}
    shadow={"status":SHADOW,"season":2026,"observed_at_utc":ISSUE,
        "betting_status":"PASS_UNVALIDATED","model_promoted":False,
        "summary":{"games_with_qb_conditional_adjustment":1},
        "games":[{"game_id":"12","home":"Home","away":"Away",
                  "kickoff_utc":KICK,
                  "candidate":{"status":"QB_PLAYER_CONDITIONAL_SHADOW",
                               "model_promoted":False}}]}
    readiness={
        "status":TRAINABILITY,"betting_status":"PASS_UNVALIDATED",
        "trained_qb_replacement_value":False,
        "automatic_model_promotion":False,
        "ready_to_train_injury_qb_model":False,
        "checks":{"both_starters_confirmed_coverage":False,
                  "independent_postgame_qb_participation_and_switch_labels":False},
        "blocking_reasons":["both_starters_confirmed_coverage",
                            "independent_postgame_qb_participation_and_switch_labels"],
        "summary":{"independently_labeled_in_game_qb_replacements":0}}
    grades={"status":GRADE,"betting_status":"PASS_UNVALIDATED",
            "model_promoted":False,"evaluated_at_utc":ISSUE,
            "metrics":{"qb_conditional":{"games":2,"margin_mae":11.4,
                            "same_game_baseline_v03_mae":11.6}}}
    return exp,coverage,shadow,readiness,grades


class CompletionTests(unittest.TestCase):
    def test_green_code_does_not_forge_starter_and_replacement_milestone(self):
        r=assess(*inputs(),now=NOW)
        self.assertEqual(r["status"],STATUS)
        self.assertTrue(r["engineering_workflow_integrated"])
        self.assertFalse(r["milestone_1_evidence_complete"])
        self.assertFalse(r["milestone_1_ready_for_model_promotion"])
        self.assertEqual(len(r["blocked_sections"]),3)
        self.assertEqual(r["sections"]["1A_verified_starting_qb_coverage"]["confirmed_game_team_slots"],0)
        self.assertEqual(r["sections"]["1C_measured_qb_replacement_value"]["actual_independently_labeled_replacements"],0)
        self.assertEqual(r["sections"]["1D_prospective_qb_validation"]["paired_qb_games"],2)
        self.assertFalse(r["automatic_score_adjustment_from_qb_absence"])
        self.assertEqual(len(r["remaining_roadmap_milestones"]),4)

    def test_wrong_game_team_or_starter_source_claim_fails_closed(self):
        args=list(inputs())
        args[1]["rows"][1]["team"]="Wrong"
        with self.assertRaisesRegex(ValueError,"cohorts"):
            assess(*args,now=NOW)
        args=list(inputs())
        args[1]["rows"][0]["confirmed_starter"]=True
        with self.assertRaisesRegex(ValueError,"claim changed"):
            assess(*args,now=NOW)
        args=list(inputs())
        args[2]["games"][0]["home"]="Unknown"
        with self.assertRaisesRegex(ValueError,"source fixture"):
            assess(*args,now=NOW)

    def test_future_shadow_observation_and_false_ready_training_rejected(self):
        args=list(inputs())
        args[2]["observed_at_utc"]="2026-11-05T16:06:00Z"
        with self.assertRaisesRegex(ValueError,"chronology"):
            assess(*args,now=NOW)
        args=list(inputs())
        args[3]["ready_to_train_injury_qb_model"]=True
        args[3]["checks"]={"all":True}
        with self.assertRaisesRegex(ValueError,"verified replacement labels"):
            assess(*args,now=NOW)

    def test_full_synthetic_evidence_still_cannot_promote(self):
        args=list(inputs())
        for r in args[0]["games"]:r["is_confirmed_starter"]=True
        for r in args[1]["rows"]:r["confirmed_starter"]=True
        args[0]["summary"]["confirmed_starters"]=2
        args[1]["summary"]["confirmed"]=2
        args[3]["ready_to_train_injury_qb_model"]=True
        args[3]["checks"]={"labeled_samples":True,"verified_qb":True}
        args[3]["blocking_reasons"]=[]
        args[3]["summary"]["independently_labeled_in_game_qb_replacements"]=25
        args[4]["metrics"]["qb_conditional"]["games"]=100
        # A winning comparison against V03 alone is not sufficient. V03
        # was quarantined for home bias and is not the current score model.
        not_ready=assess(*args,now=NOW)
        self.assertFalse(not_ready["milestone_1_evidence_complete"])
        one=not_ready["sections"]["1D_prospective_qb_validation"]
        self.assertEqual(one["same_cohort_legacy_v03_mae"],11.6)
        self.assertIsNone(one["same_cohort_baseline_mae"])
        self.assertFalse(one["same_game_v04_source_hashed"])
        # A separately verified, exactly paired frozen V04 comparator is
        # required (synthetic here; no real source record is forged).
        group=args[4]["metrics"]["qb_conditional"]
        group["same_game_baseline_v04_mae"]=12.1
        group["same_game_baseline_v04_games"]=100
        group["same_game_v04_pregame_source_hashed"]=True
        # Summary flags without actual game-by-game predecision receipts
        # must never clear an evidence threshold.
        no_receipts=assess(*args,now=NOW)
        self.assertFalse(no_receipts["milestone_1_evidence_complete"])
        args[4]["per_game"]=[{"game_id":str(i),
              "model_results":{"qb_conditional":{}},
              "v04_paired_reference":{
                  "capture_utc":"2026-11-05T15:30:00Z",
                  "qb_shadow_observed_utc":"2026-11-05T16:00:00Z",
                  "site_snapshot_sha256":"a"*64,
                  "source_hashed_before_qb_decision":True,
                  "no_hindsight_recalculation":True,
                  "market_odds_not_used":True}} for i in range(100)]
        args[4]["v04_comparison_audit"]={
            "status":"QB_SHADOW_EARLIER_WEBSITE_V04_PAIRED_AUDIT_RESEARCH_ONLY",
            "qb_candidate_games":100,"same_game_v04_pair_count":100,
            "fully_matched_cohort":True,
            "predecision_source_hashed_no_hindsight":True}
        report=assess(*args,now=NOW)
        self.assertTrue(report["milestone_1_evidence_complete"])
        self.assertFalse(report["milestone_1_ready_for_model_promotion"])
        self.assertFalse(report["model_promoted"])


    def test_v04_comparator_requires_exact_source_paired_games(self):
        args=list(inputs())
        group=args[4]["metrics"]["qb_conditional"]
        group.update({"games":100,"margin_mae":11.0,
                      "same_game_baseline_v04_mae":12.5,
                      "same_game_baseline_v04_games":99,
                      "same_game_v04_pregame_source_hashed":True})
        r=assess(*args,now=NOW)
        self.assertFalse(r["sections"]["1D_prospective_qb_validation"]["evidence_ready"])
        group["same_game_baseline_v04_games"]=100
        group["same_game_v04_pregame_source_hashed"]=False
        self.assertFalse(assess(*args,now=NOW)["sections"]["1D_prospective_qb_validation"]["evidence_ready"])
        group["same_game_v04_pregame_source_hashed"]=True
        group["same_game_baseline_v04_mae"]=10.5
        self.assertFalse(assess(*args,now=NOW)["sections"]["1D_prospective_qb_validation"]["evidence_ready"])

    def test_forged_v04_aggregate_with_bad_pairing_is_rejected(self):
        args=list(inputs())
        group=args[4]["metrics"]["qb_conditional"]
        group.update({"games":1,"same_game_baseline_v04_games":1,
             "same_game_baseline_v04_mae":12.,
             "same_game_v04_pregame_source_hashed":True})
        args[4]["v04_comparison_audit"]={
             "status":"QB_SHADOW_EARLIER_WEBSITE_V04_PAIRED_AUDIT_RESEARCH_ONLY",
             "qb_candidate_games":1,"same_game_v04_pair_count":1,
             "fully_matched_cohort":True,"predecision_source_hashed_no_hindsight":True}
        args[4]["per_game"]=[{"game_id":"123",
             "model_results":{"qb_conditional":{}},
             "v04_paired_reference":{
                 "capture_utc":"2026-11-05T16:02:00Z",
                 "qb_shadow_observed_utc":"2026-11-05T16:00:00Z",
                 "site_snapshot_sha256":"a"*64,
                 "source_hashed_before_qb_decision":True,
                 "no_hindsight_recalculation":True,
                 "market_odds_not_used":True}}]
        with self.assertRaisesRegex(ValueError,"Untrusted predecision"):
            assess(*args,now=NOW)
        args[4]["per_game"][0]["v04_paired_reference"]["capture_utc"]="2026-11-05T15:00:00Z"
        args[4]["v04_comparison_audit"]["same_game_v04_pair_count"]=0
        with self.assertRaisesRegex(ValueError,"pair count"):
            assess(*args,now=NOW)

if __name__=="__main__":unittest.main()

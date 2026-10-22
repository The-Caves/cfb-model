"""Step 3F preregistered research-readiness and fold-disjointness tests.

All example labels are synthetic fixtures and NEVER empirical predictions.
"""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.personnel_features import FEATURE_FIELDS
from scripts.personnel_validation_readiness import (
    STATUS, POLICY, ABLATION_POLICY, _check_features, _validate_folds, assess, run)

EVAL="2026-11-20T00:00:00Z"
SOURCE="https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
BASE="RETROSPECTIVE_EVALUATION_OF_CAPTURED_EVIDENCE"
VARIANTS=("profile_baseline","plus_qb_coverage","plus_availability_coverage",
          "plus_reported_availability","all_personnel")


def fixture(empty=True):
    features=[]
    labels=[]
    days=[] if empty else [
        (dt.date(2026,10,10),90),
        (dt.date(2026,10,24),20),
        (dt.date(2026,10,31),20),
        (dt.date(2026,11,7),20)]
    by_day={}
    gid=0
    for day,n in days:
        by_day[day]=[]
        kickoff=dt.datetime.combine(day,dt.time(20),dt.timezone.utc)
        capture=kickoff-dt.timedelta(hours=48)
        known=kickoff+dt.timedelta(hours=6)
        for _ in range(n):
            gid+=1
            ident=str(700000+gid)
            by_day[day].append(ident)
            features.append({
                "game_id":ident,"home":"Team A","away":"Team B",
                "kickoff_utc":kickoff.isoformat(),
                "capture_utc":capture.isoformat(),
                "record_sha256":"a"*64,
                "features":{f:0.5 for f in FEATURE_FIELDS},
                "betting_status":"PASS_UNVALIDATED"})
            labels.append({
                "evidence_status":"OBSERVED_POSTGAME_FINAL",
                "game_id":ident,"home":"Team A","away":"Team B",
                "kickoff_utc":kickoff.isoformat(),
                "home_score":20,"away_score":13,
                "outcome_known_at_utc":known.isoformat(),
                "source_url":SOURCE})
    all_games=len(features)
    folds=[]
    for day in [dt.date(2026,10,24),dt.date(2026,10,31),
                dt.date(2026,11,7)] if not empty else []:
        cutoff=dt.datetime.combine(day,dt.time(0),dt.timezone.utc)
        prior=sorted(r["game_id"] for r,l in zip(features,labels) if
            dt.datetime.fromisoformat(r["kickoff_utc"]) < cutoff and
            dt.datetime.fromisoformat(l["outcome_known_at_utc"]) < cutoff)
        target=sorted(by_day[day])
        folds.append({
            "train_before_utc":cutoff.isoformat(),
            "train_games":len(prior),"test_games":len(target),
            "train_game_ids":prior,"test_game_ids":target,
            "status":"RESEARCH_FOLD_EVALUATED",
            "models":{name:{"status":BASE,"games":len(target),
                            "su_accuracy":0.5,"margin_mae":10.0,"total_mae":12.0}
                      for name in VARIANTS}})
    q={
        "distinct_archived_game_ids":all_games,
        "eligible_observation_game_ids_asof":all_games,
        "linked_final_game_ids_total":all_games,
        "labeled_final_games_known_at_evaluation":all_games,
        "team_slots":2*all_games,
        "reviewed_qb_slots":2*all_games,
        "verified_report_slots":2*all_games,
        "matchups_both_reports_verified":all_games,
        "missing_value_denominator_game_ids":all_games,
        "missing_features_among_selected_games":{}}
    quality={
        "status":"STEP3E_AUDITED_OBSERVED_DATASET_RESEARCH_ONLY",
        "quality":q,
        "evaluation_gate":{"model_ready_for_promotion":False,
                           "model_promoted":False},
        "evaluated_at_utc":EVAL,"betting_status":"PASS_UNVALIDATED"}
    evaluation={
        "status":"OBSERVED_PERSONNEL_ABLATION_RESEARCH_ONLY",
        "betting_status":"PASS_UNVALIDATED",
        "model_promoted":False,
        "game_selection_policy":ABLATION_POLICY,
        "folds":folds,
        "aggregates":{name:({"games":60} if not empty else None)
                      for name in VARIANTS},
        "comparisons":{}}
    return quality,features,labels,evaluation


class Step3FReadinessTests(unittest.TestCase):
    def test_live_like_missing_outcomes_is_insufficient(self):
        q,f,l,e=fixture()
        out=assess(q,f,l,e)
        self.assertEqual(out["status"],STATUS)
        self.assertEqual(out["valid_paired_game_ids"],0)
        self.assertIsNone(out["missingness"]["verified_starting_qb_slot_fraction"])
        self.assertFalse(out["observed_personnel_research_comparison_ready"])
        self.assertFalse(out["model_promoted"])
        self.assertFalse(out["model_ready_for_promotion"])
        self.assertEqual(out["betting_status"],"PASS_UNVALIDATED")
        self.assertIn("at_least_60_matched_heldout_games",out["blocking_reasons"])

    def test_synthetic_many_folds_only_unlocks_research_diagnostics(self):
        q,f,l,e=fixture(False)
        out=assess(q,f,l,e)
        self.assertEqual(out["valid_paired_game_ids"],150)
        self.assertEqual(out["folds"]["evaluated_folds"],3)
        self.assertEqual(out["folds"]["heldout_games"],60)
        self.assertTrue(out["observed_personnel_research_comparison_ready"])
        self.assertTrue(out["checks"]["at_least_60_matched_heldout_games"])
        self.assertFalse(out["checks"]["independent_historical_pbp_publication_verified"])
        self.assertFalse(out["validated_prediction_improvement"])
        self.assertFalse(out["model_ready_for_promotion"])

    def test_forged_fold_membership_rejected(self):
        q,f,l,e=fixture(False)
        e["folds"][0]["test_game_ids"][-1]="999999"
        with self.assertRaisesRegex(ValueError,"membership"):
            assess(q,f,l,e)

    def test_training_game_with_outcome_not_yet_known_rejected(self):
        q,f,l,e=fixture(False)
        l[0]["outcome_known_at_utc"]="2026-11-09T02:00:00Z"
        with self.assertRaisesRegex(ValueError,"membership"):
            assess(q,f,l,e)

    def test_duplicate_heldout_game_in_multiple_folds_rejected(self):
        q,f,l,e=fixture(False)
        e["folds"][1]["test_game_ids"]=e["folds"][0]["test_game_ids"].copy()
        with self.assertRaisesRegex(ValueError,"membership"):
            assess(q,f,l,e)

    def test_missing_explicit_fold_game_ids_rejected(self):
        q,f,l,e=fixture(False)
        del e["folds"][0]["train_game_ids"]
        with self.assertRaisesRegex(ValueError,"game IDs"):
            assess(q,f,l,e)

    def test_incorrect_variant_test_sample_rejected(self):
        q,f,l,e=fixture(False)
        e["folds"][0]["models"]["all_personnel"]["games"]=19
        with self.assertRaisesRegex(ValueError,"Unequal"):
            assess(q,f,l,e)

    def test_low_qb_report_coverage_is_explicit_blocker(self):
        q,f,l,e=fixture(False)
        q["quality"]["reviewed_qb_slots"]=0
        q["quality"]["matchups_both_reports_verified"]=10
        out=assess(q,f,l,e)
        self.assertFalse(out["observed_personnel_research_comparison_ready"])
        self.assertIn("at_least_25pct_qb_slots_reviewed",out["blocking_reasons"])
        self.assertIn("at_least_60pct_two_team_reports_verified",out["blocking_reasons"])

    def test_missing_cells_gate_only_diagnostics(self):
        q,f,l,e=fixture(False)
        # Each feature appears null in 90 of 150 selected game profiles.
        q["quality"]["missing_features_among_selected_games"]={
            name:90 for name in FEATURE_FIELDS}
        out=assess(q,f,l,e)
        self.assertFalse(out["checks"]["at_most_50pct_missing_feature_cells"])
        self.assertFalse(out["observed_personnel_research_comparison_ready"])

    def test_future_or_duplicate_label_rejected(self):
        q,f,l,e=fixture(False)
        l[0]["outcome_known_at_utc"]="2026-12-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"unavailable"):
            assess(q,f,l,e)
        q,f,l,e=fixture(False)
        l[1]["game_id"]=l[0]["game_id"]
        with self.assertRaisesRegex(ValueError,"duplicate"):
            assess(q,f,l,e)

    def test_postgame_score_in_pregame_record_rejected(self):
        q,f,l,e=fixture(False)
        f[0]["features"]["home_score"]=25
        with self.assertRaises(ValueError):
            assess(q,f,l,e)

    def test_fixed_policy_and_source_integrity_rejected_when_tampered(self):
        q,f,l,e=fixture(False)
        e["game_selection_policy"]="WHATEVER_WON"
        with self.assertRaisesRegex(ValueError,"policy"):
            assess(q,f,l,e)
        q,f,l,e=fixture(False)
        l[0]["source_url"]="https://unknown.com"
        with self.assertRaisesRegex(ValueError,"scoreboard source"):
            assess(q,f,l,e)

    def test_write_is_exclusive(self):
        q,f,l,e=fixture()
        with tempfile.TemporaryDirectory() as root:
            directory=Path(root)
            for fn,obj in (("quality.json",q),
                           ("pregame_features.json",f),
                           ("postgame_labels.json",l),
                           ("personnel_ablation.json",e)):
                (directory/fn).write_text(json.dumps(obj))
            path=directory/"result.json"
            a=run(str(directory),str(path))
            self.assertFalse(a["model_promoted"])
            with self.assertRaises(FileExistsError):
                run(str(directory),str(path))


if __name__=="__main__":
    unittest.main()

import copy
import datetime as dt
import unittest
from scripts.qb_trainability_audit import assess,STATUS,REQUIRED_FEATURES

def example():
    qa={"status":"STEP3E_AUDITED_OBSERVED_DATASET_RESEARCH_ONLY",
        "betting_status":"PASS_UNVALIDATED","evaluated_at_utc":"2026-10-26T12:00:00Z",
        "quality":{"team_slots":2,"eligible_observation_game_ids_asof":1,
            "reviewed_qb_slots":0,"matchups_both_reports_verified":0,
            "labeled_final_games_known_at_evaluation":1}}
    vals={name:None for name in REQUIRED_FEATURES}
    vals.update({"home_qb_reviewed":0,"away_qb_reviewed":0,
        "home_report_verified":0,"away_report_verified":0})
    feats=[{"game_id":"1","home":"Home","away":"Away",
        "kickoff_utc":"2026-10-24T19:00:00Z",
        "capture_utc":"2026-10-23T16:00:00Z",
        "features":vals,"betting_status":"PASS_UNVALIDATED"}]
    labels=[{"game_id":"1","home":"Home","away":"Away",
        "kickoff_utc":"2026-10-24T19:00:00Z",
        "outcome_known_at_utc":"2026-10-25T01:00:00Z",
        "home_score":27,"away_score":17,
        "evidence_status":"OBSERVED_POSTGAME_FINAL"}]
    return qa,feats,labels

class QBTrainingGateTests(unittest.TestCase):
    def test_realistic_zero_coverage_stays_blocked(self):
        r=assess(*example())
        self.assertEqual(r["status"],STATUS)
        self.assertEqual(r["summary"]["reviewed_starters_in_policy_slots"],0)
        self.assertFalse(r["ready_to_train_injury_qb_model"])
        self.assertFalse(r["trained_qb_replacement_value"])
        self.assertEqual(r["summary"]["games_with_verified_finals"],1)
    def test_reviewed_boolean_not_identity_or_replacement(self):
        q,f,l=example()
        q["quality"]["reviewed_qb_slots"]=2
        f[0]["features"]["home_qb_reviewed"]=1
        f[0]["features"]["away_qb_reviewed"]=1
        result=assess(q,f,l)
        self.assertEqual(result["summary"]["games_both_qbs_reviewed"],1)
        self.assertEqual(result["summary"]["named_starter_matchups_in_step3e"],0)
        self.assertEqual(result["summary"]["independently_labeled_in_game_qb_replacements"],0)
        self.assertFalse(result["ready_to_train_injury_qb_model"])
    def test_undocumented_injury_differential_fails(self):
        q,f,l=example();f[0]["features"]["availability_qb_out_diff"]=1
        with self.assertRaises(ValueError):assess(q,f,l)
    def test_postkickoff_capture_fails(self):
        q,f,l=example();f[0]["capture_utc"]="2026-10-24T20:00:00Z"
        with self.assertRaises(ValueError):assess(q,f,l)
    def test_final_before_kickoff_fails(self):
        q,f,l=example();l[0]["outcome_known_at_utc"]="2026-10-24T17:00:00Z"
        with self.assertRaises(ValueError):assess(q,f,l)
    def test_identity_or_duplicate_fails(self):
        q,f,l=example();l[0]["home"]="Different"
        with self.assertRaises(ValueError):assess(q,f,l)
        q,f,l=example();f.append(copy.deepcopy(f[0]));l.append(copy.deepcopy(l[0]))
        with self.assertRaises(ValueError):assess(q,f,l)
    def test_unverified_starter_boolean_fails(self):
        q,f,l=example();f[0]["features"]["home_qb_reviewed"]=1
        with self.assertRaises(ValueError):assess(q,f,l)
    def test_score_in_pregame_feature_fails(self):
        q,f,l=example();f[0]["features"]["home_score"]=27
        with self.assertRaises(ValueError):assess(q,f,l)
    def test_positive_reports_do_not_equal_verified_qb1(self):
        q,f,l=example()
        q["quality"]["matchups_both_reports_verified"]=1
        f[0]["features"]["home_report_verified"]=1
        f[0]["features"]["away_report_verified"]=1
        f[0]["features"]["availability_qb_out_diff"]=1
        r=assess(q,f,l)
        self.assertEqual(r["summary"]["games_with_verified_qb_out_differential"],1)
        self.assertEqual(r["summary"]["games_both_availability_reports_reviewed"],1)
        self.assertEqual(r["summary"]["reviewed_starters_in_policy_slots"],0)
        self.assertFalse(r["ready_to_train_injury_qb_model"])
if __name__=="__main__":unittest.main()

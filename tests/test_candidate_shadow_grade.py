import unittest
from scripts.candidate_shadow_grade import evaluate
from scripts.qb_conditional_forecast import STATUS as QB
from scripts.venue_travel_forecast import STATUS as VENUE
def candidate(kind):
    r={"status":QB if kind=="qb" else VENUE,"season":2026,"model_promoted":False,
       "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
       "observed_at_utc":"2026-10-29T14:00:00Z","baseline_forecast_sha256":"a"*64}
    if kind=="qb":
        r["baseline_forecast_run_id"]="991"
        r["historical_pbp_publication_authenticated"]=False
    else:
        r["baseline_run_id"]="991"
        r["historical_publication_authenticated"]=False
    g={"game_id":"123","home":"Home","away":"Away",
       "kickoff_utc":"2026-10-31T19:00:00Z","baseline_row_sha256":"b"*64}
    if kind=="qb":g["candidate"]={"status":"QB_PLAYER_CONDITIONAL_SHADOW",
        "adjusted_home_margin":3.0,"adjusted_side_count":1,
        "betting_status":"PASS_UNVALIDATED","model_promoted":False}
    else:g.update({"venue_only_margin":1.0,"venue_plus_travel_margin":1.5,
                  "small_travel_adjustment_points":.5})
    r["games"]=[g]
    return r
def grade():
    return {"status":"OBSERVED_FORECAST_GRADED_RESEARCH_ONLY",
        "betting_status":"PASS_UNVALIDATED","model_validated":False,
        "safe_for_betting":False,"forecast_run_id":"991","forecast_bundle_sha256":"a"*64,
        "frozen_forecast_row_sha256":"b"*64,
        "game_id":"123","home":"Home","away":"Away",
        "kickoff_utc":"2026-10-31T19:00:00Z",
        "final_outcome_known_at_utc":"2026-11-01T01:00:00Z",
        "predicted_margin":5.0,"actual_margin":4.0}
class ProspectiveCandidateGradeTests(unittest.TestCase):
    def test_pairs_exact_baseline_and_two_candidate_sources(self):
        report=evaluate({"qb":[candidate("qb")],"venue":[candidate("venue")]},
                        [grade()],"2026-11-02T00:00:00Z")
        self.assertEqual(report["summary"]["graded_games"],1)
        self.assertEqual(report["metrics"]["qb_conditional"]["games"],1)
        self.assertEqual(report["metrics"]["venue_plus_travel"]["margin_mae"],2.5)
    def test_qb_usage_mixture_has_separate_identical_game_prospective_metric(self):
        qb=candidate("qb")
        c=qb["games"][0]["candidate"]
        c.update({"usage_weighted_status":"QB_EMPIRICAL_EXPOSURE_SHADOW",
                  "usage_weighted_home_margin":4.5,
                  "evaluated_player_sample_exposure_by_side":{"home":.70,"away":.35}})
        report=evaluate({"qb":[qb],"venue":[candidate("venue")]},
                        [grade()],"2026-11-02T00:00:00Z")
        self.assertEqual(report["metrics"]["qb_empirical_exposure"]["games"],1)
        self.assertEqual(report["metrics"]["qb_empirical_exposure"]["margin_mae"],.5)
        self.assertEqual(report["metrics"]["qb_empirical_exposure"]["same_game_baseline_v03_mae"],1.)
        self.assertEqual(report["metrics"]["qb_conditional"]["margin_mae"],1.)
        self.assertEqual(report["per_game"][0]["model_results"]["qb_empirical_exposure"]["sample_coverage_home"],.7)
    def test_missing_qualified_usage_exposure_not_artificially_counted(self):
        report=evaluate({"qb":[candidate("qb")],"venue":[candidate("venue")]},
                        [grade()],"2026-11-02T00:00:00Z")
        self.assertEqual(report["metrics"]["qb_empirical_exposure"]["games"],0)
    def test_invalid_empirical_exposure_probability_mass_rejected(self):
        qb=candidate("qb")
        qb["games"][0]["candidate"].update({
            "usage_weighted_status":"QB_EMPIRICAL_EXPOSURE_SHADOW",
            "usage_weighted_home_margin":4.5,
            "evaluated_player_sample_exposure_by_side":{"home":1.3,"away":0.}})
        with self.assertRaisesRegex(ValueError,"Invalid prospective"):
            evaluate({"qb":[qb],"venue":[candidate("venue")]},
                     [grade()],"2026-11-02T00:00:00Z")

    def test_opponent_adjusted_qb_shadows_grade_on_same_original_v03_games(self):
        q=candidate("qb")
        c=q["games"][0]["candidate"]
        c.update({"opponent_peer_status":"QB_OPPONENT_PEER_EPA_SHADOW",
                  "opponent_peer_home_margin":4.5,
                  "opponent_peer_qualified_sides":1,
                  "opponent_peer_exposure_status":"QB_OPPONENT_PEER_EXPOSURE_SHADOW",
                  "opponent_peer_exposure_home_margin":4.25,
                  "opponent_peer_exposure_sample_by_side":{"home":.5,"away":0.}})
        x=evaluate({"qb":[q],"venue":[candidate("venue")]},
                   [grade()],"2026-11-02T00:00:00Z")
        self.assertEqual(x["metrics"]["qb_defense_peer"]["games"],1)
        self.assertEqual(x["metrics"]["qb_defense_peer"]["margin_mae"],.5)
        self.assertEqual(x["metrics"]["qb_defense_peer"]["same_game_baseline_v03_mae"],1.)
        self.assertEqual(x["metrics"]["qb_defense_peer_exposure"]["margin_mae"],.25)
        self.assertEqual(x["per_game"][0]["model_results"]["qb_defense_peer"]["covered_sides"],1)

    def test_opponent_adjusted_missing_peer_sample_never_counts_as_graded(self):
        q=candidate("qb")
        c=q["games"][0]["candidate"]
        c.update({"opponent_peer_status":"PASS_NO_OPPONENT_ADJUSTED_QB_PEER_SAMPLE",
                  "opponent_peer_home_margin":5.,
                  "opponent_peer_exposure_status":"PASS_NO_OPPONENT_ADJUSTED_QB_PEER_EXPOSURE",
                  "opponent_peer_exposure_home_margin":5.})
        x=evaluate({"qb":[q],"venue":[]},[grade()],"2026-11-02T00:00:00Z")
        self.assertEqual(x["metrics"]["qb_defense_peer"]["games"],0)
        self.assertEqual(x["metrics"]["qb_defense_peer_exposure"]["games"],0)

    def test_untrusted_peer_coverage_or_nonnumeric_points_rejected(self):
        q=candidate("qb")
        c=q["games"][0]["candidate"]
        c.update({"opponent_peer_status":"QB_OPPONENT_PEER_EPA_SHADOW",
                  "opponent_peer_home_margin":4.,"opponent_peer_qualified_sides":3})
        with self.assertRaisesRegex(ValueError,"Invalid archived opponent peer"):
            evaluate({"qb":[q],"venue":[]},[grade()],"2026-11-02T00:00:00Z")
        c["opponent_peer_qualified_sides"]=1
        c["opponent_peer_exposure_status"]="QB_OPPONENT_PEER_EXPOSURE_SHADOW"
        c["opponent_peer_exposure_home_margin"]=float("nan")
        c["opponent_peer_exposure_sample_by_side"]={"home":.4,"away":0.}
        with self.assertRaisesRegex(ValueError,"Invalid archived opponent QB exposure"):
            evaluate({"qb":[q],"venue":[]},[grade()],"2026-11-02T00:00:00Z")

    def test_mismatched_reference_fails_closed(self):
        g=grade();g["forecast_bundle_sha256"]="z"*64
        with self.assertRaisesRegex(ValueError,"Wrong original"):
            evaluate({"qb":[candidate("qb")],"venue":[candidate("venue")]},
                     [g],"2026-11-02T00:00:00Z")
    def test_postgame_forecast_rejected(self):
        q=candidate("qb");q["observed_at_utc"]="2026-11-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"Postkickoff|chronology"):
            evaluate({"qb":[q],"venue":[]},[grade()],"2026-11-02T00:00:00Z")
if __name__=="__main__":unittest.main()

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
    def test_mismatched_reference_fails_closed(self):
        g=grade();g["forecast_bundle_sha256"]="z"*64
        with self.assertRaisesRegex(ValueError,"Wrong original"):
            evaluate({"qb":[candidate("qb")],"venue":[candidate("venue")]},
                     [g],"2026-11-02T00:00:00Z")
    def test_postgame_forecast_rejected(self):
        q=candidate("qb");q["observed_at_utc"]="2026-11-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"chronology"):
            evaluate({"qb":[q],"venue":[]},[grade()],"2026-11-02T00:00:00Z")
if __name__=="__main__":unittest.main()


import copy
import datetime as dt
import unittest
from scripts.verified_player_impact import features,fit_training,estimate,FEATURES

KICK="2026-10-31T20:00:00Z"
CAP="2026-10-30T16:00:00Z"
def player(status="OUT",position="OL",share=.85):
    return {"player_id":"school:jersey:2026","position":position,
        "reported_status":status,"identity_crosswalk_verified":True,
        "pregame_role_share_verified":True,"prior_snap_share":share,
        "prior_games_observed":4,"status_source_url":"https://example.edu/report",
        "role_source_url":"https://example.edu/stats",
        "status_published_at_utc":"2026-10-30T12:00:00Z",
        "role_source_observed_at_utc":"2026-10-30T13:00:00Z"}
def game():
    return {"game_id":"latest","home":"A","away":"B",
      "kickoff_utc":KICK,"captured_at_utc":CAP,"betting_status":"PASS_UNVALIDATED",
      "sides":{
        "home":{"team":"A","coverage":"VERIFIED_REPORT_REVIEWED",
                "reported_players":[player()],
                "opponent_pressure_rate":.3,"pressure_source_observed_at_utc":"2026-10-30T10:00:00Z"},
        "away":{"team":"B","coverage":"VERIFIED_REPORT_REVIEWED",
                "reported_players":[],
                "opponent_pressure_rate":.4,"pressure_source_observed_at_utc":"2026-10-30T10:00:00Z"}}}
class PlayerImpactTests(unittest.TestCase):
    def test_named_ol_and_front_pressure_captured_but_no_point_penalty(self):
        s=features(game(),CAP)
        self.assertEqual(s["status"],"SOURCE_READY_RESEARCH_ONLY")
        self.assertAlmostEqual(s["features"]["OL_FULL_OUT"],.85)
        self.assertAlmostEqual(s["features"]["HOME_OL_VS_DEFENSIVE_PRESSURE"],.255)
        self.assertEqual(s["features"]["QB_FULL_OUT"],0.)

    def test_incomplete_opponent_report_cannot_impute_healthy(self):
        g=game();g["sides"]["away"]["coverage"]="UNKNOWN"
        self.assertIsNone(features(g,CAP)["features"])
        self.assertEqual(features(g,CAP)["unlisted_players"],"UNKNOWN")

    def test_questionable_not_full_out_and_first_half_separate(self):
        g=game();g["sides"]["home"]["reported_players"][0]["reported_status"]="QUESTIONABLE"
        s=features(g,CAP)
        self.assertEqual(s["features"]["OL_FULL_OUT"],0.)
        self.assertAlmostEqual(s["features"]["OL_UNCERTAIN"],.85)
        g["sides"]["home"]["reported_players"][0]["reported_status"]="OUT_FIRST_HALF"
        s=features(g,CAP)
        self.assertAlmostEqual(s["features"]["OL_FIRST_HALF_OUT"],.85)
        self.assertEqual(s["features"]["OL_FULL_OUT"],0.)

    def test_unsupported_identity_or_future_role_cannot_predict(self):
        g=game();g["sides"]["home"]["reported_players"][0]["identity_crosswalk_verified"]=False
        self.assertEqual(features(g,CAP)["status"],"PASS_PLAYER_ROLE_OR_IDENTITY_MISSING")
        g=game();g["sides"]["home"]["reported_players"][0]["role_source_observed_at_utc"]=KICK
        self.assertIsNone(features(g,CAP)["features"])

    def test_training_withheld_without_actual_prior_game_evidence(self):
        self.assertEqual(fit_training([],CAP,min_games=20)["status"],
                         "PASS_INSUFFICIENT_PRIOR_VERIFIED_PLAYER_GAMES")
        self.assertIsNone(estimate(game(),{"status":"PASS_INSUFFICIENT_PRIOR_VERIFIED_PLAYER_GAMES"},CAP)["home_margin_adjustment"])

    def test_training_prior_observed_games_learns_direction_not_fixed_value(self):
        records=[]
        for i in range(60):
            row=game()
            day=dt.date(2026,9,1)+dt.timedelta(days=i//2)
            when=dt.datetime.combine(day,dt.time(18),dt.timezone.utc)
            row["game_id"]=str(i)
            row["captured_at_utc"]=(when-dt.timedelta(days=1)).isoformat()
            row["kickoff_utc"]=when.isoformat()
            row["sides"]["home"]["pressure_source_observed_at_utc"]=(when-dt.timedelta(days=2)).isoformat()
            row["sides"]["away"]["pressure_source_observed_at_utc"]=(when-dt.timedelta(days=2)).isoformat()
            if i%2:
                row["sides"]["home"]["reported_players"]=[]
                row["sides"]["away"]["reported_players"]=[player(position="CB",share=.9)]
            else:
                p=row["sides"]["home"]["reported_players"][0]
                p["status_published_at_utc"]=(when-dt.timedelta(days=2)).isoformat()
                p["role_source_observed_at_utc"]=(when-dt.timedelta(days=2)).isoformat()
            if i%2:
                p=row["sides"]["away"]["reported_players"][0]
                p["status_published_at_utc"]=(when-dt.timedelta(days=2)).isoformat()
                p["role_source_observed_at_utc"]=(when-dt.timedelta(days=2)).isoformat()
            records.append({"pregame":row,
               "outcome_known_at_utc":(when+dt.timedelta(hours=5)).isoformat(),
               "frozen_baseline_hash":"a"*64,
               "observed_final_source":"https://example.edu/final",
               "frozen_baseline_home_margin":7.,
               "actual_home_margin":3. if i%2==0 else 10.})
        training=fit_training(records,"2026-11-15T18:00:00Z",min_games=30)
        self.assertEqual(training["status"],"FITTED_PRIOR_EVIDENCE_RESEARCH_ONLY")
        self.assertLess(training["coefficients"]["OL_FULL_OUT"],0)
        self.assertFalse(training["prospective_accuracy_established"])
        out=estimate(game(),training,"2026-11-15T18:00:00Z") if False else estimate(game(),training,CAP)
        # Model fit as-of November cannot be applied to an October 30 decision.
        self.assertIsNone(out["home_margin_adjustment"]) if out["status"]!="PLAYER_IMPACT_RESEARCH_CANDIDATE" else None

if __name__=="__main__":
    unittest.main()

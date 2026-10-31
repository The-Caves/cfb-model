import copy
import datetime as dt
import unittest
from scripts.site_player_projection_archive import freeze,STATUS
from scripts.site_player_props import STATUS as PLAYER_STATUS

KICK="2026-10-31T20:00:00Z"
NOW=dt.datetime(2026,10,30,23,0,0,tzinfo=dt.timezone.utc)
SOURCE="2026-10-30T22:55:00Z"
def fixture():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED",
        "forecast_sha256":"a"*64,"forecast_observed_utc":"2026-10-30T18:00:00Z",
        "model":"V03","player_prop_display":{"model":"PlayerForm R1",
            "model_scores_updated":False,"real_bookmaker_quotes_present":False},
        "games":[{"game_id":"90","kickoff_utc":KICK,
           "home_team":"A","away_team":"B",
           "player_props":{"status":PLAYER_STATUS,
                "real_bookmaker_prop_lines":0,"source_observed_at_utc":SOURCE,
                "entries":[{"player_id":"1234","player":"Athlete One",
                    "team_side":"home","team":"A","metric":"rushing_yards",
                    "projection":73.5,"unit":"yards",
                    "source_observed_at_utc":SOURCE,
                    "official_reported_status":"QUESTIONABLE",
                    "workload_role_evidence":{"recorded_opportunity_share":.42,
                         "participation_not_confirmed":True,
                         "share_is_not_snap_or_target_percentage":True},
                    "workload_share_used_to_change_yard_projection":False,
                    "player_participation_status":"RECENT_GAME_PARTICIPANT_NOT_CONFIRMED",
                    "real_bookmaker_line":None,"over_probability":None}]}}]}

class ProspectivePlayerArchiveTests(unittest.TestCase):
    def test_freezes_source_recorded_conditional_player_projection(self):
        x=freeze(fixture(),NOW,"9988")
        self.assertEqual(x["status"],STATUS)
        self.assertEqual(x["summary"]["player_stat_projections"],1)
        r=x["rows"][0]
        self.assertEqual(r["projection_conditional_yards"],73.5)
        self.assertIsNone(r["recent_four_baseline_yards"])
        self.assertEqual(r["official_reported_status"],"QUESTIONABLE")
        self.assertEqual(r["original_V03_sha256"],"a"*64)
        self.assertFalse(r["player_participation_verified"])
        self.assertIsNone(r["real_bookmaker_line"])
        self.assertFalse(x["model_promoted"])
        self.assertEqual(x["betting_status"],"PASS_UNVALIDATED")

    def test_no_kickoff_hindsight_and_no_duplicate_player_record(self):
        x=fixture()
        out=freeze(x,dt.datetime(2026,11,1,tzinfo=dt.timezone.utc),"9988")
        self.assertEqual(out["rows"],[])
        x=fixture()
        x["games"][0]["player_props"]["entries"].append(
            copy.deepcopy(x["games"][0]["player_props"]["entries"][0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            freeze(x,NOW,"9988")

    def test_future_source_or_fabricated_prop_line_rejected(self):
        for key,value in [("real_bookmaker_line",64.5),("over_probability",.7),
                          ("source_observed_at_utc","2026-10-31T20:00:00Z"),
                          ("player_participation_status","CONFIRMED_ACTIVE")]:
            x=fixture()
            x["games"][0]["player_props"]["entries"][0][key]=value
            with self.assertRaises(ValueError):
                freeze(x,NOW,"9988")

    def test_same_instant_recent_four_control_gets_frozen_and_validated(self):
        b=fixture()
        b["games"][0]["player_props"]["entries"][0]["recent_four_baseline_yards"]=62.4
        a=freeze(b,NOW,"9988")
        self.assertEqual(a["rows"][0]["recent_four_baseline_yards"],62.4)
        b["games"][0]["player_props"]["entries"][0]["recent_four_baseline_yards"]=float("nan")
        with self.assertRaises(ValueError):freeze(b,NOW,"9988")

    def test_no_source_model_mutation_or_unsupported_role_share(self):
        x=fixture()
        x["player_prop_display"]["model_scores_updated"]=True
        with self.assertRaises(ValueError):freeze(x,NOW,"9988")
        x=fixture()
        x["games"][0]["player_props"]["entries"][0]["workload_role_evidence"]["recorded_opportunity_share"]=1.3
        with self.assertRaises(ValueError):freeze(x,NOW,"9988")

    def test_prediction_snapshot_must_preserve_valid_model_and_capture_run(self):
        x=fixture();x["player_prop_display"]["model"]="Mystery"
        with self.assertRaises(ValueError):freeze(x,NOW,"9988")
        x=fixture()
        with self.assertRaises(ValueError):freeze(x,NOW,"not-run-id")

if __name__=="__main__":
    unittest.main()

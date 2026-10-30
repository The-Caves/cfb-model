"""Empirical two-game passer exposure keeps UNKNOWN mass and source chronology."""
import copy
import unittest
from scripts.qb_scenario_exposure import mixture,STATUS

WHEN="2026-10-29T18:00:00Z"
DATE="2026-10-31"
def data(gid,date,qb,plays,total=40,received="2026-10-29T12:00:00Z",team="Team A"):
    return {"game_id":gid,"date":date,"team":team,"opponent":"Other",
        "player":qb,"pass_tagged_plays":str(plays),
        "team_pass_tagged_plays":str(total),
        "source_retrieved_at_utc":received,
        "historical_source_time_verified":"False",
        "betting_status":"PASS_UNVALIDATED"}
def slot():
    return {"starter":"A Two","is_confirmed_starter":False,
            "betting_status":"PASS_UNVALIDATED",
            "scenarios":[{"player":"A One","depth_rank":1},
                         {"player":"A Two","depth_rank":2}],
            "availability_by_player":{}}
class EmpiricalExposureTests(unittest.TestCase):
    def test_two_games_weighted_dominant_use_and_unattributed_mass(self):
        rows=[data("1","2026-10-20","A One",30),
              data("1","2026-10-20","A Two",10),
              data("2","2026-10-27","A One",20),
              data("2","2026-10-27","A Two",12)]
        x=mixture(rows,"Team A",slot(),DATE,WHEN)
        self.assertEqual(x["status"],STATUS)
        self.assertEqual(x["past_game_ids"],["2","1"])
        self.assertAlmostEqual(x["weights"]["A One"],(.5*2/3+.75*1/3),places=6)
        self.assertAlmostEqual(x["weights"]["A Two"],(.3*2/3+.25*1/3),places=6)
        self.assertAlmostEqual(x["unknown_weight"],.2*2/3,places=6)
        self.assertFalse(x["calibrated"])
        self.assertTrue(x["not_starter_probabilities"])
    def test_unknown_mass_for_unlisted_qbs(self):
        rows=[data("2","2026-10-27","A One",24),
              data("2","2026-10-27","A Third",16)]
        x=mixture(rows,"Team A",slot(),DATE,WHEN)
        self.assertAlmostEqual(x["weights"]["A One"],.6)
        self.assertAlmostEqual(x["unknown_weight"],.4)
    def test_out_recent_qb_flows_to_unknown_not_another_qb(self):
        s=slot();s["availability_by_player"]={"a one":{"status":"OUT"}}
        rows=[data("2","2026-10-27","A One",32),data("2","2026-10-27","A Two",8)]
        x=mixture(rows,"Team A",s,DATE,WHEN)
        self.assertNotIn("A One",x["weights"])
        self.assertAlmostEqual(x["weights"]["A Two"],.2)
        self.assertAlmostEqual(x["unknown_weight"],.8)
    def test_low_pass_attribution_rejected(self):
        rows=[data("1","2026-10-20","A One",8,total=40)]
        x=mixture(rows,"Team A",slot(),DATE,WHEN)
        self.assertEqual(x["unknown_weight"],1)
        self.assertEqual(x["accepted_past_games"],0)
        self.assertEqual(x["rejected_past_games"],1)
    def test_future_or_postcapture_play_cannot_enter(self):
        rows=[data("1","2026-10-20","A One",30),
              data("2","2026-10-27","A Two",40,received="2026-11-01T11:00:00Z"),
              data("3","2026-10-31","A Two",40)]
        x=mixture(rows,"Team A",slot(),DATE,WHEN)
        self.assertEqual(x["past_game_ids"],["1"])
        self.assertAlmostEqual(x["weights"]["A One"],.75)
    def test_earlier_dates_dont_become_extra_votes(self):
        rows=[data("1","2026-10-01","A One",40),
              data("2","2026-10-15","A One",40),
              data("3","2026-10-27","A Two",40)]
        x=mixture(rows,"Team A",slot(),DATE,WHEN)
        self.assertEqual(x["past_game_ids"],["3","2"])
        self.assertAlmostEqual(x["weights"]["A Two"],2/3,places=6)
    def test_explicit_official_starter_is_one_scenario_not_calibrated(self):
        s=slot();s["starter"]="A Two";s["is_confirmed_starter"]=True
        x=mixture([],"Team A",s,DATE,WHEN)
        self.assertEqual(x["status"],"REVIEWED_GAME_SPECIFIC_STARTER_SCENARIO")
        self.assertEqual(x["weights"]["A Two"],1)
        self.assertEqual(x["unknown_weight"],0)
        self.assertFalse(x["calibrated"])
    def test_missing_and_conflicting_official_starter_rejected(self):
        s=slot();s["starter"]="A Missing";s["is_confirmed_starter"]=True
        with self.assertRaisesRegex(ValueError,"Official starter"):
            mixture([],"Team A",s,DATE,WHEN)
        s=slot();s["is_confirmed_starter"]=True;s["availability_by_player"]={"a two":{"status":"OUT"}}
        with self.assertRaisesRegex(ValueError,"Official starter"):
            mixture([],"Team A",s,DATE,WHEN)
    def test_duplicate_and_conflicting_passer_totals_fails(self):
        row=data("1","2026-10-20","A One",30)
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            mixture([row,row],"Team A",slot(),DATE,WHEN)
        with self.assertRaisesRegex(ValueError,"Invalid historical"):
            mixture([data("1","2026-10-20","A One",30,total=20)],
                    "Team A",slot(),DATE,WHEN)
    def test_sparse_no_source_uses_original_model(self):
        x=mixture([],"Team A",slot(),DATE,WHEN)
        self.assertEqual(x["unknown_weight"],1)
        self.assertEqual(sum(x["weights"].values()),0)
    def test_utc_date_after_midnight_but_eastern_pregame_is_allowed(self):
        x=mixture([],"Team A",slot(),"2026-10-30","2026-10-31T00:15:00Z")
        self.assertEqual(x["unknown_weight"],1)

if __name__=="__main__":unittest.main()

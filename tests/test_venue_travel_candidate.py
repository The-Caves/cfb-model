import datetime as dt
import unittest
from scripts.venue_travel_candidate import (
    fit,predict,compare,travel_inputs,STATUS,PRIOR_HOME_POINTS,MIN_GAMES)

def samples(n=150):
    clubs=[f"Team-{i}" for i in range(16)]
    start=dt.date(2026,8,1)
    out=[]
    for i in range(n):
        home=clubs[(i*3)%16]
        away=clubs[(i*5+1)%16]
        if home==away:away=clubs[(i*5+2)%16]
        neutral=(i%9==0)
        out.append({"game_id":str(i),"date":(start+dt.timedelta(days=i//8)).isoformat(),
            "kickoff_utc":(start+dt.timedelta(days=i//8)).isoformat()+"T16:00:00Z",
            "home":home,"away":away,"neutral":neutral,
            "home_score":30+(i%5)+int(not neutral)*2,"away_score":27+(i%5)})
    return out

def venue(home="A",away="B",neutral=False):
    return {"game_id":"x","home":home,"away":away,"neutral":neutral,
        "venue_location_quality":"CITY_CENTROID_NOT_STADIUM_COORDINATE",
        "travel_source":"INFERRED_PRIOR_HOME_CITY_TO_GEOCODED_VENUE_CITY",
        "home_approx_straight_line_miles":0.,
        "away_approx_straight_line_miles":2500.,
        "home_timezone_shift_hours":0.,
        "away_timezone_shift_hours":3.,
        "home_days_since_last_game":7.,"away_days_since_last_game":7.,
        "away_body_clock_kickoff_hour":9.}

class VenueTravelTests(unittest.TestCase):
    def test_fit_neutral_rating_and_venue_have_separate_parts(self):
        rows=samples()
        trained=fit(rows,"2026-09-20")
        self.assertEqual(trained["status"],STATUS)
        self.assertGreaterEqual(trained["home_field_points"],0)
        self.assertLessEqual(trained["home_field_points"],4.5)
        h=predict(trained,{"home":"Team-0","away":"Team-1","neutral":False})
        n=predict(trained,{"home":"Team-0","away":"Team-1","neutral":True})
        self.assertAlmostEqual(h["predicted_home_margin"]-n["predicted_home_margin"],
                               trained["home_field_points"],places=4)
        self.assertEqual(n["home_field_points"],0)
        self.assertEqual(h["travel_adjustment"],0)

    def test_missing_team_and_venue_flag_cannot_claim_points(self):
        trained=fit(samples(),"2026-09-20")
        self.assertIsNone(predict(trained,{"home":"Unknown","away":"Team-1","neutral":False}))
        self.assertIsNone(predict(trained,{"home":"Team-1","away":"Team-2","neutral":None}))
        self.assertIsNone(travel_inputs({"venue_location_quality":"UNKNOWN"}))

    def test_eastward_body_clock_kickoff_and_travel_shape(self):
        trip=travel_inputs(venue())
        self.assertEqual(trip["away_minus_home_travel_1000mi"],2.5)
        self.assertEqual(trip["away_eastward_hours"],3.)
        self.assertEqual(trip["away_body_clock_early_hours"],3.)
        west=venue();west["away_timezone_shift_hours"]=-3.
        self.assertEqual(travel_inputs(west)["away_eastward_hours"],0.)
        self.assertEqual(travel_inputs(west)["away_minus_home_abs_shift"],3.)

    def test_missing_distance_or_clock_is_unknown_not_zero(self):
        trip=venue();trip["away_body_clock_kickoff_hour"]=None
        self.assertIsNone(travel_inputs(trip))
        trip=venue();trip["travel_source"]="GUESS"
        self.assertIsNone(travel_inputs(trip))
        trip=venue();trip["away_approx_straight_line_miles"]=-1
        with self.assertRaisesRegex(ValueError,"geographic"):
            travel_inputs(trip)

    def test_no_sample_historical_travel_training_never_invents_coefficient(self):
        result=fit(samples(),"2026-09-20",travel=True)
        self.assertEqual(result["status"],"PASS_INSUFFICIENT_HISTORICAL_TRAVEL")
        self.assertEqual(result["travel_training_games"],0)

    def test_future_same_day_training_leakage_fails_closed(self):
        rows=samples()
        with self.assertRaisesRegex(ValueError,"Same-day"):
            fit(rows,"2026-08-05")
        copied=samples(96);copied[1]["game_id"]=copied[0]["game_id"]
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            fit(copied,"2026-09-20")

    def test_exact_same_game_pairing_and_no_future_fold_outcome(self):
        from scripts.venue_travel_candidate import paired_comparison
        from scripts.model_v03 import build_weekly_games
        base=samples(480)
        # All history must be in 2026 and sufficient previous games.
        report=paired_comparison(base,{},[dt.date(2026,9,26),dt.date(2026,10,3)])
        self.assertTrue(report["folds"])
        for fold in report["folds"]:
            assert set(fold["metrics"])=={"v03","recency","neutral_rating"}
            self.assertEqual(len(fold["same_game_details"]),fold["metrics"]["v03"]["games"])
            self.assertEqual(fold["metrics"]["recency"]["games"],
                             fold["metrics"]["neutral_rating"]["games"])
            self.assertTrue(all(row["date"]>=fold["cutoff"] for row in fold["same_game_details"]))
        changed=[dict(r) for r in base]
        for row in changed:
            if row["date"]>="2026-09-26":
                row["home_score"]=100
        repeat=paired_comparison(changed,{},[dt.date(2026,9,26)])
        first=report["folds"][0]
        same=repeat["folds"][0]
        original={r["game_id"]:r for r in first["same_game_details"]}
        for new in same["same_game_details"]:
            # Later days within the week can legitimately incorporate scores
            # already completed the previous day. The initial test date is
            # strictly frozen against changes to its own outcomes.
            if new["date"]!=first["cutoff"]:continue
            old=original[new["game_id"]]
            for key in ("v03","recency","neutral_rating"):
                self.assertAlmostEqual(old[key],new[key],places=4)

    def test_walk_forward_only_earlier_games_and_travel_pass(self):
        data=samples(200)
        out=compare(data,[dt.date(2026,8,18),dt.date(2026,8,25)])
        self.assertGreaterEqual(len(out["folds"]),1)
        self.assertEqual(out["model_promoted"],False)
        self.assertTrue(all(x["travel_training_status"]==
            "PASS_INSUFFICIENT_HISTORICAL_TRAVEL" for x in out["folds"]))
        self.assertTrue(all(x["models"]["venue_plus_travel"]["games"]==0 for x in out["folds"]))
if __name__=="__main__":unittest.main()

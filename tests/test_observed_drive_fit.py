import copy
import unittest

from scripts.observed_drive_fit import fit
from scripts.game_simulation_research import simulate

DECISION="2026-10-30T17:00:00Z"
KICKOFF="2026-10-31T19:00:00Z"

def make_bundle():
    games=[]
    for i in range(4):
        date=f"2026-09-{i+1:02d}"
        drives=[]
        for side,team in (("home","A"),("away","B")):
            for n in range(10):
                drives.append({"team":team,"drive_id":f"{i}-{side}-{n}",
                    "field_zone":"own_half" if n%2==0 else "midfield",
                    "points":7 if n%4==0 and team=="A" else 0,
                    "explosive":n%3==0})
        games.append({"game_id":str(i),"home":"A","away":"B",
            "kickoff_utc":date+"T19:00:00Z",
            "outcome_known_at_utc":date+"T23:00:00Z",
            "source_captured_at_utc":"2026-10-20T14:00:00Z",
            "source_url":"https://example.edu/scores",
            "source_status":"OFFICIAL_POSTGAME_DRIVES_REVIEWED_RESEARCH_ONLY",
            "complete_drives_reviewed":True,
            "offensive_score_ownership_verified":True,"drives":drives})
    return {"status":"OFFICIAL_POSTGAME_DRIVES_REVIEWED_RESEARCH_ONLY","season":2026,
            "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,"games":games}

def game():
    return {"game_id":"next","home":"A","away":"B","kickoff_utc":KICKOFF}

class EmpiricalDriveTests(unittest.TestCase):
    def test_fit_to_simulator_from_observed_drives(self):
        record=fit(make_bundle(),game(),DECISION)
        self.assertTrue(record["ready"])
        out=simulate(record["simulator_input"],DECISION,trials=150,seed=12)
        self.assertGreater(out["home_points_mean"],0)
        self.assertEqual(out["away_points_mean"],0)
        self.assertFalse(out["model_promoted"])

    def test_two_team_field_position_and_defensive_history_are_empirical(self):
        result=fit(make_bundle(),game(),DECISION)
        observed=result["simulator_input"]["distributions"]
        self.assertEqual(set(observed["field_position_by_side"]),{"home","away"})
        self.assertEqual(sum(x["weight"] for x in observed["field_position_by_side"]["home"]),40)
        self.assertEqual(result["sample_summary"]["home"]["opponent_defense_exposed_drives"],40)
        self.assertFalse(result["model_promoted"])

    def test_unverified_score_ownership_rejected(self):
        data=make_bundle()
        data["games"][0]["offensive_score_ownership_verified"]=False
        with self.assertRaises(ValueError):
            fit(data,game(),DECISION)

    def test_missing_opponent_history_blocks_fit(self):
        g=game();g["away"]="C"
        result=fit(make_bundle(),g,DECISION)
        self.assertFalse(result["ready"])
        self.assertIsNone(result["simulator_input"])

    def test_bad_source_or_future_capture_rejected(self):
        data=make_bundle()
        data["games"][0]["complete_drives_reviewed"]=False
        with self.assertRaises(ValueError):fit(data,game(),DECISION)
        data=make_bundle()
        data["games"][0]["source_captured_at_utc"]="2026-11-01T00:00:00Z"
        with self.assertRaises(ValueError):fit(data,game(),DECISION)

    def test_cannot_invent_unknown_drive_scores(self):
        data=make_bundle()
        data["games"][0]["drives"][0]["points"]=None
        with self.assertRaises(ValueError):fit(data,game(),DECISION)

    def test_unequal_observed_possessions_are_preserved(self):
        data=make_bundle()
        data["games"][0]["drives"]=[x for x in data["games"][0]["drives"]
                                     if x["team"]!="B" or not x["drive_id"].endswith("-9")]
        result=fit(data,game(),DECISION)
        self.assertTrue(result["ready"])
        self.assertTrue(any(p["home_count"]==10 and p["away_count"]==9
                      for p in result["simulator_input"]["distributions"]["possessions"]))

if __name__=="__main__":
    unittest.main()

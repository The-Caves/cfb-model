import datetime as dt
import unittest
from scripts.player_prop_history import from_box_rows
from scripts.player_prop_matchup_walkforward import evaluate

AT="2026-11-15T19:00:00Z"
def fixture():
    # 33 consecutive matches allow >=25 prior league defense observations.
    rows=[];schedule={}
    for i in range(33):
        gid=str(400+i)
        day=dt.date(2026,9,1)+dt.timedelta(days=i)
        schedule[gid]={"date":day.isoformat(),"game_id":gid,
           "kickoff_utc":day.isoformat()+"T18:00:00Z",
           "home":"A","away":"B"}
        for team,name,y in ((10,"A QB",180+i),(20,"B QB",220+i)):
            rows.append({"game_id":gid,"season":2026,"team_id":team,
               "athlete_id":team+100,"athlete_name":name,"category":"passing",
               "passingYards":str(y),"passingTouchdowns":"1",
               "interceptions":"0","completions/passingAttempts":"15/25"})
        for team,name,y in ((10,"A RB",80+i),(20,"B RB",90+i)):
            rows.append({"game_id":gid,"season":2026,"team_id":team,
               "athlete_id":team+1000,"athlete_name":name,"category":"rushing",
               "rushingYards":str(y),"rushingAttempts":"15",
               "rushingTouchdowns":"1"})
    return from_box_rows(rows,schedule,AT)

class PlayerMatchupTests(unittest.TestCase):
    def test_prior_defense_only_and_baseline_same_cohort(self):
        r=evaluate(fixture(),start="2026-09-26")
        for field in ("passing_yards","rushing_yards"):
            self.assertGreater(r["summary"][field]["paired_recorded_player_games"],0)
            self.assertIsNotNone(r["summary"][field]["opponent_adjusted_delta_mae"])
            self.assertFalse(r["summary"][field]["eligible_for_live_model"])
        self.assertTrue(r["same_matchup_date_no_leakage"])

    def test_missing_matching_opponent_leaves_unknown_not_zero(self):
        source=fixture()
        # Only passing/rushing; no receiving game stat categories.
        r=evaluate(source,start="2026-09-26")
        self.assertEqual(r["summary"]["receiving_yards"]["paired_recorded_player_games"],0)
        self.assertIsNone(r["summary"]["receiving_yards"]["opponent_adjusted_mae"])

    def test_duplicate_game_athlete_rejected(self):
        r=fixture();r["rows"].append(dict(r["rows"][0]))
        with self.assertRaises(ValueError):evaluate(r)

if __name__=="__main__":
    unittest.main()

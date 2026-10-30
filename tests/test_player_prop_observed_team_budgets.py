import copy
import unittest
from scripts.player_prop_history import from_box_rows
from scripts.player_prop_observed_team_budgets import assemble

OBS="2026-10-30T19:00:00Z"
GAME={"100":{"game_id":"100","date":"2026-10-01",
             "kickoff_utc":"2026-10-01T18:00:00Z","home":"A","away":"B"}}

def fixture():
    return from_box_rows([
      {"game_id":"100","season":2026,"team_id":10,
       "athlete_id":20,"athlete_name":"QB","category":"passing",
       "completions/passingAttempts":"10/17","passingYards":"120",
       "passingTouchdowns":"1","interceptions":"0"},
      {"game_id":"100","season":2026,"team_id":10,
       "athlete_id":30,"athlete_name":"WR","category":"receiving",
       "receptions":"10","receivingYards":"120","receivingTouchdowns":"1"},
      {"game_id":"100","season":2026,"team_id":10,
       "athlete_id":50,"athlete_name":"RB","category":"rushing",
       "rushingAttempts":"21","rushingYards":"94","rushingTouchdowns":"0"},
    ],GAME,"2026-10-30T18:00:00Z")
def drives():
    return [{"season":2026,"game_id":100,"team_id":10,"drive_id":i} for i in range(9)]
class BudgetEvidenceTests(unittest.TestCase):
    def test_join_real_provenance_without_backdating_to_original_kickoff(self):
        a=assemble(fixture(),drives(),OBS,"b"*64)
        self.assertEqual(a["summary"]["eligible_matched_game_team_budgets"],1)
        r=a["team_game_budgets"][0]
        self.assertEqual(r["possessions"],9)
        self.assertEqual(r["pass_completions"],10)
        self.assertEqual(r["rush_yards"],94)
        self.assertEqual(r["outcome_confirmed_by_capture_utc"],OBS.replace("Z","+00:00"))
        self.assertFalse(a["ready_for_live_prop_forecasts"])
        self.assertFalse(a["all_active_player_participation_verified"])

    def test_duplicated_drives_quarantined_not_double_counted(self):
        rows=drives()+[drives()[0]]
        x=assemble(fixture(),rows,OBS,"b"*64)
        self.assertEqual(x["summary"]["eligible_matched_game_team_budgets"],0)
        self.assertEqual(x["summary"]["duplicated_drive_team_slots"],1)

    def test_bad_box_yards_and_receptions_quarantined(self):
        f=fixture()
        for r in f["rows"]:
            if r["player_id"]=="30":r["values"]["receiving_yards"]=90
        x=assemble(f,drives(),OBS,"b"*64)
        self.assertEqual(x["summary"]["eligible_matched_game_team_budgets"],0)
        self.assertIn("PASS_RECEIVE_YARDS_NOT_RECONCILED",x["summary"]["rejected_by_reason"])

    def test_future_or_retroactive_source_time_fails(self):
        f=fixture()
        with self.assertRaises(ValueError):
            assemble(f,drives(),"2026-10-01T17:00:00Z","b"*64)
        with self.assertRaises(ValueError):
            assemble(f,drives(),OBS,"short")

if __name__=="__main__":
    unittest.main()

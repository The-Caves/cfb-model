import unittest
from scripts.player_prop_history import from_box_rows, STATS
from scripts.player_prop_walkforward import evaluate
AT="2026-10-30T20:00:00Z"

def fixture():
    return {"100":{"game_id":"100","kickoff_utc":"2026-09-01T16:00:00Z",
                   "date":"2026-09-01","home":"A","away":"B"},
            "101":{"game_id":"101","kickoff_utc":"2026-09-08T16:00:00Z",
                   "date":"2026-09-08","home":"A","away":"B"},
            "102":{"game_id":"102","kickoff_utc":"2026-09-15T16:00:00Z",
                   "date":"2026-09-15","home":"A","away":"B"},
            "103":{"game_id":"103","kickoff_utc":"2026-09-29T16:00:00Z",
                   "date":"2026-09-29","home":"A","away":"B"}}
def passing(game,attempts="20/30",yards="220"):
    return {"game_id":game,"team_id":10,"athlete_id":77,
        "athlete_name":"Research QB","season":2026,"category":"passing",
        "passingYards":yards,"passingTouchdowns":"2","interceptions":"1",
        "completions/passingAttempts":attempts}

class PlayerPropHistoryTests(unittest.TestCase):
    def test_player_game_identity_and_passing_pair(self):
        result=from_box_rows([passing("100")],fixture(),AT)
        self.assertEqual(result["recorded_player_games"],1)
        v=result["rows"][0]["values"]
        self.assertEqual(v["passing_attempts"],30)
        self.assertEqual(v["passing_completions"],20)
        self.assertEqual(v["passing_yards"],220)
        self.assertIsNone(v["rushing_yards"])
        self.assertFalse(result["unlisted_player_game_means_zero"])

    def test_invalid_completion_attempts_remain_missing(self):
        r=from_box_rows([passing("100","35/30")],fixture(),AT)
        self.assertIsNone(r["rows"][0]["values"]["passing_attempts"])
        self.assertIsNone(r["rows"][0]["values"]["passing_completions"])

    def test_name_collision_and_duplicate_category_rejected(self):
        row=passing("100")
        with self.assertRaises(ValueError):
            from_box_rows([row,row],fixture(),AT)

    def test_research_challenger_not_selected_by_participation(self):
        items=[passing(g,yards=str(v)) for g,v in
               (("100",100),("101",140),("102",180),("103",220))]
        snapshot=from_box_rows(items,fixture(),AT)
        result=evaluate(snapshot,start="2026-09-26")
        p=result["summary"]["passing_yards"]
        self.assertEqual(p["paired_recorded_player_games"],1)
        self.assertEqual(p["baseline_mae"],80)
        self.assertFalse(result["source_first_publication_verified"])
        self.assertTrue(result["player_participation_selection_bias_present"])
        self.assertIsNone(result["summary"]["rushing_yards"]["baseline_mae"])

    def test_same_day_games_never_update_earlier_games(self):
        game=fixture()
        game["104"]={"game_id":"104","kickoff_utc":"2026-09-29T21:00:00Z",
                     "date":"2026-09-29","home":"C","away":"D"}
        rows=[passing(g,yards=str(y)) for g,y in
              (("100",100),("101",140),("102",180),("103",220),("104",300))]
        snapshot=from_box_rows(rows,game,AT)
        scored=evaluate(snapshot,start="2026-09-26")
        self.assertEqual(scored["summary"]["passing_yards"]["paired_recorded_player_games"],2)
        self.assertEqual(scored["summary"]["passing_yards"]["baseline_mae"],120)

if __name__=="__main__":
    unittest.main()

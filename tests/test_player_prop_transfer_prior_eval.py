import copy
import unittest
from scripts.player_prop_transfer_prior_eval import evaluate,STATUS
from scripts.player_prop_history import from_box_rows

NOW="2026-10-30T21:00:00Z"
def prev():
    seasons={}
    for year in (2024,2025):
        rows=[]
        for i in range(3):
            rows.append({"game_id":str(year*100+i),"team_id":"10" if year==2024 else "20",
                "player_id":"9001","date":f"{year}-09-{i+1:02d}",
                "source_status":"RETROSPECTIVE_REVISED_PLAYER_BOX_ONLY",
                "values":{"passing_yards":200+i*20}})
        seasons[str(year)]={"season":year,"player_game_ledger":rows}
    return {"status":"SOURCE_OBSERVED_2024_2025_PLAYER_GAME_FORM_RESEARCH_ONLY",
        "historical_first_publication_authenticated":False,
        "betting_status":"PASS_UNVALIDATED","seasons":[2024,2025],
        "source_observed_at_utc":NOW,"by_season":seasons}
def current(team=20):
    games={}
    records=[]
    for i in range(3):
        day=f"2026-09-{i+1:02d}"
        games[str(i+1)]={"game_id":str(i+1),"date":day,
            "kickoff_utc":day+"T18:00:00Z","home":"A","away":"B"}
        records.append({"game_id":str(i+1),"athlete_id":"9001",
            "team_id":team,"athlete_name":"Example QB","season":2026,
            "category":"passing","passingYards":str(280-i*20),
            "passingTouchdowns":"2","interceptions":"0",
            "completions/passingAttempts":"20/28"})
    return from_box_rows(records,games,NOW)

class TransferPriorResearchTests(unittest.TestCase):
    def test_same_athlete_same_team_priors_improve_early_game(self):
        r=evaluate(prev(),current(),first="2026-09-01",last="2026-10-01")
        self.assertEqual(r["status"],STATUS)
        a=r["summary"]["SAME_RECORDED_TEAM_ID"]["passing_yards"]
        self.assertEqual(a["matched_player_games"],2)
        self.assertLess(a["paired_mae_delta"],0)
        self.assertFalse(a["eligible_for_live_promotion"])
        self.assertEqual(r["real_bookmaker_player_prop_lines_used"],0)

    def test_different_team_association_shrinks_prior_more(self):
        r=evaluate(prev(),current(team=30),first="2026-09-01",last="2026-10-01")
        a=r["summary"]["DIFFERENT_RECORDED_TEAM_ID"]["passing_yards"]
        self.assertEqual(a["matched_player_games"],2)
        self.assertEqual(r["2025_previous_season_blend_for_different_team"],.25)
        self.assertFalse(r["transfer_eligibility_proved"])

    def test_missing_previous_season_does_not_invent_priors(self):
        p=prev();p["by_season"]["2025"]["player_game_ledger"]=[]
        r=evaluate(p,current(),first="2026-09-01",last="2026-10-01")
        self.assertEqual(r["summary"]["SAME_RECORDED_TEAM_ID"]["passing_yards"]["matched_player_games"],0)

    def test_future_same_day_games_are_not_lookahead(self):
        r=evaluate(prev(),current(),first="2026-09-02",last="2026-09-03")
        a=r["summary"]["SAME_RECORDED_TEAM_ID"]["passing_yards"]
        self.assertEqual(a["matched_player_games"],1)

    def test_untrusted_dates_or_duplicate_identity_cannot_grade(self):
        p=prev()
        p["historical_first_publication_authenticated"]=True
        with self.assertRaises(ValueError):evaluate(p,current())
        p=prev()
        p["by_season"]["2025"]["player_game_ledger"].append(
            p["by_season"]["2025"]["player_game_ledger"][0].copy())
        with self.assertRaises(ValueError):evaluate(p,current())

if __name__=="__main__":
    unittest.main()

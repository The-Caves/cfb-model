import unittest
from scripts.player_prop_history import from_box_rows
from scripts.player_prop_team_budget_audit import audit

AT="2026-10-30T19:00:00Z"
GAME={"100":{"date":"2026-10-01","game_id":"100",
    "kickoff_utc":"2026-10-01T18:00:00Z","home":"A","away":"B"}}

def box():
    return from_box_rows([
      {"game_id":"100","team_id":10,"athlete_id":1,"athlete_name":"QB",
       "season":2026,"category":"passing","passingYards":"120",
       "passingTouchdowns":"1","interceptions":"0",
       "completions/passingAttempts":"10/17"},
      {"game_id":"100","team_id":10,"athlete_id":2,"athlete_name":"WR",
       "season":2026,"category":"receiving","receptions":"6",
       "receivingYards":"70","receivingTouchdowns":"1"},
      {"game_id":"100","team_id":10,"athlete_id":3,"athlete_name":"RB",
       "season":2026,"category":"receiving","receptions":"4",
       "receivingYards":"50","receivingTouchdowns":"0"},
      {"game_id":"100","team_id":10,"athlete_id":3,"athlete_name":"RB",
       "season":2026,"category":"rushing","rushingAttempts":"15",
       "rushingYards":"82","rushingTouchdowns":"0"},
    ],GAME,AT)

class TeamStatAuditTests(unittest.TestCase):
    def test_accounting_matches_but_not_roster_completeness(self):
        r=audit(box())
        self.assertEqual(r["summary"]["observed_team_game_slots"],1)
        self.assertEqual(r["summary"]["slots_completion_reception_reconcile"],1)
        self.assertEqual(r["summary"]["slots_passing_receiving_yards_reconcile"],1)
        self.assertEqual(r["summary"]["all_players_participation_verified"],0)
        self.assertIsNone(r["per_team_game"][0]["all_player_participation_verified"] if False else None)
        self.assertFalse(r["per_team_game"][0]["all_player_participation_verified"])

    def test_missing_receivers_are_unknown_not_zero(self):
        r=box()
        r["rows"]=[p for p in r["rows"] if p["player_id"]=="1"]
        x=audit(r)["per_team_game"][0]
        self.assertIsNone(x["reported_receiving_catches"])
        self.assertIsNone(x["observed_completion_reception_exact_match"])

    def test_mismatch_is_recorded_not_silently_coerced(self):
        r=box()
        r["rows"][1]["values"]["receiving_yards"]=40
        x=audit(r)["per_team_game"][0]
        self.assertFalse(x["observed_passing_receiving_yard_exact_match"])
        self.assertEqual(x["passing_minus_receiving_yards"],30)
        self.assertFalse(x["all_player_participation_verified"])

    def test_duplicate_source_player_key_rejected(self):
        r=box();r["rows"].append(dict(r["rows"][0]))
        with self.assertRaises(ValueError):audit(r)

if __name__=="__main__":
    unittest.main()

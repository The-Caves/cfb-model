import copy
import unittest
from scripts.site_simulation_shadow import attach, STATUS, PENDING, AVAILABLE
from scripts.observed_drive_fit import SOURCE_STATUS

DECISION="2026-10-30T17:00:00Z"
KICKOFF="2026-10-31T19:00:00Z"


def board():
    return {"schema_version": 2, "betting_status": "PASS_UNVALIDATED",
            "prospective_records": {"su": {"wins": 1, "losses": 0}},
            "games": [{"game_id": "next", "home_team": "A", "away_team": "B",
                      "kickoff_utc": KICKOFF, "model_home_margin": -5.5,
                      "model_total": 54.5, "v04_direct_scores": {"home_points": 25.1}}]}


def reviewed_drives():
    rows = []
    for index in range(4):
        date="2026-09-"+str(index+1).zfill(2)
        plays = []
        for side, team in (("home", "A"), ("away", "B")):
            for n in range(10):
                plays.append({"team": team, "drive_id": str(index)+"-"+side+"-"+str(n),
                              "field_zone": "own_half" if n%2==0 else "midfield",
                              "points": 7 if n%4==0 and team=="A" else 0,
                              "explosive": n%3==0})
        rows.append({"game_id": str(index), "home": "A", "away": "B",
                     "kickoff_utc": date+"T19:00:00Z",
                     "outcome_known_at_utc": date+"T23:00:00Z",
                     "source_captured_at_utc": "2026-10-20T14:00:00Z",
                     "source_url": "https://example.edu/scores",
                     "source_status": SOURCE_STATUS,
                     "complete_drives_reviewed": True,
                     "offensive_score_ownership_verified": True,
                     "drives": plays})
    return {"status": SOURCE_STATUS, "season": 2026, "games": rows,
            "betting_status": "PASS_UNVALIDATED", "safe_for_betting": False}


class SimulationShadowTests(unittest.TestCase):
    def test_missing_sources_does_not_make_up_simulations(self):
        data=board()
        old=copy.deepcopy(data["games"])
        result=attach(data,None,DECISION)
        self.assertEqual(result["simulation_display"]["readiness"],PENDING)
        self.assertEqual(result["simulation_display"]["games_with_fit"],0)
        self.assertIsNone(result["games"][0]["simulation_shadow"])
        self.assertEqual(result["games"][0]["model_home_margin"],old[0]["model_home_margin"])

    def test_verified_history_enables_only_shadow_and_preserves_v04(self):
        data=board()
        original=copy.deepcopy(data)
        out=attach(data,reviewed_drives(),DECISION,trials=150)
        sim=out["games"][0]["simulation_shadow"]
        self.assertEqual(out["simulation_display"]["readiness"],AVAILABLE)
        self.assertEqual(sim["status"],AVAILABLE)
        self.assertGreater(sim["home_points_mean"],0)
        self.assertIsNone(sim.get("home_cover_probability"))
        self.assertFalse(sim["validated_win_probabilities"])
        self.assertFalse(sim["model_promoted"])
        self.assertEqual(out["prospective_records"],original["prospective_records"])
        self.assertEqual(out["games"][0]["v04_direct_scores"],original["games"][0]["v04_direct_scores"])

    def test_false_evidence_and_future_drives_fail_closed(self):
        for change in ({"status": "RAW_UNREVIEWED"},
                       {"safe_for_betting": True}):
            data=reviewed_drives()
            data.update(change)
            with self.assertRaises(ValueError):
                attach(board(),data,DECISION,trials=150)
        data=reviewed_drives()
        data["games"][0]["source_captured_at_utc"]="2026-10-31T21:00:00Z"
        with self.assertRaises(ValueError):
            attach(board(),data,DECISION,trials=150)

    def test_thin_independent_history_stays_unfit(self):
        data=reviewed_drives()
        data["games"] = data["games"][:1]
        out=attach(board(),data,DECISION,trials=150)
        self.assertIsNone(out["games"][0]["simulation_shadow"])
        self.assertEqual(out["simulation_display"]["games_with_fit"],0)


if __name__ == "__main__":
    unittest.main()

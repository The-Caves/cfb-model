"""Source-only completed-score display and no changes to archived grades."""
import copy
import unittest

from scripts.site_history_scores import apply, capture, SOURCE

WHEN = "2026-11-13T13:00:00Z"
KICK = "2026-11-13T01:00:00Z"


def raw(state="post", complete=True, home="Home"):
    return {"events": [{
        "id": "123", "date": KICK, "status": {"type": {"state": state, "completed": complete}},
        "competitions": [{
            "date": KICK,
            "competitors": [
                {"homeAway": "home", "team": {"displayName": home}, "score": "30"},
                {"homeAway": "away", "team": {"displayName": "Away"}, "score": "17"}
            ]
        }]
    }]}


def board():
    return {
        "schema_version": 2, "betting_status": "PASS_UNVALIDATED",
        "games": [{"model_home_margin": -3.3}],
        "prospective_records": {"su": {"wins": 4}},
        "history_display": {
            "status": "ARCHIVED_PREKICKOFF_V04_WITH_INDEPENDENT_FINAL",
            "verified_finals": 0},
        "history_games": [{
            "game_id": "123", "kickoff_utc": KICK, "home_team": "Home",
            "away_team": "Away", "archived_model": "V04",
            "model_home_margin": -4.5, "market_home_spread": -2.5,
            "market_total": 55, "ats_pick": "PASS", "ou_pick": "UNDER",
            "final": None, "outcomes": {"su": "PENDING", "ats": "PENDING", "ou": "PENDING"}
        }]
    }


class FinalDisplayTests(unittest.TestCase):
    def test_completed_source_matches_without_lying_about_graded_archive(self):
        data = board()
        orig = copy.deepcopy(data)
        event = capture(raw(), WHEN)
        result = apply(data, event, WHEN)
        game = result["history_games"][0]
        self.assertEqual(game["final"]["home_score"], 30)
        self.assertEqual(game["final"]["source"], SOURCE)
        self.assertEqual(game["outcomes"]["su"], "LOSS")
        self.assertEqual(game["outcomes"]["ats"], "PASS")
        self.assertEqual(game["outcomes"]["ou"], "WIN")
        self.assertTrue(game["outcomes_display_only"])
        self.assertEqual(result["history_display"]["verified_finals"], 0)
        self.assertEqual(result["prospective_records"], orig["prospective_records"])
        self.assertEqual(result["games"], orig["games"])

    def test_only_final_counts(self):
        self.assertEqual(capture(raw(state="in"), WHEN), {})
        self.assertEqual(capture(raw(complete=False), WHEN), {})

    def test_team_mismatch_and_unverified_kickoff_are_rejected(self):
        self.assertIsNone(apply(board(), capture(raw(home="Wrong"), WHEN),
                                WHEN)["history_games"][0]["final"])
        bad = raw()
        bad["events"][0]["competitions"][0]["date"] = "2026-11-15T01:00:00Z"
        self.assertEqual(capture(bad, WHEN), {})

    def test_original_archived_final_takes_priority(self):
        data = board()
        data["history_games"][0]["final"] = {"home_score": 12, "away_score": 10}
        done = apply(data, capture(raw(), WHEN), WHEN)
        self.assertEqual(done["history_games"][0]["final"]["home_score"], 12)
        self.assertEqual(done["history_display"]["espn_provisional_display_finals"], 0)


if __name__ == "__main__":
    unittest.main()

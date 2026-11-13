"""V14 player-level joint-context research, conserved real team opportunities."""
import copy
import unittest

from scripts.v14_player_scenarios import simulate,STATUS
from scripts.player_prop_conserved_opportunities import simulate as conserve
from tests.test_player_prop_conserved_opportunities import (
    gamefit,profile,ASOF,KICK)


def forecast():
    return {"status":"V14_REGULARIZED_V04_MATCHUP_RESIDUAL_RESEARCH_ONLY",
        "source_cutoff_exclusive":"2026-10-30",
        "home_points":29.,"away_points":25.,"margin":4.,"total":54.,
        "current_market_line_used_for_training":False,
        "historical_source_first_publication_verified":False,
        "model_promoted":False,"safe_for_betting":False}


def quotes():
    return {"status":"NCAAF_PLAYER_PROP_SOURCE_CAPTURE_RESEARCH_ONLY",
        "espn_game_id":"100","observed_at_utc":"2026-10-30T17:00:00Z",
        "safe_for_betting":False,"model_promoted":False,
        "quotes":[{"status":"OBSERVED_TWO_SIDED_PREDECISION_PROP",
            "espn_game_id":"100","team":"A","player_id":"A-QB",
            "metric":"passing_yards","line":180.5,
            "bookmaker":"fanduel","over_american_odds":-110,
            "under_american_odds":-110,
            "implied_over_no_vig":.5,
            "observed_at_utc":"2026-10-30T17:00:00Z",
            "book_updated_at_utc":"2026-10-30T16:55:00Z",
            "market_updated_at_utc":"2026-10-30T16:55:00Z",
            "kickoff_utc":KICK,
            "source_snapshot_sha256":"c"*64}]}


class V14PlayerScenarios(unittest.TestCase):
    def test_real_sourced_prop_line_graded_with_shared_opportunities(self):
        x=simulate(gamefit(),profile(),forecast(),ASOF,
                   quotes=quotes(),trials=100,seed=44)
        self.assertEqual(x["status"],STATUS)
        self.assertEqual(x["game_points"]["margin"],4.)
        self.assertTrue(x["team_opportunities_conserved"])
        self.assertTrue(x["unknown_athletes_preserved"])
        self.assertFalse(x["fully_jointly_calibrated_game_and_player_scores"])
        self.assertFalse(x["safe_for_betting"])
        self.assertFalse(x["model_promoted"])
        q=x["matched_sourced_prop_probabilities"]
        self.assertEqual(len(q),1)
        self.assertEqual(q[0]["player_id"],"A-QB")
        self.assertEqual(q[0]["metric"],"passing_yards")
        self.assertAlmostEqual(sum(q[0][k] for k in (
            "conditional_over_probability","conditional_under_probability",
            "simulated_push_probability")),1.,places=5)
        self.assertFalse(q[0]["calibrated_prop_edge"])
        self.assertEqual(x,simulate(gamefit(),profile(),forecast(),ASOF,
                                    quotes=quotes(),trials=100,seed=44))

    def test_without_real_market_no_prop_line_or_probability_fabrication(self):
        x=simulate(gamefit(),profile(),forecast(),ASOF,trials=50,seed=8)
        self.assertEqual(x["matched_sourced_prop_probabilities"],[])
        original=conserve(gamefit(),profile(),ASOF,trials=50,seed=8)
        self.assertEqual(x["player_opportunity_scenarios"],
                         original["team_scenarios"])

    def test_verified_touchdown_quotes_are_passed_not_invented(self):
        q=quotes()
        td=dict(q["quotes"][0],metric="passing_touchdowns",
                line=1.5)
        q["quotes"].append(td)
        r=simulate(gamefit(),profile(),forecast(),ASOF,
                   quotes=q,trials=50,seed=2)
        self.assertEqual(len(r["matched_sourced_prop_probabilities"]),1)
        self.assertEqual(r["unsupported_verified_prop_categories"][0]["metric"],
                         "passing_touchdowns")
        self.assertFalse(r["player_prop_betting_edge_proven"])

    def test_after_decision_quote_or_wrong_player_refused(self):
        q=quotes()
        q["quotes"][0]["observed_at_utc"]="2026-10-31T19:00:00Z"
        with self.assertRaises(ValueError):
            simulate(gamefit(),profile(),forecast(),ASOF,
                     quotes=q,trials=50)
        q=quotes();q["quotes"][0]["player_id"]="UNVERIFIED"
        with self.assertRaises(ValueError):
            simulate(gamefit(),profile(),forecast(),ASOF,
                     quotes=q,trials=50)
        q=quotes();q["espn_game_id"]="WRONG"
        with self.assertRaises(ValueError):
            simulate(gamefit(),profile(),forecast(),ASOF,
                     quotes=q,trials=50)

    def test_score_changes_and_future_week_do_not_launder_into_player_forecast(self):
        g=forecast();g["model_promoted"]=True
        with self.assertRaises(ValueError):
            simulate(gamefit(),profile(),g,ASOF,trials=50)
        g=forecast();g["source_cutoff_exclusive"]="2026-11-01"
        with self.assertRaisesRegex(ValueError,"Future weekly"):
            simulate(gamefit(),profile(),g,ASOF,trials=50)
        g=forecast();g["margin"]=400.
        with self.assertRaises(ValueError):
            simulate(gamefit(),profile(),g,ASOF,trials=50)

if __name__=="__main__":
    unittest.main()

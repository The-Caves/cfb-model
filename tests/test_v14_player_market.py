"""V14 player prop simulation uses actual paired predecision source lines only.

The existing source-audited player-budget simulator conserves every pass, target,
reception, rushing carry and yard. This acceptance test confirms that V14
cannot turn a hypothetical/late/unknown-athlete line into an actionable edge.
"""
import copy
import unittest
from scripts.player_prop_conserved_opportunities import simulate
from tests.test_player_prop_conserved_opportunities import gamefit,profile,ASOF,KICK

def verified_quotes():
    return {"status":"NCAAF_PLAYER_PROP_SOURCE_CAPTURE_RESEARCH_ONLY",
       "espn_game_id":"100","observed_at_utc":"2026-10-30T17:30:00Z",
       "safe_for_betting":False,"model_promoted":False,
       "quotes":[{
          "status":"OBSERVED_TWO_SIDED_PREDECISION_PROP",
          "provider":"the-odds-api-v4","bookmaker":"fanduel",
          "espn_game_id":"100","team":"A","player_id":"A-QB",
          "metric":"passing_yards","line":184.5,
          "over_american_odds":-110,"under_american_odds":-110,
          "implied_over_no_vig":.5,
          "source_snapshot_sha256":"b"*64,
          "kickoff_utc":KICK,
          "observed_at_utc":"2026-10-30T17:30:00Z",
          "book_updated_at_utc":"2026-10-30T17:10:00Z",
          "market_updated_at_utc":"2026-10-30T17:15:00Z"}]}

class V14PlayerPropTests(unittest.TestCase):
    def test_conserved_player_usage_and_verified_quote_probability(self):
        p=profile()
        original=copy.deepcopy(p)
        r=simulate(gamefit(),p,ASOF,trials=110,seed=14,
                   quotes=verified_quotes())
        self.assertEqual(p,original)
        self.assertTrue(r["team_stat_conservation"])
        self.assertEqual(r["reconciled_team_trials"],220)
        self.assertFalse(r["v14_player_prop_betting_edge_verified"])
        self.assertFalse(r["prop_model_probabilities_calibrated"])
        self.assertFalse(r["model_promoted"])
        self.assertEqual(len(r["v14_matched_player_prop_quote_probabilities"]),1)
        q=r["v14_matched_player_prop_quote_probabilities"][0]
        self.assertAlmostEqual(q["conditional_over_probability"]+
            q["conditional_under_probability"]+
            q["simulated_push_probability"],1.,places=5)
        self.assertTrue(q["player_active_scenario_conditional"])
        self.assertFalse(q["calibrated_prop_edge"])

    def test_absent_lines_do_not_create_implied_betting_value(self):
        r=simulate(gamefit(),profile(),ASOF,trials=50,seed=14)
        self.assertEqual(r["v14_matched_player_prop_quote_probabilities"],[])
        self.assertFalse(r["v14_player_prop_betting_edge_verified"])

    def test_future_prices_unknown_player_and_line_mismatch_rejected(self):
        for key,val in (("observed_at_utc",KICK),("source_snapshot_sha256","x"),
                        ("player_id","UNVERIFIED"),("kickoff_utc","2026-11-02T14:00:00Z")):
            source=verified_quotes();source["quotes"][0][key]=val
            with self.subTest(field=key),self.assertRaises(ValueError):
                simulate(gamefit(),profile(),ASOF,trials=50,quotes=source)

    def test_only_supported_categories_are_simulated(self):
        source=verified_quotes()
        source["quotes"][0]["metric"]="passing_touchdowns"
        r=simulate(gamefit(),profile(),ASOF,trials=50,quotes=source)
        self.assertFalse(r["v14_matched_player_prop_quote_probabilities"])
        self.assertEqual(len(r["v14_unsupported_verified_prop_categories"]),1)

if __name__=="__main__":
    unittest.main()

import copy
import unittest
from scripts.player_prop_history import from_box_rows
from scripts.player_prop_joint_simulation import simulate

DEC="2026-10-30T19:00:00Z"
KICK="2026-10-31T20:00:00Z"
def fitted():
    return {"status":"FROZEN_PREDECISION_DRIVE_DISTRIBUTIONS_RESEARCH_ONLY",
       "game_id":"200","home":"A","away":"B","kickoff_utc":KICK,
       "trained_through_utc":"2026-10-29T10:00:00Z",
       "source_captured_at_utc":"2026-10-30T18:00:00Z",
       "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
       "model_promoted":False,
       "distributions":{"possessions":[{"home_count":10,"away_count":9,"weight":1}],
          "field_position":[{"zone":"half","weight":1}],
          "outcomes":{"home":{"half":[{"points":3,"weight":1,"explosive":False}]},
                      "away":{"half":[{"points":0,"weight":1,"explosive":False}]}}}}
def player_history():
    games={str(i):{"game_id":str(i),"date":f"2026-09-{i+1:02d}",
         "kickoff_utc":f"2026-09-{i+1:02d}T20:00:00Z",
         "home":"A","away":"C"} for i in range(5)}
    rows=[{"game_id":str(i),"team_id":10,"athlete_id":100,
           "athlete_name":"QB Example","season":2026,"category":"passing",
           "passingYards":str(200+i*20),"passingTouchdowns":"2",
           "interceptions":"1","completions/passingAttempts":"20/30"} for i in range(5)]
    return from_box_rows(rows,games,"2026-10-30T16:00:00Z")
def possessions():
    return {"status":"OBSERVED_PRIOR_TEAM_POSSESSIONS_RESEARCH_ONLY",
       "observed_at_utc":"2026-10-30T18:00:00Z",
       "rows":[{"game_id":str(i),"team_id":"10","team_possessions":10,
                "observed_at_utc":"2026-10-30T16:00:00Z",
                "source_url":"https://example.edu/box"} for i in range(5)]}
def target():
    return {"game_id":"200","date":"2026-10-31","kickoff_utc":KICK,
       "home":"A","away":"B","players":[
         {"player_id":"100","team_id":"10","team":"A",
          "availability":"UNCONFIRMED_EXPECTED",
          "availability_observed_at_utc":"2026-10-30T17:00:00Z"}]}

class PlayerPropJointTests(unittest.TestCase):
    def test_same_game_10_possessions_resamples_joint_passing_stats(self):
        r=simulate(fitted(),player_history(),possessions(),target(),DEC,trials=200,seed=42)
        self.assertEqual(r["status"],"POSSESSION_CONDITIONED_PROP_SIM_RESEARCH_ONLY")
        self.assertEqual(r["mean_simulated_home_score"],30)
        self.assertEqual(r["mean_simulated_away_score"],0)
        self.assertEqual(r["mean_home_possessions"],10)
        p=r["player_scenarios"][0]
        self.assertEqual(p["metrics"]["passing_attempts"]["mean"],30)
        self.assertGreater(p["metrics"]["passing_yards"]["mean"],190)
        self.assertTrue(p["probabilities_conditional_on_playing"])
        self.assertFalse(r["team_level_stat_conservation_fitted"])

    def test_reproducible_seed_and_unknown_market_no_line(self):
        a=simulate(fitted(),player_history(),possessions(),target(),DEC,trials=100,seed=10)
        b=simulate(fitted(),player_history(),possessions(),target(),DEC,trials=100,seed=10)
        self.assertEqual(a,b)
        self.assertEqual(a["player_scenarios"][0]["metrics"]["passing_yards"]["quoted_markets"],[])

    def test_real_predecision_quote_comparison_conditional_only(self):
        quote={"status":"NCAAF_PLAYER_PROP_SOURCE_CAPTURE_RESEARCH_ONLY",
               "espn_game_id":"200","quotes":[{
                 "status":"OBSERVED_TWO_SIDED_PREDECISION_PROP",
                 "espn_game_id":"200","player_id":"100","metric":"passing_yards",
                 "line":240.5,"bookmaker":"fanduel","implied_over_no_vig":.5,
                 "observed_at_utc":"2026-10-30T18:00:00Z",
                 "kickoff_utc":KICK,"betting_status":"PASS_UNVALIDATED"}]}
        a=simulate(fitted(),player_history(),possessions(),target(),DEC,quote,trials=100)
        m=a["player_scenarios"][0]["metrics"]["passing_yards"]["quoted_markets"][0]
        self.assertAlmostEqual(m["over_probability_conditional"]+m["under_probability_conditional"],1)
        self.assertTrue(m["potential_edge_unvalidated"])
        quote["quotes"][0]["observed_at_utc"]=KICK
        with self.assertRaises(ValueError):
            simulate(fitted(),player_history(),possessions(),target(),DEC,quote,trials=100)

    def test_missing_sources_and_postdecision_do_not_create_false_predictions(self):
        missing=possessions();missing["rows"]=[]
        r=simulate(fitted(),player_history(),missing,target(),DEC,trials=100)
        self.assertEqual(r["status"],"PASS_INSUFFICIENT_PLAYER_PREGAME_EVIDENCE")
        source=player_history();source["rows"][0]["observed_at_utc"]="2026-11-02T00:00:00Z"
        r=simulate(fitted(),source,possessions(),target(),DEC,trials=100)
        self.assertEqual(r["status"],"POSSESSION_CONDITIONED_PROP_SIM_RESEARCH_ONLY")
        no=target();no["players"][0]["availability"]="UNKNOWN"
        self.assertEqual(simulate(fitted(),player_history(),possessions(),no,DEC,trials=100)["status"],
                         "PASS_INSUFFICIENT_PLAYER_PREGAME_EVIDENCE")
        with self.assertRaises(ValueError):
            simulate(fitted(),player_history(),possessions(),target(),"2026-11-01T00:00:00Z",trials=100)

if __name__=="__main__":
    unittest.main()

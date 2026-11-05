"""Game-level player opportunity conservation, time gates and honest PASS tests."""
import copy
import unittest

from scripts.player_prop_team_budget import (
    STATUS, bounded_counts, conserve_trial, prepare)
from scripts.player_prop_joint_simulation import simulate
from test_player_prop_joint_simulation import (
    fitted,player_history,possessions,target,DEC,KICK)


def source():
    rows=[]
    for i in range(5):
        for side,team,passing,rushing in (
            ("home",10,25,30),("away",20,17,39)):
            rows.append({
                "game_id":str(i),"team_id":str(team),
                "kickoff_utc":f"2026-09-{i+1:02d}T20:00:00Z",
                "outcome_known_at_utc":f"2026-09-{i+1:02d}T23:00:00Z",
                "captured_at_utc":"2026-10-29T12:00:00Z",
                "passing_attempts":passing,"rushing_attempts":rushing,
                "complete_team_attempts_reviewed":True,
                "source_url":"https://example.edu/verified/boxscore"})
    return {
        "status":STATUS,"season":2026,
        "target_game_id":"200","target_kickoff_utc":KICK,
        "observed_at_utc":"2026-10-29T15:00:00Z",
        "rows":rows,"betting_status":"PASS_UNVALIDATED",
        "safe_for_betting":False,"model_promoted":False}


def inputs():
    t=target()
    t["team_ids"]={"home":"10","away":"20"}
    p=possessions()
    p["rows"] += [
        {"game_id":str(i),"team_id":"20","team_possessions":10,
         "observed_at_utc":"2026-10-30T16:00:00Z",
         "source_url":"https://example.edu/verified/boxscore"}
        for i in range(5)]
    return t,p


class BudgetTests(unittest.TestCase):
    def test_allocation_never_exceeds_cap_and_reserves_unknown_players(self):
        self.assertEqual(bounded_counts([11,9],10),([6,4],0))
        self.assertEqual(bounded_counts([2,1],5),([2,1],2))
        self.assertEqual(bounded_counts([],8),([],8))
        self.assertEqual(bounded_counts([4,5],0),([0,0],0))
        with self.assertRaises(ValueError):bounded_counts([3,-1],8)

    def test_joint_player_attempts_and_receiver_catches_are_bounded(self):
        players={
            "qb1":{"side":"home","values":{
                "passing_attempts":15,"passing_completions":12,
                "passing_yards":150,"passing_touchdowns":3,"interceptions":2}},
            "qb2":{"side":"home","values":{
                "passing_attempts":15,"passing_completions":11,
                "passing_yards":120,"passing_touchdowns":1}},
            "wr1":{"side":"home","values":{
                "receptions":11,"receiving_yards":120,"receiving_touchdowns":2}},
            "wr2":{"side":"home","values":{
                "receptions":9,"receiving_yards":80}},
            "rb1":{"side":"home","values":{
                "rushing_attempts":16,"rushing_yards":140,"rushing_touchdowns":2}},
            "rb2":{"side":"home","values":{
                "rushing_attempts":12,"rushing_yards":100}},
        }
        caps={"home":{"passing_attempts":18,"rushing_attempts":20},
              "away":{"passing_attempts":19,"rushing_attempts":25}}
        residual=conserve_trial(players,caps)
        home=[p["values"] for p in players.values()]
        self.assertEqual(sum(p.get("passing_attempts",0) for p in home),18)
        self.assertEqual(sum(p.get("rushing_attempts",0) for p in home),20)
        self.assertLessEqual(sum(p.get("receptions",0) for p in home),
                             sum(p.get("passing_completions",0) for p in home))
        self.assertGreaterEqual(residual["home"]["passing_attempts"],0)
        self.assertEqual(residual["away"]["passing_attempts"],19)
        self.assertTrue(all(p.get("passing_touchdowns",0)<=p.get("passing_completions",999)
                            for p in home))
        self.assertTrue(all(p.get("rushing_touchdowns",0)<=p.get("rushing_attempts",999)
                            for p in home))

    def test_source_requires_prior_complete_independently_observed_team_attempts(self):
        t,p=inputs()
        accepted,status=prepare(source(),t,p["rows"],DEC)
        self.assertEqual(status,"READY_CONDITIONAL_BUDGET_SHADOW")
        self.assertEqual(len(accepted["home"]),5)
        self.assertEqual(prepare(None,t,p["rows"],DEC)[0],None)
        bad=source();bad["rows"][0]["captured_at_utc"]="2026-11-01T14:00:00Z"
        with self.assertRaises(ValueError):prepare(bad,t,p["rows"],DEC)
        bad=source();bad["rows"][0]["complete_team_attempts_reviewed"]=False
        with self.assertRaises(ValueError):prepare(bad,t,p["rows"],DEC)
        bad=source();bad["target_game_id"]="999"
        with self.assertRaises(ValueError):prepare(bad,t,p["rows"],DEC)
        bad=source();bad["rows"][0]["team_id"]="30"
        with self.assertRaises(ValueError):prepare(bad,t,p["rows"],DEC)
        bad=source();bad["rows"][0]["kickoff_utc"]="2026-10-31T10:00:00Z"
        with self.assertRaises(ValueError):prepare(bad,t,p["rows"],DEC)
        bad=source();bad["rows"]=bad["rows"][:4]
        self.assertEqual(prepare(bad,t,p["rows"],DEC)[1],
                         "PASS_INSUFFICIENT_COMPLETE_HISTORICAL_TEAM_ATTEMPTS")

    def test_optional_verified_workload_budget_changes_player_opportunities_not_scores(self):
        t,p=inputs()
        original=simulate(fitted(),player_history(),p,t,DEC,trials=200,seed=42)
        adjusted=simulate(fitted(),player_history(),p,t,DEC,trials=200,seed=42,
                          team_attempt_budgets=source())
        self.assertFalse(original["team_attempt_budget_applied"])
        self.assertTrue(adjusted["team_attempt_budget_applied"])
        self.assertFalse(adjusted["team_level_stat_conservation_fitted"])
        self.assertEqual(adjusted["team_attempt_budget_status"],
                         "READY_CONDITIONAL_BUDGET_SHADOW")
        self.assertEqual(adjusted["player_scenarios"][0]["metrics"]["passing_attempts"]["mean"],25)
        self.assertEqual(original["player_scenarios"][0]["metrics"]["passing_attempts"]["mean"],30)
        self.assertEqual(adjusted["mean_simulated_home_score"],30)
        self.assertEqual(adjusted["mean_simulated_away_score"],0)
        # Away has nine projected possessions vs ten in the reviewed
        # historical source; 17 * 9/10 rounds to 15 attempts.
        self.assertEqual(adjusted["team_attempt_budget_unallocated_average"]["away"]["passing_attempts"],15)
        self.assertFalse(adjusted["prop_market_edge_validated"])
        self.assertFalse(adjusted["model_promoted"])
        self.assertEqual(adjusted["betting_status"],"PASS_UNVALIDATED")


if __name__=="__main__":
    unittest.main()

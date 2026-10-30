import copy
import unittest
from scripts.player_prop_conserved_opportunities import simulate

KICK="2026-10-31T20:00:00Z"
ASOF="2026-10-30T18:00:00Z"
def gamefit():
    return {"status":"FROZEN_PREDECISION_DRIVE_DISTRIBUTIONS_RESEARCH_ONLY",
        "game_id":"100","home":"A","away":"B","kickoff_utc":KICK,
        "trained_through_utc":"2026-10-29T09:00:00Z",
        "source_captured_at_utc":"2026-10-30T15:00:00Z",
        "safe_for_betting":False,"model_promoted":False,
        "betting_status":"PASS_UNVALIDATED",
        "distributions":{"possessions":[{"home_count":10,"away_count":9,"weight":1}],
             "field_position":[{"zone":"own","weight":1}],
             "outcomes":{"home":{"own":[{"points":0,"explosive":False,"weight":1}]},
                         "away":{"own":[{"points":0,"explosive":False,"weight":1}]}}}}
def profile():
    def team(name):
        return {"team":name,"roster_coverage":"PARTIAL_VERIFIED_SOURCE_REVIEWED",
            "prior_games":[{"game_id":str(i)+name,
              "kickoff_utc":f"2026-09-0{i}T19:00:00Z",
              "outcome_known_at_utc":f"2026-09-0{i}T23:00:00Z",
              "observed_at_utc":"2026-10-20T15:00:00Z",
              "source_url":"https://example.edu/box",
              "pass_attempts":30,"pass_completions":18,"pass_yards":210,
              "rush_attempts":28,"rush_yards":115,"possessions":10}
              for i in range(1,5)],
            "players":[
              {"player_id":name+"-QB","availability":"UNCONFIRMED_EXPECTED",
                "role_evidence_reviewed":True,"source_url":"https://example.edu/depth",
                "source_observed_at_utc":"2026-10-30T16:00:00Z",
                "pass_attempt_share":.91,"carry_share":.12,
                "rushing_yards_per_carry":4.5},
              {"player_id":name+"-WR","availability":"CONFIRMED_ACTIVE",
                "role_evidence_reviewed":True,"source_url":"https://example.edu/depth",
                "source_observed_at_utc":"2026-10-30T16:00:00Z",
                "target_share":.36,"receiving_yards_per_catch":12.5},
              {"player_id":name+"-RB","availability":"UNCONFIRMED_EXPECTED",
                "role_evidence_reviewed":True,"source_url":"https://example.edu/depth",
                "source_observed_at_utc":"2026-10-30T16:00:00Z",
                "carry_share":.6,"rushing_yards_per_carry":4.1,
                "target_share":.09,"receiving_yards_per_catch":7.2}
            ]}
    return {"status":"PREDECISION_TEAM_BOX_AND_ROLE_EVIDENCE_RESEARCH_ONLY",
        "captured_at_utc":"2026-10-30T17:00:00Z",
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
        "teams":{"home":team("A"),"away":team("B")}}

class OpportunityTests(unittest.TestCase):
    def test_per_trial_exact_reconciliation_and_unknown_buckets(self):
        r=simulate(gamefit(),profile(),ASOF,trials=100,seed=15)
        self.assertEqual(r["reconciled_team_trials"],200)
        self.assertTrue(r["team_stat_conservation"])
        for team in r["team_scenarios"]:
            self.assertEqual(len(team["player_opportunity_scenarios"]),6)
            others=[p for p in team["player_opportunity_scenarios"] if p["is_unmodeled_bucket"]]
            self.assertEqual(len(others),3)
            self.assertGreater(next(x for x in others if x["player_id"]=="OTHER_RECEIVER")
                               ["metrics"]["targets"]["mean"],0)
            self.assertFalse(team["source_lineup_complete"])
        self.assertFalse(r["model_promoted"])

    def test_repeated_runs_have_same_seeded_results(self):
        a=simulate(gamefit(),profile(),ASOF,trials=50,seed=20)
        b=simulate(gamefit(),profile(),ASOF,trials=50,seed=20)
        self.assertEqual(a,b)

    def test_unknown_role_and_future_captured_role_never_imputed(self):
        p=profile()
        p["teams"]["home"]["players"][0]["source_observed_at_utc"]=KICK
        with self.assertRaises(ValueError):
            simulate(gamefit(),p,ASOF,trials=50)
        p=profile()
        p["teams"]["away"]["players"][0]["pass_attempt_share"]=1.
        with self.assertRaises(ValueError):
            simulate(gamefit(),p,ASOF,trials=50)

    def test_no_trust_in_future_team_game_or_bad_completions(self):
        p=profile()
        p["teams"]["home"]["prior_games"][0]["observed_at_utc"]=KICK
        with self.assertRaises(ValueError):
            simulate(gamefit(),p,ASOF,trials=50)
        p=profile()
        p["teams"]["away"]["prior_games"][1]["pass_completions"]=40
        with self.assertRaises(ValueError):
            simulate(gamefit(),p,ASOF,trials=50)

    def test_unknown_source_or_no_real_games_cannot_create_player_projections(self):
        p=profile()
        p["teams"]["home"]["prior_games"]=[]
        with self.assertRaises(ValueError):
            simulate(gamefit(),p,ASOF,trials=50)
        p=profile()
        p["teams"]["home"]["players"][0]["role_evidence_reviewed"]=False
        with self.assertRaises(ValueError):
            simulate(gamefit(),p,ASOF,trials=50)

if __name__=="__main__":
    unittest.main()

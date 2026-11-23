"""V15 player scenario safeguards: prior grades only, no invented props."""
import copy
import unittest

from scripts.v15_player_opportunities import STATUS,fit,research_projection
from scripts.v14_player_scenarios import simulate as v14_sim
from tests.test_v14_player_scenarios import forecast
from tests.test_player_prop_conserved_opportunities import gamefit,profile,ASOF


def record(i,stat="rushing_yards",actual=52.):
    return {
        "game_id":str(1000+i),"player_id":"PLAYER-A","stat":stat,
        "first_forecast_observed_utc":"2026-10-01T11:00:00Z",
        "kickoff_utc":"2026-10-02T18:00:00Z",
        "final_observed_utc":"2026-10-03T13:00:00Z",
        "forecast_provenance":"FIRST_FROZEN_PREGAME_PLAYER_PROJECTION",
        "final_provenance":"INDEPENDENT_POSTGAME_ATHLETE_BOX",
        "pregame_player_status":"CONFIRMED_ACTIVE",
        "outcome_stat_observed":True,
        "forecast_sha256":"a"*64,"final_sha256":"b"*64,
        "forecast_yards":44.,"observed_yards":actual}


class V15PlayerModelTests(unittest.TestCase):
    def test_only_first_pregame_real_athlete_results_prior_to_decision(self):
        x=fit([record(i) for i in range(36)],"2026-10-20T16:00:00Z")
        self.assertEqual(x["status"],STATUS)
        self.assertEqual(x["source_paired_observations"],36)
        self.assertTrue(x["categories"]["rushing_yards"]["ready"])
        self.assertGreater(x["categories"]["rushing_yards"]["yard_shift"],0)
        self.assertFalse(x["categories"]["passing_yards"]["ready"])
        self.assertTrue(x["original_simulator_conservation_preserved"])
        self.assertFalse(x["model_promoted"])
        self.assertFalse(x["safe_for_betting"])

    def test_future_player_results_and_unconfirmed_starters_are_rejected(self):
        rows=[record(i) for i in range(36)]
        with self.assertRaisesRegex(ValueError,"after-cutoff"):
            fit(rows,"2026-10-03T11:00:00Z")
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            fit(rows+[copy.deepcopy(rows[0])],"2026-10-20T16:00:00Z")
        bad=copy.deepcopy(rows)
        bad[0]["pregame_player_status"]="UNCONFIRMED_EXPECTED"
        with self.assertRaisesRegex(ValueError,"unconfirmed"):
            fit(bad,"2026-10-20T16:00:00Z")
        bad=copy.deepcopy(rows)
        bad[0]["outcome_stat_observed"]=False
        with self.assertRaisesRegex(ValueError,"unconfirmed"):
            fit(bad,"2026-10-20T16:00:00Z")

    def test_single_aggregated_grade_cannot_masquerade_as_individual_source(self):
        with self.assertRaises(ValueError):
            fit([{"graded_recorded_player_stat_samples":622}],
                "2026-10-20T16:00:00Z")

    def test_attaches_only_separate_research_means_not_rewrites_team_budgets(self):
        original=v14_sim(gamefit(),profile(),forecast(),ASOF,trials=50,seed=44)
        clone=copy.deepcopy(original)
        # This calibration was available before the future scenario starts.
        cal=fit([record(i) for i in range(36)],"2026-10-20T16:00:00Z")
        result=research_projection(original,cal,ASOF)
        self.assertEqual(original,clone)
        self.assertTrue(result["original_team_stat_conservation_preserved"])
        self.assertTrue(result["adjusted_means_are_not_conserved_team_stat_budgets"])
        self.assertEqual(result["original_team_player_opportunities"],
                         original["player_opportunity_scenarios"])
        self.assertTrue(result["player_conditionally_active_projections"])
        self.assertTrue(any(r["stat"]=="rushing_yards" and r["ready"]
                            for r in result["player_conditionally_active_projections"]))
        self.assertFalse(result["model_promoted"])
        self.assertFalse(result["safe_for_betting"])
        self.assertTrue(result["no_sportsbook_prop_lines_generated"])

if __name__=="__main__":
    unittest.main()

"""V12R3 chronological matchup tempo, RZ-trip and field transitions tests."""
import copy
import unittest
import random

from scripts.v10_possession_sim import fit,simulate as simulate_v11
from scripts.v12r3_possession_context import (
    STATUS,fit_context,matchup_pace,next_field,redzone_distribution)
from scripts.v12_regularized_hazards import train,pace_profile
from tests.test_v12_possession_sim import prepared


class R3ContextTests(unittest.TestCase):
    def fixture(self):
        source,model,prior,dated=prepared()
        return source,model,prior,dated,fit_context(source,model,"2026-10-01")

    def test_time_cutoff_and_source_games_are_strict(self):
        games,model,_,_,ctx=self.fixture()
        self.assertEqual(ctx["status"],STATUS)
        self.assertEqual(ctx["source_games"],44)
        self.assertEqual(len(ctx["source_prior_game_ids"]),44)
        extra=copy.deepcopy(games[0])
        extra["game_id"]="new_future"
        extra["date"]="2026-10-01"
        self.assertEqual(fit_context(games+[extra],model,"2026-10-01"),ctx)
        with self.assertRaisesRegex(ValueError,"differs"):
            extra["date"]="2026-09-15"
            fit_context(games+[extra],model,"2026-10-01")
        with self.assertRaises(ValueError):
            fit_context(games,model,"2026-09-30")

    def test_opponent_role_pace_and_source_observations(self):
        _,_,_,_,ctx=self.fixture()
        p=matchup_pace(ctx,"Home","Away")
        self.assertEqual(p["source_cutoff"],"2026-10-01")
        self.assertEqual(p["source_games"],44)
        self.assertGreaterEqual(p["expected_possessions_each"],7)
        self.assertLessEqual(p["expected_possessions_each"],18)
        self.assertEqual(len(p["historical_deviations"]),44)
        self.assertEqual(set(p["team_role_estimates"]),
                         {"home_offense","home_opponent_offense",
                          "away_offense","away_opponent_offense"})
        old=train(prepared()[0],[],"2026-10-01")
        self.assertTrue(pace_profile(old,"Home","Away")["historical_deviations"])

    def test_transition_samples_are_observed_and_event_specific(self):
        _,_,_,_,ctx=self.fixture()
        rng=random.Random(1234)
        for kind,group in ctx["transition"].items():
            self.assertTrue(group["league"] or kind=="RETURN_TD")
            draws=[next_field(ctx,kind,"Home","Away",rng) for _ in range(12)]
            self.assertTrue(all(x in group["league"] for x in draws if x is not None))
        with self.assertRaises(ValueError):
            next_field(ctx,"NOT_A_REAL_RESULT","Home","Away",rng)

    def test_redzone_trip_not_play_success_preserves_turnover(self):
        _,model,prior,dated,ctx=self.fixture()
        self.assertGreater(ctx["rz"]["league"]["trips"],0)
        base={"TD":.27,"FG":.18,"EMPTY":.42,"TURNOVER":.13}
        home=redzone_distribution(ctx,"home","Home","Away","red_zone",base)
        self.assertAlmostEqual(sum(home.values()),1.)
        self.assertAlmostEqual(home["TURNOVER"],base["TURNOVER"])
        self.assertEqual(redzone_distribution(ctx,"home","Home","Away","own_half",base),base)
        with self.assertRaises(ValueError):
            redzone_distribution(ctx,"home","Home","Away","BOGUS",base)

    def test_old_forecast_bitwise_preserved_when_context_disabled(self):
        games,model,prior,dated,ctx=self.fixture()
        base=simulate_v11(model,True,trials=120,seed=345,regress_turnovers=True,
                          v04_prior=prior,dated_profile=dated,return_draws=True)
        no_effect=simulate_v11(model,True,trials=120,seed=345,regress_turnovers=True,
                               v04_prior=prior,dated_profile=dated,return_draws=True,
                               r3_context=ctx)
        self.assertEqual(base,no_effect)
        tempo=matchup_pace(ctx,"Home","Away")
        variants=[dict(pace_override=tempo),
                  dict(pace_override=tempo,r3_context=ctx,r3_field=True),
                  dict(pace_override=tempo,r3_context=ctx,r3_redzone=True),
                  dict(pace_override=tempo,r3_context=ctx,r3_field=True,r3_redzone=True)]
        for args in variants:
            output=simulate_v11(model,True,trials=120,seed=345,
                regress_turnovers=True,v04_prior=prior,dated_profile=dated,
                return_draws=True,trace=True,**args)
            self.assertEqual(len(output["margin_draws"]),120)
            self.assertEqual(len(output["total_draws"]),120)
            self.assertFalse(output["model_promoted"])
            self.assertFalse(output["safe_for_betting"])
        with self.assertRaisesRegex(ValueError,"weekly V04 cutoff"):
            wrong=dict(ctx,cutoff="2026-09-26")
            simulate_v11(model,True,trials=100,seed=2,regress_turnovers=True,
                         v04_prior=prior,dated_profile=dated,
                         r3_context=wrong,r3_redzone=True)

if __name__=="__main__":
    unittest.main()

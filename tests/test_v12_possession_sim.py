"""V12 research acceptance: identical cutoff, empirical RZ trips and calibration."""
import copy
import unittest

from scripts.v10_possession_sim import fit
from scripts.v11_dated_profile_bridge import STATUS as BRIDGE_STATUS
from scripts.weekly_profiles import STATUS as SNAPSHOT_STATUS
from scripts.v12_possession_sim import fit_v12,drive_probabilities,simulate
from scripts.v12_possession_backtest import _crps,_reliability,_distribution_grade
from tests.test_v10_possession_sim import fixtures


def prepared():
    source,advanced=fixtures()
    target={"game_id":"999","home":"Home","away":"Away","date":"2026-10-01"}
    model=fit(source,advanced,target,min_games=35)
    assert model["ready"]
    old={"source":"EARLIER_FOLD_V04","game_id":"999",
         "asof_cutoff":"2026-10-01","home_points":34.,"away_points":17.}
    profile={"status":BRIDGE_STATUS,"game_id":"999",
             "cutoff_date_exclusive":"2026-10-01",
             "historical_source_first_publication_verified":False,
             "scores_reconciled_to_weekly_v04":True,
             "teams":{}}
    for side,team in (("home","Home"),("away","Away")):
        profile["teams"][side]={
            "team":team,"games_before_cutoff":2,"prior_game_ids":["1","2"],
            "weekly_recent_form":{"epa_off_adj":.4,"epa_def_adj":-.1},
            "v04_neutral_strength":1.,"v04_scoring_offense_component":1.,
            "v04_scoring_defense_component":1.,
            "asof_profile_status":SNAPSHOT_STATUS}
    return source,model,old,profile


class V12AcceptanceTests(unittest.TestCase):
    def test_two_stage_redzone_probability_mass_and_real_trip_conditioning(self):
        source,prior,old,dated=prepared()
        fitted=fit_v12(prior,source,old,dated)
        self.assertTrue(fitted["ready"])
        self.assertFalse(fitted["availability_adjustments_applied"])
        self.assertEqual(fitted["availability_evidence"]["qb"],"UNVERIFIED")
        for side in ("home","away"):
            for ytg in (95,75,55,35,15):
                x=drive_probabilities(fitted,side,ytg)
                self.assertGreaterEqual(x["reach_probability"],0)
                self.assertLessEqual(x["reach_probability"],1)
                for reached in (False,True):
                    self.assertAlmostEqual(sum(x["conditional"][reached].values()),
                                           1.,places=8)
            self.assertEqual(drive_probabilities(fitted,side,15)["reach_probability"],1.)
        a=simulate(fitted,trials=120,seed=22,trace=True)
        b=simulate(fitted,trials=120,seed=22,trace=True)
        self.assertEqual(a,b)
        self.assertGreaterEqual(a["expected_home_redzone_trips"],a["expected_home_redzone_tds"])
        self.assertGreaterEqual(a["expected_away_redzone_trips"],a["expected_away_redzone_tds"])
        self.assertTrue(len(a["sample_possessions"])>0)
        self.assertFalse(a["model_promoted"])
        self.assertFalse(a["safe_for_betting"])
        self.assertEqual(len(a["margin_draws"]),120)
        self.assertEqual(len(a["total_draws"]),120)

    def test_future_target_or_profile_mismatch_abstains(self):
        source,prior,old,dated=prepared()
        modified=copy.deepcopy(prior)
        modified["target_date"]="2026-09-26"
        with self.assertRaisesRegex(ValueError,"weekly cutoff"):
            fit_v12(modified,source,old,dated)
        tamper=copy.deepcopy(dated)
        tamper["teams"]["away"]["team"]="Elsewhere"
        with self.assertRaisesRegex(ValueError,"historical team"):
            fit_v12(prior,source,old,tamper)
        tamper=copy.deepcopy(dated)
        tamper["cutoff_date_exclusive"]="2026-10-02"
        with self.assertRaises(ValueError):
            fit_v12(prior,source,old,tamper)
        source[0]["date"]="2026-10-01"
        with self.assertRaisesRegex(ValueError,"differs"):
            fit_v12(prior,source,old,dated)

    def test_stable_distribution_metrics_and_probabilistic_lines(self):
        self.assertAlmostEqual(_crps([0.,2.],1.),.5,places=8)
        self.assertAlmostEqual(_crps([4.,4.],4.),0.,places=8)
        self.assertEqual(_reliability([])["n"],0)
        calibrated=_reliability([(.8,1),(.2,0)])
        self.assertAlmostEqual(calibrated["brier"],.04)
        self.assertGreater(calibrated["log_loss"],0)
        self.assertLess(calibrated["ece"],.25)
        self.assertEqual(len(_reliability([(.2,0),(.9,1)])["bins"]),2)

    def test_weekly_source_prior_not_changed(self):
        source,prior,old,dated=prepared()
        model=fit_v12(prior,source,old,dated)
        forecast=simulate(model,trials=140,seed=88)
        self.assertEqual(model["source_games"],prior["source_prior_games"])
        self.assertFalse(forecast["availability_adjustments_applied"])
        self.assertEqual(model["prior"],old)
        self.assertLessEqual(forecast["margin_p10"],forecast["margin_p90"])
        self.assertLessEqual(forecast["total_p10"],forecast["total_p90"])
        changed=copy.deepcopy(old);changed["game_id"]="888"
        with self.assertRaisesRegex(ValueError,"game identity"):
            fit_v12(prior,source,changed,dated)

if __name__=="__main__":
    unittest.main()

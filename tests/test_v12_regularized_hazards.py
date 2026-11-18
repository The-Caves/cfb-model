"""V12R2 frozen-week, regularized drive-learning and pace ablation tests."""
import copy
import unittest

from scripts.v12_regularized_hazards import (
    STATUS, TASKS, _ridge_logit, _features, train, probabilities, pace_profile
)
from scripts.v12_possession_sim import fit_v12, simulate
from scripts.v10_possession_sim import simulate as simulate_v11
from tests.test_v10_possession_sim import fixtures
from tests.test_v12_possession_sim import prepared


class RegularizedHazardsTests(unittest.TestCase):
    def test_chronological_fit_normalized_and_deterministic(self):
        games, advanced=fixtures()
        cutoff="2026-10-01"
        fit=train(games,[],cutoff)
        self.assertTrue(fit["ready"])
        self.assertEqual(fit["status"],STATUS)
        self.assertEqual(fit["source_games"],44)
        self.assertEqual(fit["feature_coverage"]["training_drives"],44*22)
        self.assertEqual(set(fit["models"]),set(TASKS))
        self.assertFalse(fit["model_promoted"])
        _,base,prior,dated=prepared()
        p=probabilities(fit,"home","own_half","Home","Away",prior,dated)
        self.assertGreater(p["reach_probability"],0)
        self.assertLess(p["reach_probability"],1)
        for reached in (True,False):
            self.assertAlmostEqual(sum(p["conditional"][reached].values()),1.,places=9)
        rz=probabilities(fit,"home","red_zone","Home","Away",prior,dated)
        self.assertEqual(rz["reach_probability"],1.)
        with self.assertRaises(ValueError):
            probabilities(fit,"home","invalid-zone","Home","Away",prior,dated)

    def test_no_future_or_same_week_labels(self):
        games,_=fixtures()
        old=train(games,[],"2026-10-01")
        fake=copy.deepcopy(games[0])
        fake["game_id"]="future"
        fake["date"]="2026-10-01"  # strict original weekly cutoff
        fake["drives"][0]["result"]="TD"
        fake["drives"][0]["offense_points"]=7
        new=train(games+[fake],[],"2026-10-01")
        self.assertEqual(new,old)
        future=copy.deepcopy(fake);future["date"]="2026-10-02"
        self.assertEqual(train(games+[future],[],"2026-10-01"),old)
        stale=copy.deepcopy(games[0]);stale["game_id"]=games[0]["game_id"]
        with self.assertRaisesRegex(ValueError,"Duplicate earlier"):
            train(games+[stale],[],"2026-10-01")

    def test_pit_v04_training_forecast_strict_identity(self):
        games,_=fixtures()
        rec={"game_id":"1","date":games[1]["date"],
             "home":"Home","away":"Away","cutoff":"2026-08-30",
             "v04":{"home_points":30.,"away_points":18.},
             "source_provenance":{"weekly_recent_form":{
                 "home":{"epa_off_adj":.4,"epa_def_adj":-.1},
                 "away":{"epa_off_adj":.2,"epa_def_adj":-.3}}}}
        fit=train(games,[rec],"2026-10-01")
        self.assertGreater(fit["feature_coverage"]["drives_with_original_v04"],0)
        self.assertGreater(fit["feature_coverage"]["drives_with_dated_epa"],0)
        tamper=copy.deepcopy(rec);tamper["home"]="Different"
        with self.assertRaisesRegex(ValueError,"mismatched"):
            train(games,[tamper],"2026-10-01")
        after=copy.deepcopy(rec);after["date"]="2026-10-01"
        after["cutoff"]="2026-09-30"
        with self.assertRaisesRegex(ValueError,"mismatched"):
            train(games,[after],"2026-10-01")

    def test_ridge_shrinkage_no_unseen_team_hallucination(self):
        feats=_features("own_half","Home","Away")
        train_rows=[(feats,i%4==0) for i in range(100)]
        fitted=_ridge_logit(train_rows,"visit")
        self.assertTrue(fitted["ready"])
        self.assertEqual(fitted["n"],100)
        self.assertTrue(all(abs(w)<=2.5 for w in fitted["weights"].values()))
        self.assertFalse(_ridge_logit([], "visit")["ready"])

    def test_trained_ablation_and_observed_pace(self):
        source,base,prior,dated=prepared()
        model=fit_v12(base,source,prior,dated)
        hazards=train(source,[],"2026-10-01")
        pace=pace_profile(hazards,"Home","Away")
        self.assertEqual(pace["home_observed_games"],44)
        self.assertEqual(pace["away_observed_games"],44)
        self.assertGreater(len(pace["historical_deviations"]),0)
        a=simulate(model,trials=100,seed=991,trained_hazards=hazards)
        self.assertTrue(a["learned_drive_hazards_used"])
        self.assertFalse(a["learned_possession_pace_used"])
        self.assertEqual(a,simulate(model,trials=100,seed=991,trained_hazards=hazards))
        b=simulate(model,trials=100,seed=991,trained_hazards=hazards,
                   use_learned_pace=True)
        self.assertTrue(b["learned_possession_pace_used"])
        c=simulate(model,trials=100,seed=991,trained_hazards=hazards,
                   use_learned_pace=True,use_trained_hazards=False)
        self.assertFalse(c["learned_drive_hazards_used"])
        self.assertTrue(c["learned_possession_pace_used"])
        v11=simulate_v11(base,True,trials=100,seed=991,
                         regress_turnovers=True,v04_prior=prior,
                         dated_profile=dated,return_draws=True,
                         pace_override=pace)
        self.assertTrue(v11["learned_pace_override_used"])
        self.assertEqual(len(v11["margin_draws"]),100)
        self.assertFalse(b["model_promoted"])
        self.assertFalse(b["safe_for_betting"])
        with self.assertRaisesRegex(ValueError,"requires"):
            simulate(model,trials=100,use_learned_pace=True)
        bad=copy.deepcopy(hazards);bad["cutoff"]="2026-09-27"
        with self.assertRaisesRegex(ValueError,"weekly cutoff"):
            simulate(model,trials=100,trained_hazards=bad)

if __name__=="__main__":
    unittest.main()

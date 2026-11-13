"""V11 weekly V04 bridge, as-of source integrity, and drive hazards."""
import copy
import unittest
from unittest.mock import patch

from scripts.v11_dated_profile_bridge import (
    bridge, verify_for_target, STATUS as PROFILE_BRIDGE,
)
from scripts.v10_possession_sim import fit, simulate, outcome_distribution
from scripts.weekly_profiles import STATUS as SNAPSHOT_STATUS
from scripts.v04_direct_scores import STATUS as V04_STATUS
from tests.test_v10_possession_sim import fixtures


def sample_profile():
    return {
        "status":PROFILE_BRIDGE,"game_id":"999",
        "cutoff_date_exclusive":"2026-09-26",
        "historical_source_first_publication_verified":False,
        "scores_reconciled_to_weekly_v04":True,
        "teams":{
            "home":{
              "team":"Home","games_before_cutoff":3,
              "prior_game_ids":["1","2","3"],
              "weekly_recent_form":{"epa_off_adj":1.2,
                                    "epa_def_adj":-.45,
                                    "win":.75,"points_for":32.},
              "v04_neutral_strength":7.2,
              "v04_scoring_offense_component":2.3,
              "v04_scoring_defense_component":-1.1,
              "asof_profile_status":SNAPSHOT_STATUS,
            },
            "away":{
              "team":"Away","games_before_cutoff":3,
              "prior_game_ids":["4","5","6"],
              "weekly_recent_form":{"epa_off_adj":-.7,
                                    "epa_def_adj":.8,
                                    "win":.25,"points_for":19.},
              "v04_neutral_strength":-5.5,
              "v04_scoring_offense_component":-2.5,
              "v04_scoring_defense_component":1.4,
              "asof_profile_status":SNAPSHOT_STATUS,
            },
        },
    }


class V11DatedProfileTests(unittest.TestCase):
    def test_v04_prior_same_week_and_team_profile_changes_drive_hazards(self):
        drives,advanced=fixtures()
        target={"game_id":"999","home":"Home","away":"Away","date":"2026-10-01"}
        model=fit(drives,advanced,target,min_games=35)
        source={"source":"EARLIER_FOLD_V04","game_id":"999","asof_cutoff":"2026-09-26",
                "home_points":35.,"away_points":18.}
        profile=sample_profile()
        self.assertTrue(verify_for_target(profile,dict(target,cutoff="2026-09-26")))
        original=outcome_distribution(model,"home",75,True,True,source)
        updated=outcome_distribution(model,"home",75,True,True,source,profile)
        self.assertNotAlmostEqual(original["TD"],updated["TD"],places=6)
        self.assertAlmostEqual(sum(updated.values()),1.,places=7)
        a=simulate(model,True,trials=140,seed=321,
                   regress_turnovers=True,v04_prior=source)
        b=simulate(model,True,trials=140,seed=321,
                   regress_turnovers=True,v04_prior=source,
                   dated_profile=profile)
        self.assertTrue(b["dated_v04_team_profile_used"])
        self.assertFalse(a["dated_v04_team_profile_used"])
        self.assertTrue(b["v04_prior_used"])
        self.assertFalse(b["model_promoted"])
        self.assertEqual(b,simulate(model,True,trials=140,seed=321,
                         regress_turnovers=True,v04_prior=source,
                         dated_profile=profile))

    def test_wrong_team_cutoff_and_future_date_blocked(self):
        drives,advanced=fixtures()
        target={"game_id":"999","home":"Home","away":"Away","date":"2026-10-01"}
        model=fit(drives,advanced,target,min_games=35)
        src={"source":"EARLIER_FOLD_V04","game_id":"999",
             "asof_cutoff":"2026-09-26","home_points":35.,"away_points":18.}
        p=sample_profile()
        for mutation in (
            {"game_id":"555"},
            {"cutoff_date_exclusive":"2026-09-19"},
            {"historical_source_first_publication_verified":True},
        ):
            broken=dict(p,**mutation)
            with self.assertRaises(ValueError):
                simulate(model,True,trials=100,v04_prior=src,
                         dated_profile=broken)
        with self.assertRaises(ValueError):
            simulate(model,True,trials=100,v04_prior=dict(src,asof_cutoff="2026-10-02"),
                     dated_profile=p)
        q=copy.deepcopy(p);q["teams"]["away"]["team"]="Other"
        with self.assertRaises(ValueError):
            simulate(model,True,trials=100,v04_prior=src,dated_profile=q)

    def test_bridge_refits_from_earlier_week_and_checks_original_v04(self):
        cutoff="2026-09-26"
        source=[
          {"game_id":"1","date":"2026-09-19","home":"Home","away":"Away",
           "home_score":"24","away_score":"10","neutral":"False"},
          {"game_id":"999","date":"2026-10-01","home":"Home","away":"Away",
           "home_score":"14","away_score":"30","neutral":"False"},
        ]
        snap={"evidence_status":SNAPSHOT_STATUS,
              "historical_publication_times_verified":False,
              "cutoff_date_exclusive":cutoff,
              "profiles":[
                {"team":"Home","games_before_cutoff":1,"prior_game_ids":["1"],
                 "recent_form":{"epa_off_adj":.2}},
                {"team":"Away","games_before_cutoff":1,"prior_game_ids":["1"],
                 "recent_form":{"epa_def_adj":.1}}]}
        model={"status":V04_STATUS,"historical_first_publication_verified":False,
             "n_training_games":1,"scoring_intercept":24.,
             "home_field_points":2.5,
             "neutral_team_strength":{"Home":3.,"Away":-3.},
             "offense":{"Home":2.,"Away":-2.},
             "defense":{"Home":-1.,"Away":1.}}
        target={"game_id":"999","home":"Home","away":"Away","cutoff":cutoff,
                "home_points":30.,"away_points":20.}
        with patch("scripts.v11_dated_profile_bridge.load_inputs",
                   return_value=(source,{},{"historical_pregame_availability_verified":False})),\
             patch("scripts.v11_dated_profile_bridge.build_snapshots",
                   return_value=[snap]),\
             patch("scripts.v11_dated_profile_bridge.fit_v04",return_value=model) as fit_model,\
             patch("scripts.v11_dated_profile_bridge.predict_v04",
                   return_value={"home_points":30.,"away_points":20.}):
            out=bridge("game.csv","advanced.csv","manifest.json",[target])
            self.assertEqual(out["target_games"],1)
            self.assertEqual(out["profiles"]["999"]["teams"]["home"]["prior_game_ids"],["1"])
            self.assertFalse(out["historical_publication_verified"])
            self.assertEqual(fit_model.call_args[0][0],source[:1])
            with self.assertRaisesRegex(ValueError,"differs"):
                bridge("game.csv","advanced.csv","manifest.json",
                       [dict(target,home_points=38.)])

if __name__=="__main__":
    unittest.main()

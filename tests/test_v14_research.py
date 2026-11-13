"""V14 source-cutoff, regularized residual and player-line integrity gates."""
import copy
import datetime as dt
import unittest

from scripts.v14_matchup_features import FEATURES,load_inputs,profile,matchup,STATUS as FSTATUS
from scripts.v14_residual_challenger import (
    fit as fit_score,project,STATUS as SCORE,VARIANTS)
from scripts.v14_ats_totals_calibration import (
    fit as fit_prob,predict as prob,brier,STATUS as CALSTATUS)


def prior(i,week="2026-10-03",status=True):
    f={name:0.15 for name in FEATURES}
    return {"game_id":str(i),"date":week,"cutoff":week,
        "v04":{"home_points":28.,"away_points":21.,"margin":7.,"total":49.},
        "matchup":{"ready":status,"status":FSTATUS,"cutoff":week,
                   "features":f},
        "final_home":30+i%4,"final_away":22+i%3}


class V14Core(unittest.TestCase):
    def test_original_v04_scores_and_capped_close_game_adjustments(self):
        hist=[prior(i,"2026-09-26" if i%2 else "2026-10-03")
              for i in range(90)]
        model=fit_score(hist,"2026-10-10")
        self.assertEqual(model["status"],SCORE)
        self.assertTrue(model["models"]["margin"]["ready"])
        baseline=copy.deepcopy(hist[0]["v04"])
        p=project(baseline,hist[0]["matchup"]|{"cutoff":"2026-10-10"},
                  model,"2026-10-10",variant="joint_close")
        self.assertEqual(hist[0]["v04"],baseline)
        self.assertLessEqual(abs(p["margin_adjustment"]),6.)
        self.assertLessEqual(abs(p["total_adjustment"]),6.)
        self.assertFalse(p["model_promoted"])
        self.assertFalse(p["safe_for_betting"])
        self.assertTrue(p["matchup_evidence_ready"])
        for name in VARIANTS:
            other=project(baseline,hist[0]["matchup"]|{"cutoff":"2026-10-10"},
                          model,"2026-10-10",variant=name)
            self.assertAlmostEqual(other["home_points"]+other["away_points"],
                                   other["total"],places=4)
            self.assertAlmostEqual(other["home_points"]-other["away_points"],
                                   other["margin"],places=4)

    def test_model_never_uses_target_week_or_future_game_scores(self):
        rows=[prior(i,"2026-09-26" if i%2 else "2026-10-03") for i in range(70)]
        m=fit_score(rows,"2026-10-10")
        future=prior(100,"2026-10-10")
        with self.assertRaisesRegex(ValueError,"current/future"):
            fit_score(rows+[future],"2026-10-10")
        future["date"]="2026-10-11"
        with self.assertRaises(ValueError):
            fit_score(rows+[future],"2026-10-10")
        with self.assertRaisesRegex(ValueError,"duplicate"):
            fit_score(rows+[rows[0]],"2026-10-10")
        self.assertEqual(m,fit_score(rows,"2026-10-10"))

    def test_earlier_out_of_fold_betting_calibration_and_quote_no_inference(self):
        x={"game_id":"3","cutoff":"2026-10-03","date":"2026-10-03",
           "source_first_publication_authenticated":False,
           "v14_forecast":{"model_promoted":False,
                "source_cutoff_exclusive":"2026-10-03",
                "margin":7.,"total":49.},
           "final_home":28,"final_away":21}
        fit=fit_prob([x],"2026-10-10")
        self.assertEqual(fit["status"],CALSTATUS)
        self.assertEqual(fit["earlier_oos_games"],1)
        pred={"model_promoted":False,"source_cutoff_exclusive":"2026-10-10",
              "margin":7.,"total":49.}
        out=prob(pred,fit,market={"home_spread":-6.5,"total":50.5})
        self.assertIsNotNone(out["home_cover_probability"])
        self.assertLess(out["over_probability"],.5)
        self.assertFalse(out["safe_for_betting"])
        self.assertEqual(out["betting_status"],"PASS_UNVALIDATED")
        missing=prob(pred,fit)
        self.assertIsNone(missing["home_cover_probability"])
        self.assertIsNone(missing["over_probability"])
        bad=copy.deepcopy(x);bad["cutoff"]="2026-10-10"
        with self.assertRaisesRegex(ValueError,"Same-week"):
            fit_prob([bad],"2026-10-10")
        self.assertEqual(brier([(.8,1),(.2,0)])["brier"],.04)

    def test_historical_pbp_missing_is_abstained_not_zero(self):
        games=[]
        turns=[]
        for day in range(1,5):
            gid=str(day)
            for team,opp in (("Home","Away"),("Away","Home")):
                games.append({"game_id":gid,"team":team,"opponent":opp,
                    "date":f"2026-09-0{day}","pass_epa_sum":"10",
                    "pass_epa_plays":"30","rush_epa_sum":"5",
                    "rush_epa_plays":"20","pressure_count":"4",
                    "pressure_observed":"25","explosive_pass":"3",
                    "pass_plays":"30","scrimmage_plays":"50",
                    "redzone_success":"2","redzone_plays":"4"})
                turns.append({"game_id":gid,"team":team,
                    "turnovers_committed":1,"takeaways_observed":1,
                    "historical_pregame_publication_verified":False})
        source=load_inputs(games,{"status":
            "ESPN_COMPLETED_BOXSCORE_TURNOVERS_RESEARCH_ONLY",
            "historical_publication_times_verified":False,
            "safe_for_betting":False,"model_promoted":False,"rows":turns})
        old=profile(source,"2026-09-05")
        self.assertTrue(matchup(old,"Home","Away")["ready"])
        sample=copy.deepcopy(games[0]);sample["game_id"]="new"
        sample["date"]="2026-09-06"
        source2=load_inputs(games+[sample],{"status":
            "ESPN_COMPLETED_BOXSCORE_TURNOVERS_RESEARCH_ONLY",
            "historical_publication_times_verified":False,
            "safe_for_betting":False,"model_promoted":False,"rows":turns})
        self.assertEqual(old,profile(source2,"2026-09-05"))
        sample["date"]="2026-09-02"
        earlier=profile(source2,"2026-09-05")
        self.assertTrue(matchup(earlier,"Home","Away")["ready"])

if __name__=="__main__":
    unittest.main()

"""V15 rejection tests: no target leakage, caps, unchanged scored parents."""
import copy
import unittest

from scripts.v14_matchup_features import STATUS as MATCH_STATUS
from scripts.v15_residual_challengers import STATUS, VARIANTS,fit,project


def row(i,cutoff="2026-09-26",date="2026-09-26",match=True,actual_total=55):
    return {
        "game_id":str(i),"cutoff":cutoff,"date":date,
        "forecasts":{"joint_close":{"margin":3.,"total":50.}},
        "final_home":int((actual_total+3)//2),
        "final_away":int((actual_total-3)//2),
        "matchup":{"ready":True,"status":MATCH_STATUS,
                   "cutoff":cutoff,
                   "historical_first_publication_authenticated":False,
                   "features":{"game_pace":.5,"pass_matchup":.3,
                    "pressure_pass":-.5,"turnover_quality":.4}}
                  if match else {"ready":False,"cutoff":cutoff}
    }


class V15Regression(unittest.TestCase):
    def test_whole_week_cutoff_rejects_future_same_week_and_duplicates(self):
        prior=[row(i) for i in range(70)]
        model=fit(prior,"2026-10-03")
        self.assertEqual(model["prior_games"],70)
        self.assertTrue(all(model["models"][k]["ready"] for k in
                            ("totals_bias","totals_pace","close_margin")))
        with self.assertRaisesRegex(ValueError,"same-week"):
            fit(prior+[row(71,cutoff="2026-10-03",date="2026-10-03")],
                "2026-10-03")
        with self.assertRaisesRegex(ValueError,"same-week"):
            fit(prior+[row(71,cutoff="2026-09-26",date="2026-10-04")],
                "2026-10-03")
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            fit(prior+[copy.deepcopy(prior[0])],"2026-10-03")
        self.assertNotEqual(
            fit([row(i,actual_total=45) for i in range(70)],"2026-10-03")
            ["models"]["totals_bias"]["weights"],
            model["models"]["totals_bias"]["weights"])

    def test_baseline_untouched_and_projected_scores_coherent(self):
        prior=[row(i) for i in range(70)]
        train=fit(prior,"2026-10-03")
        target=row(99,cutoff="2026-10-03",date="2026-10-03")
        before=copy.deepcopy(target)
        for name in VARIANTS:
            output=project(target,train,name)
            self.assertEqual(output["status"],STATUS)
            self.assertLessEqual(abs(output["margin_correction"]),3.00001)
            self.assertLessEqual(abs(output["total_correction"]),4.00001)
            self.assertAlmostEqual(
                output["home_points"]+output["away_points"],
                output["total"],places=4)
            self.assertAlmostEqual(
                output["home_points"]-output["away_points"],
                output["margin"],places=4)
            self.assertFalse(output["model_promoted"])
            self.assertFalse(output["safe_for_betting"])
            self.assertFalse(output["website_scores_replaced"])
        self.assertEqual(target,before)
        self.assertEqual(project(target,train,"totals_bias")["margin"],3.)
        self.assertEqual(project(target,train,"close_margin")["total"],50.)

    def test_missing_features_cannot_be_invented(self):
        prior=[row(i,match=False) for i in range(70)]
        train=fit(prior,"2026-10-03")
        self.assertFalse(train["models"]["totals_pace"]["ready"])
        self.assertFalse(train["models"]["close_margin"]["ready"])
        target=row(101,cutoff="2026-10-03",date="2026-10-03",match=False)
        pred=project(target,train,"combined")
        self.assertEqual(pred["margin"],3.)
        self.assertEqual(pred["total"],50.)
        self.assertTrue(train["models"]["totals_bias"]["ready"])
        self.assertGreater(project(target,train,"totals_bias")["total"],50.)

    def test_bad_matchup_and_mismatched_cutoff_fail_closed(self):
        train=fit([row(i) for i in range(70)],"2026-10-03")
        target=row(101,cutoff="2026-10-03",date="2026-10-03")
        with self.assertRaisesRegex(ValueError,"cutoffs"):
            project(target,train,"garbage")
        wrong=copy.deepcopy(target)
        wrong["matchup"]["historical_first_publication_authenticated"]=True
        with self.assertRaisesRegex(ValueError,"source-dated"):
            project(wrong,train,"combined")
        wrong=copy.deepcopy(target);wrong["cutoff"]="2026-10-10"
        with self.assertRaises(ValueError):
            project(wrong,train,"combined")

if __name__=="__main__":
    unittest.main()

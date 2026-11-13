"""Acceptance tests: V13 source-only V04 scoring and past-week uncertainty."""
import copy
import math
import unittest

from scripts.v13_v04_probabilities import (
    STATUS, V04_MODEL, V04_STATUS, scores, fit_uncertainty, predict, crps
)


def game(gid="1",week="2026-09-26",date="2026-09-26",actual_home=31,actual_away=20):
    return {"game_id":gid,"cutoff":week,"date":date,
            "v04":{"home_points":28.,"away_points":20.,"margin":8.,"total":48.},
            "final_home":actual_home,"final_away":actual_away}


class V13Acceptance(unittest.TestCase):
    def test_no_current_or_future_games_enter_training(self):
        earlier=[game("1","2026-09-26","2026-09-26"),
                 game("2","2026-10-03","2026-10-03")]
        x=fit_uncertainty(earlier,"2026-10-10")
        self.assertEqual(x["earlier_games"],2)
        self.assertEqual(x["earlier_weeks"],2)
        future=game("3","2026-10-10","2026-10-10")
        with self.assertRaisesRegex(ValueError,"Same-week"):
            fit_uncertainty(earlier+[future],"2026-10-10")
        bad=game("4","2026-10-03","2026-10-11")
        with self.assertRaisesRegex(ValueError,"Uncompleted"):
            fit_uncertainty(earlier+[bad],"2026-10-10")
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            fit_uncertainty(earlier+[copy.deepcopy(earlier[0])],"2026-10-10")
        later=copy.deepcopy(earlier)
        later[1]["final_home"]=100
        self.assertNotEqual(x["total_sd"],
                            fit_uncertainty(later,"2026-10-10")["total_sd"])
        old=fit_uncertainty(earlier[:1],"2026-10-03")
        self.assertNotEqual(old["cutoff_exclusive"],x["cutoff_exclusive"])

    def test_anchoring_probabilities_and_optional_lines(self):
        c=fit_uncertainty([game()],"2026-10-03")
        source={"home_points":28.,"away_points":20.,"margin":8.,"total":48.}
        a=predict(source,c,"2026-10-03","prior_variance")
        self.assertEqual(a["status"],STATUS)
        self.assertEqual(a["margin_mean"],8)
        self.assertEqual(a["total_mean"],48)
        self.assertTrue(a["v04_mean_scores_unchanged"])
        self.assertIsNone(a["home_cover_probability"])
        self.assertIsNone(a["over_probability"])
        b=predict(source,c,"2026-10-03",market={"home_spread":-7.,
                                                   "total":50.})
        self.assertGreater(b["home_cover_probability"],.5)
        self.assertLess(b["over_probability"],.5)
        self.assertAlmostEqual(sum((b[k] for k in ("home_points_mean",
                      "away_points_mean"))),48.,places=4)
        self.assertFalse(b["model_promoted"])
        self.assertFalse(b["calibration_prospectively_proven"])
        self.assertFalse(b["safe_for_betting"])
        self.assertEqual(b["betting_status"],"PASS_UNVALIDATED")
        self.assertLess(b["margin_p10"],b["margin_p90"])
        self.assertEqual(a,predict(source,c,"2026-10-03"))

    def test_source_verification_fail_closed(self):
        x=game()["v04"]
        c=fit_uncertainty([],"2026-10-03")
        with self.assertRaisesRegex(ValueError,"earlier source-aligned"):
            predict(x,c,"2026-10-10")
        with self.assertRaisesRegex(ValueError,"Unknown"):
            predict(x,c,"2026-10-03","unrecognized")
        bad=dict(x,home_points=42)
        with self.assertRaisesRegex(ValueError,"incoherent"):
            predict(bad,c,"2026-10-03")
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            predict(x,c,"2026-10-03",site=True)
        valid=dict(x,status=V04_STATUS,model=V04_MODEL,model_promoted=False,
                   direct_scoring_fit_uses_v03_total=False,
                   no_market_lines_in_training=True)
        self.assertEqual(predict(valid,c,"2026-10-03",site=True)["margin_mean"],8)
        tampered=dict(valid,model_promoted=True)
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            predict(tampered,c,"2026-10-03",site=True)

    def test_probabilistic_score_properties(self):
        self.assertAlmostEqual(crps(0.,0.,1.),
                               (math.sqrt(2)-1)/math.sqrt(math.pi),places=7)
        self.assertLess(crps(0.,0.,15.),crps(35.,0.,15.))
        self.assertTrue(math.isfinite(crps(200.,40.,20.)))
        with self.assertRaises(ValueError):crps(0.,0.,0.)
        c=fit_uncertainty([],"2026-10-03")
        x=game()["v04"]
        a=predict(x,c,"2026-10-03","fixed")
        b=predict(x,c,"2026-10-03","prior_variance")
        self.assertEqual(a["home_win_probability"],b["home_win_probability"])
        self.assertEqual(a["total_p90"],b["total_p90"])

    def test_research_ablation_rejects_mismatched_v11_week(self):
        c=fit_uncertainty([],"2026-10-03")
        x=game()["v04"]
        with self.assertRaisesRegex(ValueError,"original weekly"):
            predict(x,c,"2026-10-03","blend10",{"cutoff":"2026-09-26",
                                                  "game_id":"1","margin":8,"total":48})
        v={"cutoff":"2026-10-03","game_id":"1","margin":10.,
           "total":48.5,"margin_width":38.,"total_width":42.}
        output=predict(x,c,"2026-10-03","blend10",v)
        self.assertFalse(output["v04_mean_scores_unchanged"])
        self.assertAlmostEqual(output["margin_mean"],8.2,places=6)
        self.assertTrue(predict(x,c,"2026-10-03","v11_width",v)
                        ["v04_mean_scores_unchanged"])

if __name__=="__main__":
    unittest.main()

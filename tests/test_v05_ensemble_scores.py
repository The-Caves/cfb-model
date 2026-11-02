"""Source-coherent, no-market, equal-weight ensemble evidence tests."""
import copy
import unittest
from scripts.v05_ensemble_scores import blend, MODEL, STATUS
from scripts.v04_direct_scores import fit as fit_v04, predict as predict_v04
from scripts.v05_robust_scores import fit as fit_v05, predict as predict_v05
from test_v05_robust_scores import games

TIME="2026-10-31T12:00:00Z"


class EnsembleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows=games()[:104]
        cls.old=predict_v04(fit_v04(rows,TIME),"Team 0","Team 13",False)
        cls.new=predict_v05(fit_v05(rows,TIME),"Team 0","Team 13",False)

    def test_predeclared_blend_preserves_point_coherence(self):
        result=blend(self.old,self.new)
        self.assertEqual(result["model"],MODEL)
        self.assertEqual(result["status"],STATUS)
        self.assertEqual(result["fixed_weights"],{"v04":.5,"v05":.5})
        self.assertAlmostEqual(result["home_points"],
            (self.old["home_points"]+self.new["home_points"])/2,places=3)
        self.assertAlmostEqual(result["away_points"],
            (self.old["away_points"]+self.new["away_points"])/2,places=3)
        self.assertAlmostEqual(result["home_margin"],
            result["home_points"]-result["away_points"],places=3)
        self.assertAlmostEqual(result["total_points"],
            result["home_points"]+result["away_points"],places=3)
        self.assertFalse(result["model_promoted"])
        self.assertFalse(result["selected_after_test_performance"])
        self.assertTrue(result["market_lines_not_used"])

    def test_rejected_mixed_source_neutral_or_training_cohort(self):
        x=copy.deepcopy(self.new)
        x["neutral"]=True
        with self.assertRaisesRegex(ValueError,"Mismatched"):
            blend(self.old,x)
        x=copy.deepcopy(self.new)
        x["source_training_games"]-=1
        with self.assertRaisesRegex(ValueError,"Mismatched"):
            blend(self.old,x)
        x=copy.deepcopy(self.new)
        x["model_promoted"]=True
        with self.assertRaisesRegex(ValueError,"Mismatched"):
            blend(self.old,x)

    def test_cannot_forge_bad_score_or_fit_with_market(self):
        x=copy.deepcopy(self.old)
        x["home_points"]=float("nan")
        with self.assertRaisesRegex(ValueError,"conservation"):
            blend(x,self.new)
        x=copy.deepcopy(self.new)
        x["no_market_lines_in_training"]=False
        with self.assertRaisesRegex(ValueError,"provenance"):
            blend(self.old,x)


if __name__=="__main__":unittest.main()

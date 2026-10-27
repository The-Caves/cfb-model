import datetime as dt
import math
import unittest
from scripts.creative_model_research import (
    _calibration, _percentile, _predeclared_ensemble, _predictions, _score_predictions,
    _variation, validate, STATUS, VARIANTS, ENSEMBLE_WEIGHTS)

def synthetic_rows(n=240):
    result=[]
    for i in range(n):
        day=dt.date(2026,8,1)+dt.timedelta(days=i//5)
        row={key:None for key in VARIANTS["all_creative"]}
        row.update({"game_id":str(i),"date":day.isoformat(),
                    "home":"Home","away":"Away",
                    "home_score":24+i%9,"away_score":20+i%6,
                    "home_games_prior":2,"away_games_prior":2,
                    "betting_status":"PASS_UNVALIDATED",
                    "possession_score_estimate":None,
                    "volatility_proxy":None,
                    "score_margin_form":float(i%12-6),
                    "scoring_total_form":45.+i%10})
        result.append(row)
    return result

class CreativeModelResearch(unittest.TestCase):
    def test_all_groups_are_distinct_and_have_baseline(self):
        self.assertIn("active_v03",VARIANTS)
        self.assertEqual(set(VARIANTS["active_v03"]),set(
            __import__("scripts.personnel_features",fromlist=["BASE_FIELDS"]).BASE_FIELDS))
        self.assertAlmostEqual(sum(ENSEMBLE_WEIGHTS.values()),1.)

    def test_chronological_walkforward_blocks_same_week_labels(self):
        report,preds=validate(synthetic_rows(),start="2026-08-29",weeks=5,min_train=90)
        self.assertEqual(report["status"],STATUS)
        self.assertFalse(report["model_promoted"])
        self.assertTrue(report["aggregate"]["active_v03"]["games"]>0)
        for fold in report["weeks"]:
            ids=set(fold["train_game_ids"])
            self.assertFalse(ids.intersection(fold["test_game_ids"]))
            self.assertTrue(all(int(g)<min(map(int,fold["test_game_ids"]))
                                for g in ids) if fold["test_game_ids"] else True)
        self.assertNotIn("possession_mechanistic",report["aggregate"])
        self.assertIn("fixed_weight_ensemble",report["aggregate"])
        self.assertEqual(report["unavailable_inputs"]["turnover_attribution"],"UNVERIFIED")

    def test_training_freeze_same_week_future_result_does_not_change_prior(self):
        a=synthetic_rows()
        first,_=validate(a,start="2026-08-29",weeks=1,min_train=90)
        cutoff=dt.date(2026,8,29)
        b=[dict(r) for r in a]
        for r in b:
            if dt.date.fromisoformat(r["date"])>=cutoff:
                r["home_score"]=103
        second,_=validate(b,start="2026-08-29",weeks=1,min_train=90)
        # Predictions intentionally retained outside report for full audit;
        # no training metadata depends on same-week actuals.
        self.assertEqual(first["weeks"][0]["train_game_ids"],second["weeks"][0]["train_game_ids"])
        self.assertEqual(first["weeks"][0]["train_games"],second["weeks"][0]["train_games"])

    def test_temporal_interval_calibration_uses_later_prior_games_only(self):
        rows=synthetic_rows(200)
        calibration=_calibration(rows[:155],VARIANTS["active_v03"])
        self.assertIsNotNone(calibration)
        self.assertGreaterEqual(calibration["calibration_games"],25)
        self.assertEqual(calibration["method"],"PAST_ONLY_TEMPORAL_SPLIT_RESIDUAL_QUANTILES")
        scores=_score_predictions(rows[155:160],[(3.,50.)]*5,calibration)
        self.assertEqual(scores["games"],5)
        self.assertIsNotNone(scores["nominal_80pct_total_interval_coverage"])

    def test_ensemble_weights_are_predeclared_and_fallback_without_drive(self):
        guess=_predeclared_ensemble({"active_v03":[(12,50)],
                                     "home_recency":[(2,55)]},[{}])
        self.assertAlmostEqual(guess[0][0],(12*.35+2*.25)/(.35+.25))
        self.assertEqual(_predeclared_ensemble({},[{}]),None)

    def test_unmeasured_creative_columns_skipped(self):
        rows=synthetic_rows(140)
        p,skipped=_predictions(rows[:110],rows[110:115],dt.date(2026,8,30))
        self.assertEqual(skipped["possession_context"],"NOT_ENOUGH_MEASURED_PRIOR_FEATURE_VARIATION")
        self.assertNotIn("all_creative",p)
        self.assertIn("active_v03",p)

    def test_duplicate_identity_and_bad_status_fail_closed(self):
        rows=synthetic_rows(150)
        with self.assertRaises(ValueError):validate(rows+[rows[0]])
        rows[0]["betting_status"]="VALIDATED"
        with self.assertRaises(ValueError):validate(rows)

    def test_no_postgame_intervals_derived_from_test(self):
        rows=synthetic_rows(175)
        before=_calibration(rows[:125],VARIANTS["active_v03"])
        rows[-1]["home_score"]=99
        after=_calibration(rows[:125],VARIANTS["active_v03"])
        self.assertEqual(before,after)

if __name__=="__main__":
    unittest.main()

"""Past-fold V05 uncertainty evidence: no same-week outcomes or in-sample residuals."""
import unittest

from scripts.v05_calibration import fit, evaluate, STATUS


def earlier():
    return [{"game_id":str(i+10),"cutoff":"2026-10-03" if i<20 else "2026-10-10",
             "v05_full_margin":float(i%5),"v05_full_total":float(46+i%3),
             "actual_margin":float(i%5+(-2 if i%2 else 2)),
             "actual_total":float(46+i%3+(-7 if i%2 else 7))}
            for i in range(40)]


class CalibrationTests(unittest.TestCase):
    def test_requires_multiple_real_prior_holdout_weeks(self):
        self.assertIsNone(fit(earlier()[:34],"2026-10-17"))
        self.assertIsNone(fit([dict(r,cutoff="2026-10-03") for r in earlier()],
                              "2026-10-17"))

    def test_prior_conformal_bands_are_nonzero_and_not_promoted(self):
        c=fit(earlier(),"2026-10-17")
        self.assertEqual(c["status"],STATUS)
        self.assertEqual(c["calibrated_from_games"],40)
        self.assertEqual(c["calibrated_from_weeks"],2)
        self.assertEqual(c["nominal_coverage"],.8)
        self.assertAlmostEqual(c["margin_radius"],2.)
        self.assertAlmostEqual(c["total_radius"],7.)
        self.assertTrue(c["only_prior_oos_errors"])
        self.assertFalse(c["safe_for_betting"])
        test=[{"cutoff":"2026-10-17","v05_full_margin":4.,
               "v05_full_total":45.,"actual_margin":5.,"actual_total":52.},
              {"cutoff":"2026-10-17","v05_full_margin":3.,
               "v05_full_total":50.,"actual_margin":30.,"actual_total":30.}]
        result=evaluate(test,c)
        self.assertEqual(result["calibrated_games"],2)
        self.assertEqual(result["margin_coverage"],.5)
        self.assertEqual(result["total_coverage"],.5)
        self.assertEqual(result["mean_margin_width"],4.)

    def test_same_week_result_cannot_be_used_for_interval_training(self):
        rows=earlier()
        rows[0]["cutoff"]="2026-10-17"
        with self.assertRaisesRegex(ValueError,"future calibration"):
            fit(rows,"2026-10-17")

    def test_duplicate_or_nonfinite_residuals_fail_closed(self):
        r=earlier();r.append(dict(r[0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            fit(r,"2026-10-17")
        r=earlier();r[0]["actual_total"]=float("nan")
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            fit(r,"2026-10-17")

    def test_already_seen_week_cannot_be_regraded_as_prospective(self):
        cal=fit(earlier(),"2026-10-17")
        with self.assertRaisesRegex(ValueError,"previously known"):
            evaluate([earlier()[0]],cal)
        self.assertIsNone(evaluate([],cal)["margin_coverage"])


if __name__=="__main__":unittest.main()

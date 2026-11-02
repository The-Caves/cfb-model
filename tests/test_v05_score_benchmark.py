"""Paired historical V04/V05 folds: identities, ablation and leakage guards."""
import copy
import unittest

from scripts.v05_score_benchmark import evaluate, STATUS, VARIANTS
from test_v05_robust_scores import games


class BenchmarkTests(unittest.TestCase):
    def test_all_variants_exact_same_holdout_game_ids(self):
        report=evaluate(games(),start="2026-10-17",weeks=2)
        self.assertEqual(report["status"],STATUS)
        self.assertEqual(report["n_folds"],2)
        self.assertEqual(report["matched_games"],26)
        self.assertEqual(len({r["game_id"] for r in report["predictions"]}),26)
        self.assertFalse(report["score_model_promoted"])
        self.assertTrue(report["same_team_and_game_ids_for_all_models"])
        self.assertEqual(set(report["models"]),set(VARIANTS))
        for name in VARIANTS:
            self.assertEqual(report["models"][name]["games"],26)
        self.assertEqual(report["folds"][0]["training_games"],91)
        self.assertEqual(report["folds"][1]["training_games"],104)
        self.assertTrue(all(x["v05_full_total"]>=20. for x in report["predictions"]))

    def test_future_targets_cannot_change_predictions(self):
        baseline=evaluate(games(),start="2026-10-24",weeks=1)
        forged=games()
        for row in forged:
            if row["date"]=="2026-10-24":
                row["home_score"]=199
                row["away_score"]=0
        after=evaluate(forged,start="2026-10-24",weeks=1)
        self.assertEqual(
            [(r["game_id"],r["v05_full_margin"],r["v05_full_total"])
             for r in baseline["predictions"]],
            [(r["game_id"],r["v05_full_margin"],r["v05_full_total"])
             for r in after["predictions"]])
        self.assertNotEqual(
            baseline["predictions"][0]["actual_margin"],
            after["predictions"][0]["actual_margin"])

    def test_duplicate_game_and_bad_final_fail_closed(self):
        rows=games(); rows.append(copy.deepcopy(rows[0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            evaluate(rows)
        rows=games(); rows[0]["home_score"]=-1
        with self.assertRaisesRegex(ValueError,"Unverified"):
            evaluate(rows)

    def test_same_day_entire_fold_embargo_even_if_early_game_final(self):
        rows=games()
        first=evaluate(rows,start="2026-10-24",weeks=1)["predictions"]
        for row in rows:
            if row["date"]=="2026-10-24":
                row["home_score"]=170
                row["away_score"]=0
        second=evaluate(rows,start="2026-10-24",weeks=1)["predictions"]
        self.assertEqual(
            [(r["v05_full_margin"],r["v04_margin"]) for r in first],
            [(r["v05_full_margin"],r["v04_margin"]) for r in second])


if __name__=="__main__":
    unittest.main()

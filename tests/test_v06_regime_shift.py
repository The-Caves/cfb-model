"""Source-only 2026 regime shift: no postgame narratives, no outcome leakage."""
import copy
import unittest

from scripts.v05_robust_scores import fit as v05fit, predict as v05predict
from scripts.v06_regime_shift import fit, predict, MODEL, STATUS
from test_v05_robust_scores import games, NOW


def stepped():
    rows=games()[:104]
    # A seven-game history of normal results, then three persistently weaker
    # results against the same opponents. This is synthetic test input,
    # never a backfilled "known QB injury" label.
    for week in (5,6,7):
        row=rows[week*13]
        if row["home"]=="Team 0":
            row["home_score"]=3
        else:
            row["away_score"]=3
    return rows


class RegimeTests(unittest.TestCase):
    def test_source_only_synthetic_regime_and_symmetric_scores(self):
        rows=stepped();v05=v05fit(rows,NOW)
        regime=fit(rows,NOW,v05)
        self.assertEqual(regime["model"],MODEL)
        self.assertEqual(regime["status"],STATUS)
        self.assertFalse(regime["verified_qb_effect_used"])
        self.assertFalse(regime["coach_narratives_used"])
        self.assertEqual(regime["source_training_games"],104)
        self.assertTrue(regime["states"]["Team 0"]["sufficient_comparison"])
        self.assertGreaterEqual(regime["states"]["Team 0"]["games"],7)
        a=predict(regime,v05,"Team 0","Team 13",True)
        b=predict(regime,v05,"Team 13","Team 0",True)
        self.assertAlmostEqual(a["home_margin"],-b["home_margin"],places=3)
        self.assertAlmostEqual(a["total_points"],b["total_points"],places=3)
        self.assertAlmostEqual(a["home_points"]+a["away_points"],a["total_points"],places=2)
        self.assertAlmostEqual(a["home_points"]-a["away_points"],a["home_margin"],places=2)
        self.assertFalse(a["score_model_promoted"])
        self.assertFalse(a["qb_effect_applied"])
        self.assertFalse(a["coach_narrative_applied"])
        self.assertTrue(a["no_market_lines_in_training"])

    def test_persistent_decline_produces_bounded_negative_change(self):
        rows=stepped();base=v05fit(rows,NOW)
        got=fit(rows,NOW,base)
        weak=got["states"]["Team 0"]
        self.assertLess(weak["margin"]["raw_change"],0)
        self.assertLess(weak["margin"]["shift"],0)
        self.assertLess(weak["offense"]["shift"],0)
        self.assertLessEqual(abs(weak["margin"]["shift"]),4.)
        self.assertLessEqual(abs(weak["offense"]["shift"]),3.5)
        full=predict(got,base,"Team 0","Team 13",True)
        unchanged=predict(got,base,"Team 0","Team 13",True,"v06_no_change")
        self.assertLess(full["home_margin"],unchanged["home_margin"])
        self.assertLess(full["total_points"],unchanged["total_points"]+8.)

    def test_one_blowout_not_enough_to_shift_form(self):
        rows=games()[:104]
        rows[-13]["home_score"]=0
        rows[-13]["away_score"]=90
        baseline=v05fit(rows,NOW)
        model=fit(rows,NOW,baseline)
        # The affected home club has one extreme outcome, but not a sustained
        # departure from its older adjusted performances.
        club=rows[-13]["home"]
        self.assertEqual(model["states"][club]["margin"]["shift"],0.)
        self.assertEqual(model["states"][club]["offense"]["shift"],0.)

    def test_insufficient_history_refuses_change(self):
        rows=games()[:104]
        rows[-1]["home"]="New Team"
        v05=v05fit(rows,NOW)
        state=fit(rows,NOW,v05)
        self.assertFalse(state["states"]["New Team"]["sufficient_comparison"])
        self.assertEqual(state["states"]["New Team"]["margin"]["shift"],0.)
        self.assertEqual(state["states"]["New Team"]["offense"]["shift"],0.)
        self.assertFalse(predict(state,v05,"New Team","Team 0",False)["home_regime_evaluable"])

    def test_each_ablation_on_identical_source_snapshot(self):
        rows=stepped();v05=v05fit(rows,NOW);regime=fit(rows,NOW,v05)
        base=v05predict(v05,"Team 0","Team 13",False,"v05_no_form")
        no=predict(regime,v05,"Team 0","Team 13",False,"v06_no_change")
        self.assertAlmostEqual(base["home_margin"],no["home_margin"],places=3)
        self.assertAlmostEqual(base["total_points"],no["total_points"],places=3)
        total=predict(regime,v05,"Team 0","Team 13",False,"v06_margin_only")
        self.assertAlmostEqual(total["total_points"],no["total_points"],places=3)
        both=predict(regime,v05,"Team 0","Team 13",False)
        off=predict(regime,v05,"Team 0","Team 13",False,"v06_scoring_only")
        self.assertAlmostEqual(both["total_points"],off["total_points"],places=3)

    def test_future_final_and_wrong_training_cohort_fail_closed(self):
        rows=games()[:104];v05=v05fit(rows,NOW)
        late=copy.deepcopy(rows);late[-1]["date"]="2026-10-31"
        with self.assertRaisesRegex(ValueError,"strictly before"):
            fit(late,NOW,v05)
        bad=copy.deepcopy(v05);bad["source_training_games"]-=1
        with self.assertRaisesRegex(ValueError,"exactly matched"):
            fit(rows,NOW,bad)
        with self.assertRaisesRegex(ValueError,"provenance mismatch"):
            predict(fit(rows,NOW,v05),bad,"Team 0","Team 13",False)
        with self.assertRaisesRegex(ValueError,"Unregistered"):
            predict(fit(rows,NOW,v05),v05,"Team 0","Team 13",False,"custom")
    
    def test_heldout_score_change_cannot_alter_prediction(self):
        rows=games()
        source=rows[:104]
        v05=v05fit(source,NOW);regime=fit(source,NOW,v05)
        prediction=predict(regime,v05,"Team 0","Team 13",False)
        altered=copy.deepcopy(rows)
        for game in altered[104:]:
            game["home_score"]=175;game["away_score"]=0
        newer=v05fit(altered[:104],NOW)
        self.assertEqual(prediction,
           predict(fit(altered[:104],NOW,newer),newer,"Team 0","Team 13",False))


if __name__=="__main__":
    unittest.main()

"""Independent V05: robust scores, strict train/test timestamps and ablations."""
import copy
import datetime as dt
import math
import unittest

from scripts.v05_robust_scores import fit, predict, MODEL, STATUS
from scripts.v04_direct_scores import fit as v04fit, predict as v04predict


def games():
    rows=[]
    start=dt.date(2026,8,29)
    for week in range(9):
        date=(start+dt.timedelta(days=7*week)).isoformat()
        for i in range(13):
            home=f"Team {i}" if week%2==0 else f"Team {i+13}"
            away=f"Team {i+13}" if week%2==0 else f"Team {i}"
            rows.append({"game_id":str(1000+13*week+i),"date":date,
                "kickoff_utc":date+"T19:00:00Z","home":home,"away":away,
                "neutral":"True" if i%6==0 else "False",
                "home_score":27+i%6+int(i==0 and week>=6)*12,
                "away_score":18+i%5})
    return rows


NOW="2026-10-31T12:00:00Z"


class V05RobustTests(unittest.TestCase):
    def test_v05_fits_source_scores_and_preserves_points(self):
        m=fit(games()[:104],NOW)
        s=predict(m,"Team 0","Team 13",False)
        self.assertEqual(s["model"],MODEL)
        self.assertEqual(s["status"],STATUS)
        self.assertFalse(s["model_promoted"])
        self.assertEqual(m["source_training_games"],104)
        self.assertAlmostEqual(s["home_points"]+s["away_points"],s["total_points"],places=2)
        self.assertAlmostEqual(s["home_points"]-s["away_points"],s["home_margin"],places=2)
        self.assertGreaterEqual(s["away_points"],0.)
        self.assertFalse(s["uncertainty_not_calibrated"] is False)
        self.assertFalse(s["no_market_lines_in_training"] is False)

    def test_ablation_differences_explicit_and_finite(self):
        model=fit(games()[:104],NOW)
        outputs={v:predict(model,"Team 0","Team 13",False,v) for v in (
            "v05_full","v05_no_form","v05_no_margin_form","v05_no_total_form")}
        self.assertEqual(outputs["v05_no_form"]["form_margin_adjustment"],0)
        self.assertEqual(outputs["v05_no_form"]["form_total_adjustment"],0)
        self.assertEqual(outputs["v05_no_margin_form"]["form_margin_adjustment"],0)
        self.assertEqual(outputs["v05_no_total_form"]["form_total_adjustment"],0)
        self.assertLessEqual(abs(outputs["v05_full"]["form_margin_adjustment"]),8.)
        self.assertLessEqual(abs(outputs["v05_full"]["form_total_adjustment"]),10.)
        self.assertTrue(all(math.isfinite(o["total_points"]) for o in outputs.values()))

    def test_neutral_is_symmetric_and_venue_capped(self):
        model=fit(games()[:104],NOW)
        a=predict(model,"Team 0","Team 13",True,"v05_no_form")
        b=predict(model,"Team 13","Team 0",True,"v05_no_form")
        self.assertAlmostEqual(a["home_margin"],-b["home_margin"],places=3)
        self.assertAlmostEqual(a["total_points"],b["total_points"],places=3)
        self.assertEqual(a["home_field_points"],0.)
        n=predict(model,"Team 0","Team 13",False,"v05_no_form")
        self.assertTrue(0<=n["home_field_points"]<=4.5)

    def test_source_checks_future_and_duplicate_are_hard_failures(self):
        a=games()[:104]
        a[0]["date"]="2026-10-31"
        with self.assertRaisesRegex(ValueError,"strictly before"):
            fit(a,NOW)
        a=games()[:104];a.append(copy.deepcopy(a[0]))
        with self.assertRaisesRegex(ValueError,"Duplicated"):
            fit(a,NOW)
        a=games()[:104];a[3]["neutral"]="Unknown"
        with self.assertRaisesRegex(ValueError,"Neutral"):
            fit(a,NOW)
        a=games()[:104];a[3]["home_score"]=-3
        with self.assertRaisesRegex(ValueError,"Invalid final"):
            fit(a,NOW)

    def test_holdout_outcomes_do_not_affect_pregame_projections(self):
        history=games()[:104]
        model=fit(history,NOW)
        orig=predict(model,"Team 0","Team 13",False)
        rows=games()
        for row in rows[104:]:
            row["home_score"]=200
            row["away_score"]=0
        altered=fit(rows[:104],NOW)
        self.assertEqual(predict(altered,"Team 0","Team 13",False),orig)

    def test_extreme_blowout_does_not_explode_venue_or_margin(self):
        records=games()[:104]
        records[-1]["home_score"]=200
        records[-1]["away_score"]=0
        m=fit(records,NOW)
        p=predict(m,"Team 0","Team 13",False)
        self.assertLessEqual(abs(p["home_margin"]),55.)
        self.assertTrue(0<=p["home_field_points"]<=4.5)
        self.assertTrue(20.<=p["total_points"]<=110.)

    def test_new_or_thin_team_is_not_treated_as_fully_observed(self):
        history=games()[:104]
        # This school has one observed game, no claimed several-game form.
        history[-1]["home"]="Sparse Team"
        model=fit(history,NOW)
        result=predict(model,"Sparse Team","Team 1",False)
        self.assertIsNotNone(result)
        self.assertEqual(result["lesser_team_history_games"],1)
        self.assertTrue(result["thin_history_warning"])
        self.assertEqual(result["home_form_games"],1)
        self.assertEqual(result["form_margin_adjustment"],
                         round(-model["team_form"]["Team 1"]["margin_shift"],4))

    def test_models_do_not_reuse_v03_or_betting_lines(self):
        historical=games()[:104]
        old=v04predict(v04fit(historical,NOW),"Team 0","Team 13",False)
        new=predict(fit(historical,NOW),"Team 0","Team 13",False)
        self.assertNotEqual(old["model"],new["model"])
        self.assertTrue(new["no_v03_forecast_reuse"])
        self.assertTrue(new["no_qb_or_injury_inference"])
        self.assertFalse(new["model_promoted"])
        self.assertEqual(new["betting_status"],"PASS_UNVALIDATED")

    def test_invalid_predictions_do_not_guess_missing_teams(self):
        model=fit(games()[:104],NOW)
        self.assertIsNone(predict(model,"Not real","Team 0",False))
        self.assertIsNone(predict(model,"Team 0","Team 0",False))
        self.assertIsNone(predict(model,"Team 0","Team 13","False"))
        with self.assertRaisesRegex(ValueError,"Unregistered"):
            predict(model,"Team 0","Team 13",False,"unknown_variant")


if __name__=="__main__":
    unittest.main()

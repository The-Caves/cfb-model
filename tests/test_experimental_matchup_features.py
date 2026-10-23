import datetime as dt
import unittest
from scripts.experimental_matchup_features import features_for, evaluate, GROUPS

class MatchupFeatureTests(unittest.TestCase):
    def test_no_history_returns_missing_not_zero(self):
        row=features_for([],[])
        self.assertTrue(all(v is None for v in row.values()))
    def test_trajectory_uses_only_prior_games(self):
        def hist(margins):
            return [{"margin":m,"epa_off":float(m)/100,"sack_allowed":0.1,
                     "sack_generated":0.2,"pressure_allowed":0.1,
                     "redzone_success":0.5,"fourth_success":0.5} for m in margins]
        a=features_for(hist([0,0,0,10,10]),hist([0,0,0,0,0]))
        self.assertAlmostEqual(a["margin_trajectory_form"],10)
        self.assertEqual(a["sack_allowed_matchup"],0)
    def test_evaluation_executes_brier_path(self):
        from scripts.experimental_matchup_features import evaluate
        from scripts.model_v03 import FEATURES
        rows=[]
        for i in range(200):
            day=dt.date(2026,8,1)+dt.timedelta(days=i//5)
            g={field:None for field in FEATURES}
            g.update({"game_id":str(i),"date":day.isoformat(),
                      "home":"Home","away":"Away",
                      "home_games_prior":2,"away_games_prior":2,
                      "home_score":24+i%7,"away_score":17+i%5})
            rows.append(g)
        report,preds=evaluate(rows,start="2026-08-29",min_training=90)
        self.assertGreater(len(preds["baseline_v03"]),0)
        self.assertTrue(0<=report["overall"]["baseline_v03"]["brier"]<=1)
        self.assertFalse(report["model_promoted"])
    def test_feature_groups_nonempty(self):
        self.assertEqual(set(GROUPS),{"line_front","redzone_fourth","trajectory"})

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
    def test_feature_groups_nonempty(self):
        self.assertEqual(set(GROUPS),{"line_front","redzone_fourth","trajectory"})

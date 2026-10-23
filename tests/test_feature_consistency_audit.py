import datetime as dt
import unittest
from scripts.feature_consistency_audit import VARIANTS, evaluate
from scripts.model_v03 import SCORE, ADV

class FeatureConsistencyTests(unittest.TestCase):
    def fixture(self):
        games = []
        for i in range(160):
            day = dt.date(2026, 8, 1) + dt.timedelta(days=i//5)
            row = dict.fromkeys(SCORE + ADV, None)
            row.update({"game_id": str(i), "date": day.isoformat(),
                        "kickoff_utc": day.isoformat()+"T18:00:00Z",
                        "home": "Home", "away": "Away",
                        "home_games_prior": 1, "away_games_prior": 1,
                        "home_score": 17+i%3, "away_score": 14+i%5,
                        "score_margin_form": float(i%7), "scoring_total_form": 45.,
                        "win_rate_form": 0., "rest_days_diff": 0., "neutral_site": 0.})
            games.append(row)
        return games

    def test_paired_variants_and_no_promotion(self):
        report, predictions = evaluate(self.fixture(), first_week="2026-08-29")
        self.assertFalse(report["model_promoted"])
        self.assertFalse(report["historical_pregame_source_provenance_verified"])
        self.assertEqual(set(predictions), set(VARIANTS))
        self.assertEqual(len(predictions["score_only"]), len(predictions["full_v03"]))
        self.assertEqual(report["comparisons"]["full_v03"]["correct_change_vs_full"], 0)

    def test_no_eligible_folds_fails_closed(self):
        with self.assertRaises(ValueError):
            evaluate(self.fixture()[:12], first_week="2026-08-01")

import copy
import unittest
from scripts.multifactor_walkforward import prepare, walkforward, injury_pressure_interaction, VARIANTS
from scripts.personnel_features import BASE_FIELDS

def records():
    feature = {"game_id": "1", "home": "Home", "away": "Away",
               "kickoff_utc": "2026-10-24T16:00:00Z",
               "capture_utc": "2026-10-23T12:00:00Z",
               "betting_status": "PASS_UNVALIDATED",
               "features": {name: 0.1 for name in BASE_FIELDS}}
    label = {"game_id": "1", "home": "Home", "away": "Away",
             "kickoff_utc": feature["kickoff_utc"],
             "outcome_known_at_utc": "2026-10-24T23:00:00Z",
             "evidence_status": "OBSERVED_POSTGAME_FINAL",
             "home_score": 24, "away_score": 17}
    return feature, label

class MultifactorTests(unittest.TestCase):
    def test_valid_observed_pair_and_insufficient_fold(self):
        feature, label = records()
        rows = prepare([feature], [label],
                       evaluation_asof_utc="2026-10-25T12:00:00Z")
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["wx_wind_pass_exposure"])
        report = walkforward(rows, "2026-10-24T00:00:00Z",
                             "2026-10-25T12:00:00Z", weeks=1)
        self.assertEqual(report["folds"][0]["status"], "INSUFFICIENT_OBSERVED_GAMES")
        self.assertFalse(report["model_promoted"])

    def test_partial_reports_do_not_create_fake_zero_player_effect(self):
        self.assertEqual(injury_pressure_interaction({
            "coverage":"INCOMPLETE",
            "home_report_by_position":{"coverage":"VERIFIED_REPORT_REVIEWED","absences":{"OL":2,"QB":0}},
            "away_report_by_position":{"coverage":"UNKNOWN","absences":None}
        },0.3),(None,None))

    def test_asof_verified_ol_and_qb_pressure_matchup_is_only_candidate(self):
        feature,label=records()
        all_positions={p:0 for p in __import__("scripts.player_replacement",fromlist=["POSITIONS"]).POSITIONS}
        home=dict(all_positions,OL=2,QB=1)
        away=dict(all_positions,OL=1,QB=0)
        replacement=[{"game_id":"1","kickoff_utc":feature["kickoff_utc"],
                      "decision_asof_utc":feature["capture_utc"],
                      "coverage":"BOTH_REPORTS","absence_differentials":
                      {p:home[p]-away[p] for p in all_positions},
                      "home_report_by_position":{"coverage":"VERIFIED_REPORT_REVIEWED","absences":home},
                      "away_report_by_position":{"coverage":"VERIFIED_REPORT_REVIEWED","absences":away}}]
        rows=prepare([feature],[label],replacement=replacement,
                     evaluation_asof_utc="2026-10-25T12:00:00Z")
        self.assertAlmostEqual(rows[0]["verified_ol_absence_pressure_interaction"],0.1)
        self.assertAlmostEqual(rows[0]["verified_qb_absence_pressure_interaction"],0.1)
        self.assertIn("plus_injury_pressure_interaction",VARIANTS)
        self.assertNotIn("player_point_penalty",rows[0])

    def test_future_injury_coverage_rejected_and_missing_is_null(self):
        feature,label=records()
        late=[{"game_id":"1","kickoff_utc":feature["kickoff_utc"],
               "decision_asof_utc":"2026-10-24T12:00:00Z",
               "coverage":"INCOMPLETE","absence_differentials":None}]
        with self.assertRaises(ValueError):
            prepare([feature],[label],replacement=late,
                    evaluation_asof_utc="2026-10-25T12:00:00Z")
        rows=prepare([feature],[label],
                     evaluation_asof_utc="2026-10-25T12:00:00Z")
        self.assertIsNone(rows[0]["verified_ol_absence_pressure_interaction"])
        self.assertIsNone(rows[0]["verified_qb_absence_pressure_interaction"])

    def test_rejects_future_weather(self):
        feature, label = records()
        weather = {"game_id": "1", "decision_asof_utc": feature["capture_utc"],
                   "forecast_issued_at_utc": "2026-10-23T13:00:00Z",
                   "forecast_captured_at_utc": feature["capture_utc"],
                   "kickoff_utc": feature["kickoff_utc"], "features": {}}
        with self.assertRaises(ValueError):
            prepare([feature], [label], weather=[weather],
                    evaluation_asof_utc="2026-10-25T12:00:00Z")

    def test_rejects_future_training_result(self):
        feature, label = records()
        rows = prepare([feature], [label],
                       evaluation_asof_utc="2026-10-25T12:00:00Z")
        # Test game not permitted in training even if result is eventually known.
        report = walkforward(rows, "2026-10-24T00:00:00Z",
                             "2026-10-25T12:00:00Z", weeks=1,
                             min_train=2, min_test=1)
        self.assertEqual(report["folds"][0]["train_game_ids"], [])
        self.assertEqual(report["folds"][0]["test_game_ids"], ["1"])

    def test_rejects_future_outcome(self):
        feature, label = records()
        label["outcome_known_at_utc"] = "2026-10-26T12:00:00Z"
        with self.assertRaises(ValueError):
            prepare([feature], [label],
                    evaluation_asof_utc="2026-10-25T12:00:00Z")

    def test_rejects_repeated_games(self):
        feature, label = records()
        with self.assertRaises(ValueError):
            prepare([feature, copy.deepcopy(feature)], [label],
                    evaluation_asof_utc="2026-10-25T12:00:00Z")

if __name__ == "__main__":
    unittest.main()

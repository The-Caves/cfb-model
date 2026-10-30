import unittest
from scripts.player_replacement import observed_absences, build_game, train_coefficients, estimate

ASOF = "2026-10-23T12:00:00Z"
KICKOFF = "2026-10-24T16:00:00Z"
FINAL = "2026-10-24T23:00:00Z"
DECISION = "2026-10-25T12:00:00Z"

def snap(status="VERIFIED_REPORT_REVIEWED"):
    return {"asof_utc": ASOF, "coverage_status": status,
            "reported_players": [
                {"player": "Example Quarterback", "position": "QB", "reported_status": "OUT"},
                {"player": "Example Receiver", "position": "WR", "reported_status": "QUESTIONABLE"}]}

class ReplacementTests(unittest.TestCase):
    def test_source_report_counts_and_unknown(self):
        result = observed_absences(snap(), ASOF)
        self.assertEqual(result["absences"]["QB"], 1)
        self.assertEqual(result["uncertain"]["WR"], 1)
        self.assertFalse(result["player_identity_globally_verified"])
        self.assertIsNone(observed_absences(snap("UNKNOWN"), ASOF)["absences"])
        with self.assertRaises(ValueError):
            observed_absences(snap(), "2026-10-22T12:00:00Z")

    def test_missing_report_never_zero(self):
        good = observed_absences(snap(), ASOF)
        missing = observed_absences(snap("UNKNOWN"), ASOF)
        self.assertIsNone(build_game(good, missing)["absence_differentials"])
        self.assertEqual(build_game(good, good)["absence_differentials"]["QB"], 0)

    def test_first_half_unavailable_not_full_game_out(self):
        sample=snap()
        sample["reported_players"].append({"player":"Example Guard","position":"OL",
                                          "reported_status":"OUT_FIRST_HALF"})
        result=observed_absences(sample,ASOF)
        self.assertEqual(result["partial_absences"]["OL"],1)
        self.assertEqual(result["absences"]["OL"],0)
        self.assertEqual(result["uncertain"]["OL"],0)
        combined=build_game(result,result)
        self.assertEqual(combined["partial_game_differentials"]["OL"],0)
        self.assertIsNone(combined["replacement_points"])

    def test_no_arbitrary_replacement_penalty(self):
        self.assertEqual(train_coefficients([], DECISION)["status"], "INSUFFICIENT_TRAINING")
        good = observed_absences(snap(), ASOF)
        self.assertIsNone(estimate(build_game(good, good),
                                  {"status": "INSUFFICIENT_TRAINING"}))

    def test_train_only_earlier_known_results(self):
        rows = []
        for i in range(31):
            differential = {p: 0 for p in ("QB", "RB", "WR", "TE", "OL", "DL", "EDGE",
                                           "LB", "CB", "DB", "S", "K", "P", "OTHER")}
            differential["QB"] = i % 2
            rows.append({"game_id": str(i), "kickoff_utc": KICKOFF,
                         "captured_at_utc": ASOF, "outcome_known_at_utc": FINAL,
                         "coverage": "BOTH_REPORTS", "absence_differentials": differential,
                         "actual_home_margin": 10 + 3*(i % 2),
                         "frozen_baseline_home_margin": 10})
        result = train_coefficients(rows, DECISION, minimum=30)
        self.assertEqual(result["status"], "FITTED_RESEARCH_ONLY")
        self.assertGreater(result["coefficients"]["QB"], 0)
        self.assertFalse(result["individual_player_value_verified"])
        rows[0]["outcome_known_at_utc"] = "2026-10-26T12:00:00Z"
        with self.assertRaises(ValueError):
            train_coefficients(rows, DECISION, minimum=30)

if __name__ == "__main__":
    unittest.main()

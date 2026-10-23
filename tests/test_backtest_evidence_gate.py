import unittest
from scripts.backtest_evidence_gate import audit

BASE = {"status": "RETROSPECTIVE_RESEARCH_ONLY", "season": 2026,
        "betting_status": "PASS_UNVALIDATED", "safe_for_betting": False,
        "weekly_folds": [{"train_before": "2026-09-26"}]}

class BacktestEvidenceGateTests(unittest.TestCase):
    def test_missing_all_historical_evidence_blocks_betting(self):
        result = audit(BASE)
        self.assertEqual(len(result["blockers"]), 4)
        self.assertTrue(result["chronological_research_possible"])
        self.assertFalse(result["authenticated_betting_backtest_ready"])
        self.assertFalse(result["safe_for_betting"])

    def test_boolean_and_malformed_counts_not_evidence(self):
        result = audit(BASE, {"historical_market": {"verified": True,
            "eligible_games": True, "source_manifest_sha256": "a"*64}})
        self.assertFalse(result["checks"]["historical_market"]["verified"])

    def test_claimed_manifest_cannot_override_independent_audit(self):
        manifest = {name: {"verified": True, "eligible_games": 100,
                    "source_manifest_sha256": "a"*64}
                    for name in ("epa_pbp", "historical_market",
                                 "pregame_weather", "player_replacement")}
        result = audit(BASE, manifest)
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["authenticated_betting_backtest_ready"])
        self.assertTrue(result["independent_source_time_audit_required"])

    def test_rejects_false_betting_clearance(self):
        invalid = dict(BASE, safe_for_betting=True)
        with self.assertRaises(ValueError):
            audit(invalid)
        invalid = dict(BASE, season=2025)
        with self.assertRaises(ValueError):
            audit(invalid)

if __name__ == "__main__":
    unittest.main()

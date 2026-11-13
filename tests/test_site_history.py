"""Historical PRESSBOX: actual archived V04 before kickoff, observed finals after."""
import datetime as dt
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.site_history import build, ARCHIVE_STATUS, FINAL_STATUS

UTC = dt.timezone.utc
NOW = "2026-11-13T12:00:00Z"
KICK = "2026-11-12T22:00:00Z"
CAPTURE = "2026-11-12T21:30:00Z"


def fixture(root, captured=CAPTURE, outcome=True, model=True):
    root = Path(root)
    row = {
        "game_id": "123", "home": "A", "away": "B", "kickoff_utc": KICK,
        "home_bias_quarantined": True, "v04_research_not_promoted": model,
        "v04_direct_source_no_v03_total_reuse": True,
        "v04_direct_home_points": 28.5, "v04_direct_away_points": 21.5,
        "v04_direct_home_margin": 7.0, "v04_direct_total_points": 50.0,
        "v04_research_ats_side": "PASS", "v04_research_ou_side": "UNDER",
        "market_home_spread": -4.5, "market_total": 52.5,
        "market_provider": "Book A", "market_observed_utc": captured,
        "market_home_moneyline": -190, "market_away_moneyline": 160,
    }
    snapshot = {"status": ARCHIVE_STATUS, "betting_status": "PASS_UNVALIDATED",
                "capture_utc": captured, "dashboard_run_id": "1234", "rows": [row]}
    path = "research_2026/site_board_snapshots/2026/11/12/run-1234.json.gz"
    artifact = root / path
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(gzip.compress(json.dumps(snapshot).encode()))
    hashed = hashlib.sha256(json.dumps(snapshot, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    index = {"status": ARCHIVE_STATUS, "schema_version": 1,
             "runs": [{"path": path, "run_id": "1234",
                       "capture_utc": captured, "sha256": hashed}]}
    idx = root / "research_2026/site_board_snapshots/index.json"
    idx.write_text(json.dumps(index))
    finals = {"status": FINAL_STATUS, "season": 2026, "safe_for_betting": False,
              "games": {}}
    if outcome:
        finals["games"]["123"] = {
            "game_id": "123", "home": "A", "away": "B", "kickoff_utc": KICK,
            "outcome_known_at_utc": "2026-11-13T03:00:00Z",
            "home_score": 14, "away_score": 35,
        }
    (root / "research_2026/outcome_index.json").write_text(json.dumps(finals))
    return row, idx, artifact


class HistoryTests(unittest.TestCase):
    def test_genuine_pregame_plus_observed_final_pass_not_forced_to_pick(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture(temp)
            game = build(temp, NOW)["history_games"][0]
            self.assertEqual(game["archived_model"], "V04")
            self.assertEqual(game["model_home_points"], 28.5)
            self.assertEqual(game["final"]["away_score"], 35)
            self.assertEqual(game["outcomes"]["su"], "LOSS")
            self.assertEqual(game["outcomes"]["ats"], "PASS")
            self.assertEqual(game["outcomes"]["ou"], "WIN")
            self.assertEqual(game["market_home_spread"], -4.5)
            self.assertTrue(game["pregame_snapshot_verified"])

    def test_future_snapshot_cannot_be_used_as_historical_forecast(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture(temp, captured="2026-11-13T04:00:00Z")
            self.assertEqual(build(temp, NOW)["history_games"], [])

    def test_result_not_imputed_before_verified_settlement(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture(temp, outcome=False)
            game=build(temp,NOW)["history_games"][0]
            self.assertIsNone(game["final"])
            self.assertEqual(game["outcomes"]["su"], "PENDING")

    def test_digest_mismatch_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            _, index, _ = fixture(temp)
            data = json.loads(index.read_text())
            data["runs"][0]["sha256"] = "f"*64
            index.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "digest"):
                build(temp,NOW)

    def test_mismatched_final_cannot_join(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture(temp)
            file = Path(temp) / "research_2026/outcome_index.json"
            raw=json.loads(file.read_text())
            raw["games"]["123"]["home"] = "Wrong"
            file.write_text(json.dumps(raw))
            self.assertIsNone(build(temp,NOW)["history_games"][0]["final"])

    def test_quarantined_v03_not_displayed_as_valid_historical_pick(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture(temp, model=False)
            game=build(temp,NOW)["history_games"][0]
            self.assertEqual(game["archived_model"], "V03_QUARANTINED")
            self.assertIsNone(game["model_home_points"])
            self.assertEqual(game["outcomes"]["su"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from scripts.market_history_import import ingest
from scripts.market_vault import audit, latest_quote

DATA = {"timestamp": "2026-10-21T17:00:00Z", "data": [
    {"id": "event-1", "sport_key": "americanfootball_ncaaf",
     "commence_time": "2026-10-24T19:00:00Z",
     "home_team": "Home", "away_team": "Away",
     "bookmakers": [{"key": "fanduel", "last_update": "2026-10-21T16:55:00Z",
                    "markets": [{"key": "spreads", "outcomes": [
                        {"name": "Home", "point": -5.5, "price": -110},
                        {"name": "Away", "point": 5.5, "price": -110}]}]}]}]}

class HistoricalMarketImportTests(unittest.TestCase):
    def test_offline_historical_import_and_duplicate(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root)/"history.json"
            source.write_text(json.dumps(DATA))
            vault = Path(root)/"market.sqlite3"
            first = ingest([source], vault, "2026-10-23T12:00:00Z")
            self.assertEqual(first["quotes_added"], 2)
            self.assertTrue(first["historical_retrieval_after_decision_must_not_be_live"])
            self.assertFalse(first["true_opening_or_closing_lines_verified"])
            self.assertEqual(audit(vault)["quotes"], 2)
            second = ingest([source], vault, "2026-10-23T12:00:00Z")
            self.assertEqual(second["duplicate_snapshots"], 1)

    def test_reject_future_historical_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root)/"history.json"
            source.write_text(json.dumps(DATA))
            with self.assertRaises(ValueError):
                ingest([source], Path(root)/"market.sqlite3",
                       "2026-10-20T12:00:00Z")

    def test_reject_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root)/"history.json"
            source.write_text(json.dumps(DATA))
            with self.assertRaises(ValueError):
                ingest([source, source], Path(root)/"market.sqlite3",
                       "2026-10-23T12:00:00Z")

if __name__ == "__main__":
    unittest.main()

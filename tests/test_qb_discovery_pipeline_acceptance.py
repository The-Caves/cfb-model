"""Offline, deterministic discovery-to-review acceptance tests; no invented starter evidence."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.qb_official_news_watch import run as discover
from scripts.qb_review_queue import build_queue, export_review_csv

NOW = "2026-10-22T16:00:00Z"
GAME = {"game_id": "historical-fixture-1", "home": "NC State Wolfpack",
        "away": "Virginia Cavaliers", "kickoff_utc": "2026-10-24T16:00:00Z"}
# A deterministic example announcement, NOT a claim about a real player or game.
RSS = b"""<rss version="2.0"><channel><item>
<title>Coach discusses starting quarterback before Saturday matchup</title>
<link>https://gopack.com/news/2026/example-quarterback.aspx</link>
<pubDate>Thu, 22 Oct 2026 12:00:00 GMT</pubDate>
<description>The quarterback starter is discussed at a press conference.</description>
</item></channel></rss>"""

class DiscoveryPipelineAcceptance(unittest.TestCase):
    def test_offline_announcement_reaches_queue_without_auto_verification(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "context.json"
            output = Path(d) / "news.json"
            csv_path = Path(d) / "review.csv"
            source.write_text(json.dumps({"games": [GAME]}), encoding="utf-8")
            calls = []
            def reader(url):
                calls.append(url)
                return RSS
            news = discover(source, output, reader=reader, now=NOW)
            self.assertEqual(len(calls), 1)
            self.assertEqual(news["manifest"]["candidate_count"], 1)
            self.assertEqual(news["manifest"]["feeds_failed"], 0)
            queue = build_queue({"games": [GAME]}, news, NOW)
            self.assertEqual(queue["summary"]["candidate_mentions"], 1)
            self.assertEqual(queue["summary"]["verified_starters"], 0)
            self.assertEqual(queue["summary"]["unknown_starters"], 2)
            nc = next(row for row in queue["rows"] if row["team"] == GAME["home"])
            self.assertEqual(nc["review_priority"], "REVIEW_NEWS_CANDIDATE")
            self.assertEqual(nc["starter_status"], "UNKNOWN")
            self.assertEqual(nc["candidate_count"], 1)
            va = next(row for row in queue["rows"] if row["team"] == GAME["away"])
            self.assertEqual(va["feed_status"], "NOT_CONFIGURED")
            self.assertEqual(va["candidate_count"], 0)
            self.assertEqual(export_review_csv(queue, csv_path), 2)
            self.assertIn("example-quarterback.aspx", csv_path.read_text())

    def test_stale_news_does_not_enter_review_queue(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "context.json"
            source.write_text(json.dumps({"games": [GAME]}))
            news = discover(source, Path(d) / "news.json",
                            reader=lambda _: RSS.replace(b"22 Oct 2026", b"01 Sep 2026"),
                            now=NOW)
            self.assertEqual(news["manifest"]["candidate_count"], 0)
            queue = build_queue({"games": [GAME]}, news, NOW)
            self.assertEqual(queue["summary"]["candidate_mentions"], 0)

if __name__ == "__main__":
    unittest.main()

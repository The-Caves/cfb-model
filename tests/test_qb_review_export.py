import csv
import tempfile
import unittest
from pathlib import Path
from scripts.qb_review_queue import export_review_csv

class ReviewExportTests(unittest.TestCase):
    def test_review_queue_export_never_confirms_news_candidate(self):
        queue={"rows":[{"game_id":"123","kickoff_utc":"2026-10-24T20:00:00Z",
            "team":"Iowa Hawkeyes","opponent":"Minnesota Golden Gophers",
            "starter_status":"UNKNOWN","starter_player":None,
            "review_priority":"REVIEW_NEWS_CANDIDATE","feed_status":"FETCHED",
            "candidate_count":1,
            "news_candidates":[{"source_url":"https://hawkeyesports.com/news/story"}],
            "qb_availability":[]}]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"queue.csv"
            self.assertEqual(export_review_csv(queue,p),1)
            with p.open(newline="") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(rows[0]["starter_status"],"UNKNOWN")
            self.assertEqual(rows[0]["source_urls"],"https://hawkeyesports.com/news/story")
            self.assertEqual(rows[0]["starter_player"],"")
    def test_empty_queue_produces_header(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"queue.csv"
            self.assertEqual(export_review_csv({"rows":[]},p),0)
            self.assertIn("game_id",p.read_text())

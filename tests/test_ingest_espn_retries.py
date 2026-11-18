"""ESPN scoreboard feed: transport retries never hide missing historical days."""
import datetime as dt
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from scripts import ingest_espn


class ScoreboardRetryTests(unittest.TestCase):
    def setUp(self):
        self.day=dt.date(2026,10,30)

    def test_tls_handshake_recovers_without_changing_observed_results(self):
        raw=io.BytesIO(json.dumps({"events":[]}).encode())
        with patch.object(ingest_espn.urllib.request,"urlopen",
                side_effect=[urllib.error.URLError("TLSV1_ALERT_INTERNAL_ERROR"),
                             raw]) as request,patch.object(ingest_espn.time,"sleep") as sleep:
            out=ingest_espn.fetch_day(self.day)
        self.assertEqual(out,{"events":[]})
        self.assertEqual(request.call_count,2)
        sleep.assert_called_once()

    def test_http_503_is_retryable_but_rate_denial_403_is_not(self):
        with patch.object(ingest_espn.urllib.request,"urlopen",
                side_effect=[urllib.error.HTTPError("url",503,"temporary",{},None),
                             io.BytesIO(b'{"events":[]}')]) as request,patch.object(
                                 ingest_espn.time,"sleep"):
            self.assertEqual(ingest_espn.fetch_day(self.day)["events"],[])
            self.assertEqual(request.call_count,2)
        with patch.object(ingest_espn.urllib.request,"urlopen",
                side_effect=urllib.error.HTTPError("url",403,"forbidden",{},None)) as request:
            with self.assertRaises(urllib.error.HTTPError):
                ingest_espn.fetch_day(self.day)
            self.assertEqual(request.call_count,1)

    def test_bad_espn_payload_is_not_silently_interpreted_as_no_games(self):
        with patch.object(ingest_espn.urllib.request,"urlopen",
                return_value=io.BytesIO(b'{"unexpected":"not a scoreboard"}')) as req:
            with self.assertRaisesRegex(RuntimeError,"lacked events"):
                ingest_espn.fetch_day(self.day)
            self.assertEqual(req.call_count,1)

    def test_repeated_tls_failure_fails_closed_and_marks_day_incomplete(self):
        with patch.object(ingest_espn.urllib.request,"urlopen",
                side_effect=urllib.error.URLError("TLS handshake timeout")) as req,patch.object(
                    ingest_espn.time,"sleep") as pause:
            with self.assertRaises(urllib.error.URLError):
                ingest_espn.fetch_day(self.day)
            self.assertEqual(req.call_count,3)
            self.assertEqual(pause.call_count,2)
        with tempfile.TemporaryDirectory() as tmp,patch.object(
            ingest_espn,"fetch_day",side_effect=urllib.error.URLError("SSL failure")
        ),patch.object(ingest_espn.time,"sleep"):
            with self.assertRaises(SystemExit) as caught:
                ingest_espn.ingest(self.day,self.day,Path(tmp))
            self.assertEqual(caught.exception.code,2)
            manifest=json.loads((Path(tmp)/"manifest.json").read_text())
            self.assertEqual(manifest["status"],"INCOMPLETE")
            self.assertEqual(manifest["days_fetched"],0)
            self.assertEqual(manifest["failures"][0]["date"],"2026-10-30")


if __name__=="__main__":
    unittest.main()

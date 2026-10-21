import unittest
from scripts.ingest_espn import parse_event

class ESPNDateTests(unittest.TestCase):
    def build(self, at):
        return {"id":"1","date":at,"status":{"type":{"completed":True}},
                "competitions":[{"neutralSite":False,"competitors":[
                    {"homeAway":"home","score":"31","team":{"displayName":"A"}},
                    {"homeAway":"away","score":"14","team":{"displayName":"B"}}]}]}
    def test_utc_midnight_is_previous_eastern_date(self):
        row=parse_event(self.build("2026-09-05T01:10:00Z"))
        self.assertEqual(row["date"],"2026-09-04")
        self.assertEqual(row["kickoff_utc"],"2026-09-05T01:10:00Z")
    def test_utc_daytime(self):
        self.assertEqual(parse_event(self.build("2026-09-05T19:30:00Z"))["date"],"2026-09-05")
    def test_incomplete(self):
        e=self.build("2026-09-05T01:00:00Z");e["status"]["type"]["completed"]=False
        self.assertIsNone(parse_event(e))
if __name__=="__main__":unittest.main()

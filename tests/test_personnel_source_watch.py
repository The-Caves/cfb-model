import unittest
from scripts.personnel_source_watch import monitor,SOURCES
class WatchTests(unittest.TestCase):
    def test_new_and_changed_are_not_injuries(self):
        def fetcher(_,url):return {"sha256":"xyz","url":url,"bytes":400}
        one=monitor(None,fetcher,"2026-10-21T01:00:00Z")
        self.assertFalse(one["source_reports_are_player_statuses"])
        self.assertTrue(all(x=="FIRST_SNAPSHOT" for x in one["sources_status"].values()))
        two=monitor({"sources":{k:{"sha256":"abc"} for k in SOURCES}},
                    fetcher,"2026-10-21T02:00:00Z")
        self.assertEqual(len(two["candidate_source_changes"]),len(SOURCES))
        self.assertEqual(two["parse_status"],"NO_VERIFIED_PLAYER_EXTRACTION")
if __name__=="__main__":unittest.main()

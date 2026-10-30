import unittest
from scripts.personnel_source_watch import SOURCES, monitor

class OfficialWatcherTests(unittest.TestCase):
    def test_all_four_major_conferences_watched_without_player_inference(self):
        self.assertEqual(set(SOURCES),{
            "SEC_FOOTBALL_OFFICIAL","BIG_TEN_FOOTBALL_OFFICIAL",
            "ACC_FOOTBALL_OFFICIAL","BIG12_FOOTBALL_OFFICIAL"})
        def fetch(_,url):
            return {"url":url,"sha256":"sha1","bytes":150,"content_type":"text/html"}
        result=monitor(fetcher=fetch,now="2026-10-30T17:00:00Z")
        self.assertEqual(len(result["sources"]),4)
        self.assertTrue(all(s=="FIRST_SNAPSHOT" for s in result["sources_status"].values()))
        self.assertFalse(result["source_reports_are_player_statuses"])
        self.assertEqual(result["parse_status"],"NO_VERIFIED_PLAYER_EXTRACTION")

    def test_changed_page_requires_review_and_does_not_assert_absence(self):
        def fetch(_,url):
            return {"url":url,"sha256":"new","bytes":150,"content_type":"text/html"}
        old={"sources":{key:{"sha256":"old"} for key in SOURCES}}
        r=monitor(old,fetcher=fetch,now="2026-10-30T17:00:00Z")
        self.assertEqual(len(r["candidate_source_changes"]),4)
        self.assertTrue(all(c["event"]=="OFFICIAL_SOURCE_PAGE_CHANGED_NEEDS_REPORT_REVIEW"
                            for c in r["candidate_source_changes"]))
        self.assertFalse(r["source_reports_are_player_statuses"])

if __name__=="__main__":unittest.main()

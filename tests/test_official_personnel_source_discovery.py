import unittest
from scripts.official_personnel_source_discovery import (
    inspect_school,host_allowed,resolved_links,football_pages,secondary_pages,extract_candidates)

class OfficialPersonnelSourceDiscoveryTests(unittest.TestCase):
    ROOT="https://example.edu/"
    def test_only_host_owned_https_links(self):
        body=b"""<html><a href="/sports/football">Football</a>
                  <a href="https://evil.edu/sports/football">Football</a>
                  <a href="http://example.edu/notes.pdf">Game Notes</a></html>"""
        links=resolved_links(body,self.ROOT,self.ROOT)
        self.assertEqual([x["url"] for x in links],["https://example.edu/sports/football"])
        self.assertFalse(host_allowed("https://evil.edu/football",self.ROOT))
        self.assertFalse(host_allowed("https://example.edu:8443/football",self.ROOT))
    def test_school_documents_are_candidates_not_player_evidence(self):
        pages={
            self.ROOT:b'<a href="/sports/football">Football</a>',
            "https://example.edu/sports/football":b"""<a href="/sports/football/schedule">Football Schedule</a>
               <a href="/documents/2026-game-notes.pdf">2026 Football Game Notes</a>
               <a href="/sports/football/depth-chart">Depth Chart</a>
               <a href="https://offsite.org/injury-report">Injury Report</a>""",
            "https://example.edu/sports/football/schedule":b'<a href="/sports/football/injury-report">Injury Report</a>'
        }
        def fetch(url):return url,pages[url]
        result=inspect_school({"team":"Test Team","athletics_homepage":self.ROOT},fetch)
        self.assertEqual(result["crawl_status"],"AUDITED")
        self.assertEqual(result["football_page_status"],"LIVE_SCHOOL_DOMAIN_LINK_VERIFIED")
        self.assertEqual(len(result["game_notes"]),1)
        self.assertGreaterEqual(len(result["depth_chart"]),1)
        self.assertGreaterEqual(len(result["injury_report"]),1)
        self.assertTrue(all(not x["game_specific_evidence_verified"]
                            for category in ("game_notes","depth_chart","injury_report")
                            for x in result[category]))
        self.assertFalse(result["game_specific_player_evidence_verified"])
    def test_missing_football_link_is_not_invented(self):
        def fetch(url):
            if url!=self.ROOT:raise ValueError("NOT_FOUND")
            return url,b"<html><h1>Home</h1></html>"
        result=inspect_school({"team":"Test","athletics_homepage":self.ROOT},fetch)
        self.assertEqual(result["crawl_status"],"FOOTBALL_PAGE_FETCH_FAILED")
        self.assertIsNone(result["football_page"])
if __name__=="__main__":unittest.main()

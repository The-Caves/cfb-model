"""Source discovery is review-only; it cannot confirm a QB or invent a URL."""
import unittest
from scripts.qb_gamebook_link_discovery import (
    discover, safe_href, opponent_slugs, STATUS, MAX_SCHOOLS)

AT="2026-11-02T12:00:00Z"
def sites():
    return {"season":2026,
            "status":"EXTERNALLY_CROSS_REFERENCED_ATHLETICS_DIRECTORY_CANDIDATES_V1",
            "expected_teams":2,
            "schools":[
                {"team":"Texas Longhorns",
                 "source_host":"texaslonghorns.com",
                 "athletics_homepage":"https://texaslonghorns.com/"},
                {"team":"Ole Miss Rebels",
                 "source_host":"olemisssports.com",
                 "athletics_homepage":"https://olemisssports.com/"}]}
def target(team="Texas Longhorns",opponent="Ole Miss Rebels",game="401856732"):
    return {"game_id":game,"team":team,"opponent":opponent,
            "kickoff_utc":"2026-10-24T23:30:00Z","review_required":"True",
            "reason":"NOT_REVIEWED_ACTUAL_STARTER"}
def fetch(page,host):
    assert page=="https://texaslonghorns.com/sports/football/schedule/2026"
    assert host=="texaslonghorns.com"
    return """<html><body>
        <a href="/sports/football/stats/2026/ole-miss/boxscore/22500">Official box score</a>
        <a href="/sports/football/stats/2026/texas-am/boxscore/22800">Unrelated matchup</a>
        <a href="https://evil.example/sports/football/stats/2026/ole-miss/boxscore/1">Off-host</a>
        <a href="//evil.example/sports/football/stats/2026/ole-miss/boxscore/12">Host escape</a>
        <a href="/sports/football/stats/2026/ole-miss/boxscore/22500?return=1">Query</a>
        </body></html>"""

class SchoolGamebookLinkTests(unittest.TestCase):
    def test_schedule_link_discovered_but_not_promoted_as_evidence(self):
        r=discover([target()],sites(),AT,fetch=fetch)
        self.assertEqual(r["status"],STATUS)
        self.assertEqual(r["school_sites_scanned"],1)
        self.assertEqual(r["candidate_links_found"],1)
        self.assertFalse(r["ready_to_be_starter_labels"])
        self.assertTrue(r["no_automatic_official_confirmation"])
        row=r["candidates"][0]
        self.assertEqual(row["source_url_candidate"],
                         "https://texaslonghorns.com/sports/football/stats/2026/ole-miss/boxscore/22500")
        self.assertEqual(row["match_rule"],"EXACT_OPPONENT_SLUG")
        self.assertFalse(row["starter_identity_verified"])
        self.assertFalse(row["game_identity_verified"])
        self.assertTrue(row["manually_review_game_score_date_and_starters"])

    def test_host_fragments_query_nonfootball_and_unseen_urls_unsafe(self):
        page="https://texaslonghorns.com/sports/football/schedule/2026"
        for href in (
            "http://texaslonghorns.com/sports/football/stats/2026/ole-miss/boxscore/1",
            "https://evil.com/sports/football/stats/2026/ole-miss/boxscore/1",
            "//evil.com/sports/football/stats/2026/ole-miss/boxscore/1",
            "/sports/football/stats/2026/ole-miss/boxscore/123?token=4",
            "/sports/football/stats/2026/ole-miss/boxscore/123#fragment",
            "/sports/basketball/stats/2026/ole-miss/boxscore/123",
            "/sports/football/stats/2025/ole-miss/boxscore/123",
            "javascript:alert(1)",
            "https://texaslonghorns.com@evil.com/sports/football/stats/2026/ole-miss/boxscore/1",
        ):
            with self.subTest(href=href):
                self.assertIsNone(safe_href(href,page,"texaslonghorns.com"))

    def test_partially_matching_slug_is_still_review_only(self):
        def page(url,host):
            return '<a href="/sports/football/stats/2026/ole-miss-rebels/boxscore/234">Score</a>'
        result=discover([target()],sites(),AT,fetch=page)
        self.assertEqual(result["candidates"][0]["match_rule"],
                         "PARTIAL_OPPONENT_SLUG_NEEDS_REVIEW")
        self.assertFalse(result["candidates"][0]["starter_identity_verified"])

    def test_duplicate_and_incomplete_review_targets_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            discover([target(),target()],sites(),AT,fetch=fetch)
        wrong=target();wrong["review_required"]="False"
        with self.assertRaisesRegex(ValueError,"Not a reviewed"):
            discover([wrong],sites(),AT,fetch=fetch)
        future=target();future["kickoff_utc"]="2026-11-03T23:00:00Z"
        with self.assertRaisesRegex(ValueError,"not passed"):
            discover([future],sites(),AT,fetch=fetch)
        unknown=target(team="Fake College")
        with self.assertRaisesRegex(ValueError,"Not a reviewed"):
            discover([unknown],sites(),AT,fetch=fetch)

    def test_site_errors_are_reported_not_converted_to_source_labels(self):
        def offline(page,host):
            raise OSError("Blocked")
        result=discover([target()],sites(),AT,fetch=offline)
        self.assertEqual(result["source_errors"][0]["reason"],"OSError")
        self.assertEqual(result["candidate_links_found"],0)
        self.assertFalse(result["ready_to_be_starter_labels"])

    def test_bounded_number_of_schools_and_empty_worklist(self):
        result=discover([],sites(),AT,fetch=fetch)
        self.assertEqual(result["school_sites_scanned"],0)
        self.assertEqual(result["candidate_links_found"],0)
        with self.assertRaises(ValueError):
            discover([target()],sites(),AT,fetch=fetch,max_schools=MAX_SCHOOLS+1)
        with self.assertRaises(ValueError):
            discover([target()],sites(),AT,fetch=fetch,max_schools=0)

    def test_nonmatching_opponent_and_external_hyperlink_do_not_create_candidate(self):
        def alien(page,host):
            return ('<a href="/sports/football/stats/2026/alabama/boxscore/3">Score</a>'
                    '<a href="//texaslonghorns.com.evil.net/sports/football/stats/2026/ole-miss/boxscore/3">External</a>')
        r=discover([target()],sites(),AT,fetch=alien)
        self.assertEqual(r["candidate_links_found"],0)

if __name__=="__main__":unittest.main()

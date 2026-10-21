import json,tempfile,unittest
from pathlib import Path
from scripts.qb_official_news_watch import article_candidates,run,FEEDS

NOW="2026-10-21T17:00:00Z"
GAME={"game_id":"100","home":"NC State Wolfpack","away":"Virginia Cavaliers",
      "kickoff_utc":"2026-10-24T16:00:00Z"}
XML=b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Coach addresses quarterback starter for next game</title>
<link>https://gopack.com/news/2026/qb.aspx</link>
<pubDate>Wed, 21 Oct 2026 12:00:00 GMT</pubDate>
<description>A coach discusses the quarterback position.</description></item>
<item><title>Upcoming football matchup</title><link>https://gopack.com/news/2026/preview.aspx</link>
<description>Read about the defense</description></item></channel></rss>"""

class OfficialNewsCandidateTests(unittest.TestCase):
    def test_articles_not_starter_confirmations(self):
        result=article_candidates(XML,"NC State Wolfpack",[GAME],NOW)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["status"],"UNREVIEWED_NEWS_CANDIDATE")
        self.assertEqual(result[0]["potential_game_ids"],["100"])
        self.assertNotIn("kind",result[0])
        self.assertNotIn("player",result[0])
    def test_reject_unapproved_host_and_unsafe_url(self):
        x=XML.replace(b"https://gopack.com/news",b"http://gopack.com/news")
        self.assertEqual(article_candidates(x,"NC State Wolfpack",[GAME],NOW),[])
        y=XML.replace(b"https://gopack.com/news",b"https://other.com/news")
        self.assertEqual(article_candidates(y,"NC State Wolfpack",[GAME],NOW),[])
    def test_dont_make_stale_article_pregame(self):
        x=XML.replace(b"21 Oct 2026",b"01 Sep 2026")
        self.assertEqual(article_candidates(x,"NC State Wolfpack",[GAME],NOW),[])
    def test_award_honoree_not_mistaken_for_starter_news(self):
        xml=b"""<rss><channel><item><title>Quarterback named to weekly award list</title>
        <link>https://gopack.com/news/2026/award.aspx</link>
        <pubDate>Wed, 21 Oct 2026 12:00:00 GMT</pubDate>
        <description>Football quarterback named weekly honoree.</description>
        </item></channel></rss>"""
        self.assertEqual(article_candidates(xml,"NC State Wolfpack",[GAME],NOW),[])
    def test_missing_dates_do_not_become_approved(self):
        x=XML.replace(b"<pubDate>Wed, 21 Oct 2026 12:00:00 GMT</pubDate>",b"")
        rows=article_candidates(x,"NC State Wolfpack",[GAME],NOW)
        self.assertEqual(rows[0]["published_at_utc"],None)
        self.assertEqual(rows[0]["status"],"UNREVIEWED_NEWS_CANDIDATE")
    def test_no_upcoming_games_skips_all_network_calls(self):
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/"context.json";out=Path(d)/"out.json"
            inp.write_text(json.dumps({"games":[]}))
            def fail(url):raise AssertionError("should not call network")
            result=run(inp,out,reader=fail,now=NOW)
            self.assertEqual(result["manifest"]["feeds_skipped_no_upcoming_game"],len(FEEDS))
            self.assertEqual(result["candidates"],[])
    def test_fetch_failure_reports_error_and_does_not_invent_qb(self):
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/"context.json";out=Path(d)/"out.json"
            inp.write_text(json.dumps({"games":[GAME]}))
            def fail(url):raise OSError("network blocked")
            result=run(inp,out,reader=fail,now=NOW)
            self.assertEqual(result["manifest"]["feeds_failed"],1)
            self.assertEqual(result["manifest"]["confirmed_qb_starter_count"],0)
            self.assertTrue(out.is_file())
if __name__=="__main__":unittest.main()

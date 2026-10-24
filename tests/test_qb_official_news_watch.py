import json,tempfile,unittest
from pathlib import Path
from scripts.qb_official_news_watch import article_candidates,run,FEEDS,load_feed_registry

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
    def test_reviewed_registry_expands_official_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            registry=Path(d)/"registry.json"
            registry.write_text(json.dumps({"status":"REVIEWED_OFFICIAL_RSS_REGISTRY_V1",
                "feeds":[{"team":"Virginia Cavaliers","url":"https://virginiasports.com/rss/football",
                          "publisher_host":"virginiasports.com","reviewed":True}]}))
            feeds=load_feed_registry(registry)
            self.assertEqual(len(feeds),len(FEEDS)+1)
            xml=XML.replace(b"gopack.com",b"virginiasports.com")
            rows=article_candidates(xml,"Virginia Cavaliers",[GAME],NOW,feeds)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["status"],"UNREVIEWED_NEWS_CANDIDATE")
            self.assertNotIn("player",rows[0])
    def test_registry_rejects_unreviewed_or_wrong_host(self):
        with tempfile.TemporaryDirectory() as d:
            registry=Path(d)/"registry.json"
            record={"team":"Virginia Cavaliers","url":"https://untrusted.example/rss",
                    "publisher_host":"virginiasports.com","reviewed":True}
            for bad in (record,dict(record,publisher_host="untrusted.example",reviewed=False),
                        dict(record,url="http://untrusted.example/rss",
                             publisher_host="untrusted.example")):
                registry.write_text(json.dumps({"status":"REVIEWED_OFFICIAL_RSS_REGISTRY_V1",
                    "feeds":[bad]}))
                with self.assertRaises(ValueError):
                    load_feed_registry(registry)
    def test_complete_backlog_keeps_more_than_hundred_teams(self):
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/"context.json";out=Path(d)/"out.json"
            games=[{"game_id":str(i),"home":"School "+str(i),
                    "away":"Opponent "+str(i),"kickoff_utc":"2026-10-24T16:00:00Z"}
                   for i in range(55)]
            inp.write_text(json.dumps({"games":games}))
            result=run(inp,out,reader=lambda url: XML,now=NOW)
            manifest=result["manifest"]
            self.assertEqual(manifest["unconfigured_upcoming_team_slots"],110)
            self.assertEqual(manifest["backlog_unique_teams"],110)
            self.assertTrue(manifest["backlog_complete"])
            self.assertEqual(len(manifest["feed_expansion_backlog"]),110)
    def test_official_texas_and_north_carolina_feed_urls(self):
        self.assertEqual(FEEDS["Texas Longhorns"],
                         "https://texaslonghorns.com/rss?path=football")
        self.assertEqual(FEEDS["North Carolina Tar Heels"],
                         "https://goheels.com/rss?path=football")
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
            self.assertEqual(result["manifest"]["unconfigured_upcoming_team_slots"],0)
    def test_fetch_failure_reports_error_and_does_not_invent_qb(self):
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/"context.json";out=Path(d)/"out.json"
            inp.write_text(json.dumps({"games":[GAME]}))
            def fail(url):raise OSError("network blocked")
            result=run(inp,out,reader=fail,now=NOW)
            self.assertEqual(result["manifest"]["feeds_failed"],1)
            self.assertEqual(result["manifest"]["confirmed_qb_starter_count"],0)
            self.assertTrue(out.is_file())
            self.assertEqual(result["manifest"]["unconfigured_upcoming_team_slots"],1)
            self.assertEqual(result["manifest"]["unconfigured_unique_teams"],1)
            self.assertEqual(result["manifest"]["feed_expansion_backlog"][0]["team"],"Virginia Cavaliers")
if __name__=="__main__":unittest.main()

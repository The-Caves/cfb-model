import unittest
from scripts.qb_review_queue import build_queue

NOW="2026-10-21T17:00:00Z"
GAME={"game_id":"100","home":"NC State Wolfpack","away":"Virginia Cavaliers",
      "kickoff_utc":"2026-10-24T16:00:00Z","verified_qb_starters":{},
      "qb_availability_reports":[{"team":"NC State Wolfpack","player":"Test Player",
          "status":"OUT","signal_kind":"AVAILABILITY","source_url":"https://school.edu/report"}]}
def news(candidates=None):
    return {"manifest":{"status":"OFFICIAL_NEWS_REVIEW_ONLY","asof_utc":NOW,
              "feed_status":{"NC State Wolfpack":"FETCHED"}},"candidates":candidates or []}
def candidate():
    return {"team":"NC State Wolfpack","potential_game_ids":["100"],
            "status":"UNREVIEWED_NEWS_CANDIDATE","captured_at_utc":NOW,
            "published_at_utc":NOW,"title":"Quarterback starts discussion",
            "source_url":"https://gopack.com/news/2026/sample"}
class QueueTests(unittest.TestCase):
    def test_unknown_remains_unknown(self):
        queue=build_queue({"games":[GAME]},news([candidate()]),NOW)
        self.assertEqual(queue["summary"]["team_game_slots"],2)
        self.assertEqual(queue["summary"]["verified_starters"],0)
        self.assertFalse(queue["safe_for_betting"])
        home=next(r for r in queue["rows"] if r["team"]=="NC State Wolfpack")
        self.assertEqual(home["feed_status"],"FETCHED")
        self.assertEqual(home["review_priority"],"REVIEW_QB_AVAILABILITY")
        self.assertEqual(home["candidate_count"],1)
        self.assertIsNone(home["starter_player"])
        away=next(r for r in queue["rows"] if r["team"]=="Virginia Cavaliers")
        self.assertEqual(away["feed_status"],"NOT_CONFIGURED")
    def test_future_news_is_ignored(self):
        entry=candidate();entry["captured_at_utc"]="2026-10-22T00:00:00Z"
        q=build_queue({"games":[GAME]},news([entry]),NOW)
        self.assertEqual(q["summary"]["candidate_mentions"],0)
    def test_kicked_off_game_is_excluded(self):
        q=build_queue({"games":[GAME]},news(),"2026-10-24T16:01:00Z")
        self.assertEqual(q["rows"],[])
    def test_invalid_news_manifest_is_refused(self):
        item=news();item["manifest"]["status"]="AUTO_CONFIRMED"
        with self.assertRaises(ValueError):
            build_queue({"games":[GAME]},item,NOW)
if __name__=="__main__":unittest.main()

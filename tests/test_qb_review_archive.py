import unittest
from scripts.qb_review_archive import close_qb_review

GAME={"game_id":"100","home":"Home","away":"Away",
      "kickoff_utc":"2026-10-24T20:00:00Z","verified_qb_starters":{}}
START="2026-10-21T16:00:00Z"
CAPTURE="2026-10-21T16:10:00Z"
END="2026-10-21T16:15:00Z"

def records():
    return [{"game_id":"100","home":None,"team":team,"opponent":other,
             "kickoff_utc":GAME["kickoff_utc"],"starter_status":"UNKNOWN",
             "starter_player":None,"feed_status":"NOT_CONFIGURED","candidate_count":0,
             "qb_availability":[],"news_candidates":[]}
            for team,other in (("Home","Away"),("Away","Home"))]

def snapshot(games=None):
    return {"collection_started_utc":START,"asof_utc":END,
            "games":[GAME] if games is None else games}

def queue(rows=None):
    return {"status":"QB_REVIEW_RESEARCH_ONLY","betting_status":"PASS_UNVALIDATED",
            "safe_for_betting":False,"asof_utc":CAPTURE,
            "rows":records() if rows is None else rows}

class QueueArchiveTests(unittest.TestCase):
    def test_unconfirmed_starter_is_never_promoted(self):
        output=close_qb_review(queue(),snapshot())
        self.assertEqual(output["summary"]["unknown_starters"],2)
        self.assertEqual(output["summary"]["verified_starters"],0)
    def test_future_candidate_rejected(self):
        rows=records()
        rows[0]["news_candidates"]=[{"status":"UNREVIEWED_NEWS_CANDIDATE",
            "published_at_utc":"2026-10-22T00:00:00Z"}]
        with self.assertRaises(ValueError):
            close_qb_review(queue(rows),snapshot())
    def test_cannot_promote_article_to_starter(self):
        rows=records()
        rows[0]["starter_status"]="VERIFIED_SOURCE"
        rows[0]["starter_player"]="Some Player"
        with self.assertRaises(ValueError):
            close_qb_review(queue(rows),snapshot())
    def test_drop_game_that_kicks_off_during_collection(self):
        result=close_qb_review(queue(),snapshot([]))
        self.assertEqual(result["rows"],[])
    def test_missing_team_slot_is_error(self):
        with self.assertRaises(ValueError):
            close_qb_review(queue(records()[:1]),snapshot())
    def test_archive_cutoff_must_follow_queue_capture(self):
        q=queue()
        q["asof_utc"]="2026-10-21T17:00:00Z"
        with self.assertRaises(ValueError):
            close_qb_review(q,snapshot())
if __name__=="__main__":unittest.main()

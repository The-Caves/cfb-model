"""Game-week page monitor: never infer or promote a confirmed starting QB."""
import datetime as dt
import unittest
from scripts.qb_gameweek_watch import observe,text_from_html,STATUS
NOW=dt.datetime(2026,10,26,17,tzinfo=dt.timezone.utc)
URL="https://example.edu/football-preview"
def source():
    return {"status":"REVIEWED_OFFICIAL_GAMEWEEK_LINKS_NOT_QB_STARTERS","season":2026,
      "entries":[{"game_id":"401","team":"Test College","opponent":"Away School",
       "kickoff_utc":"2026-10-29T19:00:00Z","published_date":"2026-10-25",
       "preview_url":URL,"evidence_type":"OFFICIAL_GAMEWEEK_PREVIEW_NO_QB1_CLAIM",
       "starter_confirmed":False}]}
HTML="<html><nav>QB will start</nav><article><h1>Football preview</h1><p>Coach reports that QB John Smith will start at quarterback against Away School on Thursday. John had been injured but returned from his last game injury. Our football program continues competing in 2026.</p></article></html>"
class SourceMonitorTests(unittest.TestCase):
    def test_explicit_start_language_remains_review_only(self):
        result=observe(source(),NOW,reader=lambda _:HTML)
        self.assertEqual(result["status"],STATUS)
        self.assertEqual(result["summary"]["possible_start_language"],1)
        self.assertEqual(result["entries"][0]["source_change"],"FIRST_CAPTURE")
        self.assertFalse(result["entries"][0]["confirmed_starter"])
        self.assertEqual(result["confirmed_starters_added"],0)
        self.assertFalse(result["model_predictions_modified"])
    def test_changes_detected_across_runs(self):
        first=observe(source(),NOW,reader=lambda _:HTML)
        again=observe(source(),NOW+dt.timedelta(minutes=1),reader=lambda _:HTML,previous=first)
        self.assertEqual(again["entries"][0]["source_change"],"UNCHANGED")
        changed=observe(source(),NOW+dt.timedelta(minutes=2),
            reader=lambda _:HTML.replace("John Smith","Peter Jones"),previous=first)
        self.assertEqual(changed["entries"][0]["source_change"],"CHANGED_REVIEW_REQUIRED")
        self.assertEqual(changed["confirmed_starters_added"],0)
    def test_qb_stat_and_injury_not_automatically_starting(self):
        text="<article><p>QB John Smith passed for 350 yards in his previous game and may return from injury. The coaching staff is evaluating his gameweek availability this Thursday against Away School.</p></article>"
        result=observe(source(),NOW,reader=lambda _:text)
        self.assertEqual(result["summary"]["possible_start_language"],0)
        self.assertEqual(result["entries"][0]["status"],"REVIEW_ONLY_NOT_CONFIRMED")
    def test_source_fetch_failure_fails_closed(self):
        def broken(_):raise OSError("network unavailable")
        result=observe(source(),NOW,reader=broken)
        self.assertEqual(result["summary"]["fetch_failed"],1)
        self.assertEqual(result["entries"][0]["source_change"],"UNKNOWN_FETCH_FAILED")
        self.assertEqual(result["confirmed_starters_added"],0)
    def test_untrusted_url_year_or_confirmation_rejected(self):
        for field,value in (("starter_confirmed",True),("preview_url","http://unsafe.test/"),
                            ("published_date","2025-10-25")):
            payload=source();payload["entries"][0][field]=value
            with self.assertRaises(ValueError):observe(payload,NOW,reader=lambda _:HTML)
    def test_no_fetch_after_kickoff(self):
        result=observe(source(),NOW+dt.timedelta(days=5),reader=lambda _:self.fail("Should not fetch"))
        self.assertEqual(result["summary"]["future_source_pages"],0)
    def test_page_nav_and_scripts_cannot_fake_start(self):
        text=text_from_html("<nav>QB will start</nav><article><p>Normal football previews and game information for Tuesday. This is a discussion of the upcoming school event.</p><script>QB named starter</script></article>")
        self.assertNotIn("QB will start",text)
        self.assertNotIn("QB named starter",text)
if __name__=="__main__":unittest.main()

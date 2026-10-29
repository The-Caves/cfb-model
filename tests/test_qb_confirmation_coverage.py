import unittest
from scripts.qb_confirmation_coverage import build,STATUS
from scripts.qb_expected_starters import STATUS as EXPECTED
GAME={"game_id":"1","team":"A","opponent":"B","kickoff_utc":"2026-10-31T18:00:00Z",
      "is_confirmed_starter":False,"starter":"QB Two",
      "starter_status":"PROJECTED_RECENT_PASSER_AFTER_STALE_CHART",
      "confidence":"MEDIUM_UNCONFIRMED","depth_rank":2,"depth_label":"QB2",
      "chart_source_url":"https://www.ourlads.com/example",
      "last_game_leading_passer_proxy":"QB Two"}
def sources():
    return ({"status":EXPECTED,"betting_status":"PASS_UNVALIDATED",
              "observed_at_utc":"2026-10-29T15:00:00Z","games":[GAME]},
            {"status":"QB_STARTER_MANUAL_REVIEW_WORKLIST_RESEARCH_ONLY",
             "betting_status":"PASS_UNVALIDATED","rows":[{
                "game_id":"1","team":"A","opponent":"B","kickoff_utc":"2026-10-31T18:00:00Z",
                "official_athletics_homepage":"https://school.example/",
                "reviewed_official_preview_url":None,"reviewed_game_notes_link":None,
                "official_rss_url":None}]})
class ConfirmationCoverageTests(unittest.TestCase):
    def test_projection_is_named_but_not_confirmed(self):
        a,b=sources();r=build(a,b,"2026-10-29T18:00:00Z")
        self.assertEqual(r["status"],STATUS)
        self.assertEqual(r["summary"]["named_expected"],1)
        self.assertEqual(r["summary"]["confirmed"],0)
        self.assertEqual(r["summary"]["next_72h_unconfirmed"],1)
        self.assertFalse(r["rows"][0]["can_automatically_confirm_starter"])
    def test_wrong_game_does_not_inherit_old_qb(self):
        a,b=sources();b["rows"][0]["opponent"]="Wrong"
        with self.assertRaisesRegex(ValueError,"mismatched"):
            build(a,b,"2026-10-29T18:00:00Z")
if __name__=="__main__":unittest.main()

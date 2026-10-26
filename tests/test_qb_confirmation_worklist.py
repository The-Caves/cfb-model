import copy,unittest
from scripts.qb_confirmation_worklist import build,STATUS
def fixtures():
    game={"game_id":"401","kickoff_utc":"2026-10-31T16:00:00Z",
          "starter_status":"UNKNOWN","candidate_count":0,"review_priority":"UNKNOWN_NEEDS_SOURCE","feed_status":"NOT_CONFIGURED"}
    rows=[{**game,"team":"Alpha University","opponent":"Beta College"},
          {**game,"team":"Beta College","opponent":"Alpha University","candidate_count":2}]
    qb={"status":"QB_REVIEW_RESEARCH_ONLY","betting_status":"PASS_UNVALIDATED","asof_utc":"2026-10-26T16:00:00Z","rows":rows}
    def school(name):
        return {"team":name,"official_rss_url":None,
                "official_athletics_homepage":"https://example.edu/"+name.replace(" ","-"),
                "homepage_verified":False,"game_notes_url":None,
                "official_rss_registry_reviewed":False,"personnel_evidence_verified":False}
    src={"status":"SOURCE_CANDIDATES_WITH_CONNECTIVITY_AUDIT_NOT_PERSONNEL_VERIFIED",
         "schools":[school("Alpha University"),school("Beta College")]}
    return qb,src
class WorklistTests(unittest.TestCase):
    def test_unknown_remains_unknown_and_is_prioritized(self):
        qb,s=fixtures()
        r=build(qb,s)
        self.assertEqual(r["status"],STATUS)
        self.assertEqual(r["summary"]["team_slots"],2)
        self.assertEqual(r["game_specific_QB_confirmations_added"],0)
        self.assertEqual(r["rows"][0]["source_verification_status"],"SOURCE_CANDIDATE_ONLY_NO_GAME_SPECIFIC_STARTER_CONFIRMATION")
        self.assertIn("REVIEW_DATED_OFFICIAL",r["rows"][0]["source_followup"])
        self.assertTrue(r["rows"][0]["official_athletics_homepage"])
        self.assertFalse(r["rows"][0]["homepage_verified"])
    def test_duplicate_or_unmatched_school_fails(self):
        qb,s=fixtures();qb["rows"].append(copy.deepcopy(qb["rows"][0]))
        with self.assertRaises(ValueError):build(qb,s)
        qb,s=fixtures();s["schools"].pop()
        with self.assertRaises(ValueError):build(qb,s)
    def test_untrusted_or_non_https_url_fails(self):
        qb,s=fixtures()
        s["schools"][0]["official_athletics_homepage"]="http://bad.example/path"
        with self.assertRaises(ValueError):build(qb,s)
        qb,s=fixtures();qb["status"]="REVIEWED_STARTERS"
        with self.assertRaises(ValueError):build(qb,s)
    def test_source_discovery_does_not_auto_confirm(self):
        qb,s=fixtures();s["schools"][0]["game_notes_url"]="https://example.edu/game-notes"
        s["schools"][0]["personnel_evidence_verified"]=True
        board=build(qb,s)
        self.assertTrue(any(x["game_notes_verified"] for x in board["rows"]))
        self.assertTrue(all(x["starter_status"]=="UNKNOWN" for x in board["rows"]))
        self.assertFalse(board["trained_replacement_points"])
if __name__=="__main__":unittest.main()

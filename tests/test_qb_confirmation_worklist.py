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
    def test_reviewed_gameweek_previews_enrich_but_never_confirm(self):
        qb,s=fixtures()
        registry={"status":"REVIEWED_OFFICIAL_GAMEWEEK_LINKS_NOT_QB_STARTERS",
            "season":2026,"entries":[{
              "game_id":"401","team":"Alpha University","opponent":"Beta College",
              "kickoff_utc":"2026-10-31T16:00:00Z","published_date":"2026-10-29",
              "preview_url":"https://example.edu/Alpha-University/football-preview",
              "game_notes_url":None,"starter_confirmed":False,
              "evidence_type":"OFFICIAL_GAMEWEEK_PREVIEW_NO_QB1_CLAIM"}]}
        r=build(qb,s,registry)
        self.assertEqual(r["summary"]["reviewed_official_gameweek_preview_links"],1)
        self.assertEqual(r["game_specific_QB_confirmations_added"],0)
        self.assertEqual(r["rows"][1]["starter_status"],"UNKNOWN")
        self.assertTrue(any(x["reviewed_official_preview_url"] for x in r["rows"]))
    def test_recent_qb_mention_does_not_become_confirmed_starter(self):
        qb,s=fixtures()
        entry={"game_id":"401","team":"Alpha University","opponent":"Beta College",
            "kickoff_utc":"2026-10-31T16:00:00Z","published_date":"2026-10-29",
            "preview_url":"https://example.edu/Alpha-University/preview",
            "game_notes_url":None,"starter_confirmed":False,
            "evidence_type":"OFFICIAL_GAMEWEEK_PREVIEW_NO_QB1_CLAIM",
            "qb_context":{"player":"John Quarterback",
                "mention_type":"RETURNED_FROM_INJURY_IN_PREVIOUS_GAME",
                "quote":"returned after missing two games due to injury",
                "summary":"Player returned last week but not confirmed for the next football game.",
                "source_url":"https://example.edu/Alpha-University/preview"}}
        config={"status":"REVIEWED_OFFICIAL_GAMEWEEK_LINKS_NOT_QB_STARTERS",
                "season":2026,"entries":[entry]}
        board=build(qb,s,config)
        self.assertEqual(board["summary"]["official_contextual_qb_mentions_not_starting_confirmations"],1)
        record=next(x for x in board["rows"] if x["team"]=="Alpha University")
        self.assertEqual(record["contextual_qb_player"],"John Quarterback")
        self.assertEqual(record["starter_status"],"UNKNOWN")
        entry["qb_context"]["mention_type"]="OFFICIAL_STARTER_CONFIRMED"
        with self.assertRaises(ValueError):build(qb,s,config)
    def test_gameweek_mismatch_or_claim_rejected(self):
        qb,s=fixtures()
        entry={"game_id":"401","team":"Alpha University","opponent":"Beta College",
               "kickoff_utc":"2026-10-31T16:00:00Z","published_date":"2026-10-29",
               "preview_url":"https://example.edu/a","game_notes_url":None,
               "starter_confirmed":False,
               "evidence_type":"OFFICIAL_GAMEWEEK_PREVIEW_NO_QB1_CLAIM"}
        registry={"status":"REVIEWED_OFFICIAL_GAMEWEEK_LINKS_NOT_QB_STARTERS",
                  "season":2026,"entries":[entry]}
        for change in [{"starter_confirmed":True},{"opponent":"Elsewhere"},
                       {"published_date":"2025-10-30"},{"preview_url":"https://attacker.test/a"}]:
            copied=copy.deepcopy(registry)
            copied["entries"][0].update(change)
            with self.assertRaises(ValueError):build(qb,s,copied)
if __name__=="__main__":unittest.main()

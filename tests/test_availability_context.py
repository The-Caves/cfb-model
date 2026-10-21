import unittest
from scripts.availability_context import evaluate
GAME={"game_id":"123","kickoff_utc":"2026-10-24T20:00:00Z",
      "home":"Home","away":"Away"}
ISSUE="2026-10-24T17:00:00Z"
def report(team,kind="INJURY",player="QB One",position="QB",status="QUESTIONABLE",
           captured="2026-10-24T16:00:00Z",published="2026-10-24T15:00:00Z"):
    evidence=({"source_type":"OFFICIAL_TEAM_RELEASE","evidence_scope":"EXPLICIT_THIS_GAME",
               "evidence_excerpt":player+" will start at quarterback against Away.",
               "review_status":"APPROVED","opponent":("Away" if team=="Home" else "Home"),
               "reviewed_at_utc":"2026-10-24T16:30:00Z"} if kind=="QB_STARTER" else {})
    return {**evidence,"season":"2026","game_id":"123","team":team,"kind":kind,"player":player,
            "position":position,"status":status,"kickoff_utc":GAME["kickoff_utc"],
            "published_at_utc":published,"captured_at_utc":captured,
            "source_url":"https://example.edu/official-report",
            "reviewed_by":"source_audit_user"}
class PersonnelTests(unittest.TestCase):
    def test_empty_reports_never_means_healthy(self):
        p=evaluate(GAME,ISSUE,[])
        self.assertEqual(p["coverage_status"],"UNKNOWN")
        self.assertEqual(p["confirmed_qb_starters"],{})
        self.assertEqual(p["injuries"],[])
    def test_postcutoff_claim_rejected(self):
        p=evaluate(GAME,ISSUE,[report("Home",captured="2026-10-24T18:00:00Z")])
        self.assertEqual(len(p["injuries"]),0)
        self.assertTrue(p["warnings"])
    def test_reviewed_teamwide_attestations(self):
        rows=[report(t,"TEAM_REPORT","ALL","TEAM","VERIFIED") for t in ("Home","Away")]
        p=evaluate(GAME,ISSUE,rows)
        self.assertEqual(p["coverage_status"],"BOTH_TEAMS_VERIFIED")
        self.assertEqual(p["confirmed_qb_starters"],{})
        self.assertEqual(p["betting_status"],"PASS_UNVALIDATED")
    def test_official_availability_is_not_a_confirmed_starter(self):
        rows=[report("Home",kind="AVAILABILITY",player="Quarterback Alpha",
                     position="QB",status="OUT")]
        p=evaluate(GAME,ISSUE,rows)
        self.assertEqual(p["injuries"][0]["signal_kind"],"AVAILABILITY")
        self.assertEqual(p["confirmed_qb_starters"],{})
    def test_qb_only_if_sourced_confirmed(self):
        rows=[report("Home","QB_STARTER","Quarterback Alpha","QB","CONFIRMED")]
        p=evaluate(GAME,ISSUE,rows)
        self.assertEqual(p["confirmed_qb_starters"]["Home"]["player"],"Quarterback Alpha")
        self.assertEqual(p["coverage_status"],"UNKNOWN")
    def test_qb_claim_with_no_explicit_game_evidence_is_rejected(self):
        row=report("Home","QB_STARTER","One","QB","CONFIRMED")
        row.pop("evidence_scope")
        result=evaluate(GAME,ISSUE,[row])
        self.assertEqual(result["confirmed_qb_starters"],{})
        self.assertTrue(any("not explicitly game-reviewed" in w for w in result["warnings"]))
    def test_conflicting_qb_out_prevents_false_confirmed_starter(self):
        claim=report("Home","QB_STARTER","Quarterback Alpha","QB","CONFIRMED")
        out=report("Home","AVAILABILITY","Quarterback Alpha","QB","OUT")
        result=evaluate(GAME,ISSUE,[claim,out])
        self.assertEqual(result["confirmed_qb_starters"],{})
        self.assertTrue(any("conflicts with latest official QB availability" in w for w in result["warnings"]))
    def test_reject_recorded_before_publication(self):
        p=evaluate(GAME,ISSUE,[report("Home",published="2026-10-24T16:50:00Z")])
        self.assertEqual(len(p["injuries"]),0)
    def test_conflicting_latest_starters_are_not_assumed(self):
        rows=[report("Home","QB_STARTER","One","QB","CONFIRMED"),
              report("Home","QB_STARTER","Two","QB","CONFIRMED")]
        p=evaluate(GAME,ISSUE,rows)
        self.assertNotIn("Home",p["confirmed_qb_starters"])
if __name__=="__main__":unittest.main()

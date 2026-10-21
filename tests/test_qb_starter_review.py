import csv
import tempfile
import unittest
from pathlib import Path
from scripts.qb_starter_review import EVIDENCE_FIELDS, load_reviewed_qb_starters
from scripts.availability_context import evaluate

GAME={"game_id":"123","home":"Home","away":"Away","kickoff_utc":"2026-10-24T20:00:00Z"}
NOW="2026-10-24T17:00:00Z"

def claim(**overrides):
    row=dict(season="2026",game_id="123",team="Home",opponent="Away",
        player="Quarterback Alpha",kickoff_utc=GAME["kickoff_utc"],
        published_at_utc="2026-10-23T10:00:00Z",
        captured_at_utc="2026-10-23T11:00:00Z",
        reviewed_at_utc="2026-10-24T16:00:00Z",
        source_url="https://school.edu/football/official-release",
        source_type="OFFICIAL_TEAM_RELEASE",
        evidence_scope="EXPLICIT_THIS_GAME",
        evidence_excerpt="Quarterback Alpha will start at quarterback against Away.",
        review_status="APPROVED",reviewed_by="public_research_review")
    row.update(overrides)
    return row

class QBReviewTests(unittest.TestCase):
    def read(self, rows, games=None, now=NOW):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"qb.csv"
            with path.open("w",newline="") as fd:
                w=csv.DictWriter(fd,fieldnames=EVIDENCE_FIELDS)
                w.writeheader();w.writerows(rows)
            return load_reviewed_qb_starters(path,[GAME] if games is None else games,now)
    def test_empty_csv_no_invented_starter(self):
        actual,qa=self.read([])
        self.assertEqual(actual,[])
        self.assertEqual(qa["status"],"NO_SUBMITTED_QB_EVIDENCE")
    def test_verified_game_specific_evidence_enters_existing_gate(self):
        actual,qa=self.read([claim()])
        self.assertEqual(qa["accepted"],1)
        out=evaluate(GAME,NOW,actual)
        self.assertEqual(out["confirmed_qb_starters"]["Home"]["player"],"Quarterback Alpha")
        self.assertEqual(out["betting_status"],"PASS_UNVALIDATED")
    def test_projection_not_promoted(self):
        actual,qa=self.read([claim(review_status="UNREVIEWED")])
        self.assertEqual(actual,[])
        self.assertEqual(qa["reasons"][0]["reason"],"NOT_EXPLICIT_APPROVED_EVIDENCE")
    def test_depth_chart_not_a_game_confirmation(self):
        actual,_=self.read([claim(evidence_scope="DEPTH_CHART_LISTING")])
        self.assertEqual(actual,[])
    def test_wrong_opponent_or_game_id_rejected(self):
        actual,qa=self.read([claim(opponent="Other"),claim(game_id="999")])
        self.assertEqual(actual,[])
        self.assertEqual(qa["rejected"],2)
    def test_post_kickoff_source_rejected(self):
        actual,_=self.read([claim(published_at_utc="2026-10-24T21:00:00Z",
                     captured_at_utc="2026-10-24T21:10:00Z",
                     reviewed_at_utc="2026-10-24T21:15:00Z")])
        self.assertEqual(actual,[])
    def test_stale_source_from_prior_game_rejected(self):
        actual,qa=self.read([claim(published_at_utc="2026-08-25T10:00:00Z",
                                   captured_at_utc="2026-08-25T11:00:00Z")])
        self.assertEqual(actual,[])
        self.assertEqual(qa["reasons"][0]["reason"],"NOT_GAME_WEEK_EVIDENCE")
    def test_generic_depth_chart_url_cannot_prove_starter(self):
        actual,qa=self.read([claim(evidence_excerpt="Quarterback Alpha appears first in a depth chart.")])
        self.assertEqual(actual,[])
        self.assertEqual(qa["reasons"][0]["reason"],"NO_EXPLICIT_PLAYER_START_STATEMENT")
    def test_not_starting_is_not_a_confirmed_starter(self):
        bad=["Quarterback Alpha will not start at quarterback against Away.",
             "Quarterback Alpha could start at quarterback against Away.",
             "Quarterback Alpha is not starting quarterback against Away.",
             "Quarterback Alpha is expected to start at quarterback against Away."]
        for sentence in bad:
            with self.subTest(sentence=sentence):
                actual,qa=self.read([claim(evidence_excerpt=sentence)])
                self.assertEqual(actual,[])
                self.assertEqual(qa["rejected"],1)
    def test_conflicting_claims_quarantined_not_latest_wins(self):
        actual,qa=self.read([claim(),claim(player="Quarterback Beta",
            evidence_excerpt="Quarterback Beta will start at quarterback against Away.")])
        self.assertEqual(actual,[])
        self.assertEqual(qa["rejected"],2)
        self.assertEqual(sum(x["reason"]=="CONFLICTING_STARTER_CLAIMS" for x in qa["reasons"]),2)
    def test_duplicate_same_starter_not_double_counted(self):
        actual,qa=self.read([claim(),claim(reviewed_at_utc="2026-10-24T16:30:00Z")])
        self.assertEqual(len(actual),1)
        self.assertEqual(qa["accepted"],1)
    def test_untrusted_source_url_rejected(self):
        actual,_=self.read([claim(source_url="http://school.edu/report")])
        self.assertEqual(actual,[])
    def test_qb_out_blocks_confirmation(self):
        actual,_=self.read([claim()])
        unavailable={**actual[0],"kind":"AVAILABILITY","status":"OUT"}
        out=evaluate(GAME,NOW,actual+[unavailable])
        self.assertEqual(out["confirmed_qb_starters"],{})
if __name__=="__main__":
    unittest.main()

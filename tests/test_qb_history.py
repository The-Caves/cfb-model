"""Historical QB as-of snapshots: no invented starters or time leakage."""
import copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
from scripts.qb_history import observe,lookup,verify_observation,run
NOW="2026-10-22T10:00:00Z"
KICK="2026-10-24T20:00:00Z"
GAME={"game_id":"101","home":"Texas Longhorns","away":"Georgia Bulldogs",
      "kickoff_utc":KICK,"verified_qb_starters":{},"qb_availability_reports":[]}
def ctx(game=None):
    return {"asof_utc":"2026-10-22T09:45:00Z",
            "captured_at_utc":"2026-10-22T09:50:00Z",
            "games":[copy.deepcopy(game if game is not None else GAME)]}
def queue(starter_status="UNKNOWN",player=None):
    return {"status":"QB_REVIEW_RESEARCH_ONLY","asof_utc":"2026-10-22T09:55:00Z",
            "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
            "rows":[{"game_id":"101","team":"Texas Longhorns",
                     "starter_status":starter_status,"starter_player":player,
                     "candidate_count":1}]}
def claim(player="Quarterback A",**changes):
    item={"player":player,
          "source_url":"https://texaslonghorns.com/news/football/statement",
          "published_at_utc":"2026-10-22T08:00:00Z",
          "captured_at_utc":"2026-10-22T08:30:00Z",
          "reviewed_at_utc":"2026-10-22T09:00:00Z",
          "source_type":"OFFICIAL_TEAM_RELEASE",
          "evidence_scope":"EXPLICIT_THIS_GAME"}
    item.update(changes)
    return item
class Tests(unittest.TestCase):
    def test_unknown_remains_unknown_including_news_candidate(self):
        snap=observe(ctx(),queue(),NOW)
        self.assertEqual(snap["summary"]["game_team_slots"],2)
        self.assertEqual(snap["summary"]["unknown"],2)
        self.assertEqual(snap["summary"]["confirmed_reviewed"],0)
        self.assertEqual(snap["summary"]["unreviewed_news_candidates"],1)
        self.assertTrue(verify_observation(snap))
        self.assertEqual(lookup([snap],"101","Texas Longhorns",KICK[:10]+"T18:00:00Z")["status"],"UNKNOWN")
    def test_game_specific_reviewed_official_starter(self):
        g=copy.deepcopy(GAME)
        g["verified_qb_starters"]={"Texas Longhorns":claim()}
        snap=observe(ctx(g),queue("VERIFIED_SOURCE","Quarterback A"),NOW)
        texas=snap["rows"][1] if snap["rows"][0]["team"]!="Texas Longhorns" else snap["rows"][0]
        self.assertEqual(texas["starter_status"],"CONFIRMED_REVIEWED_PREKICKOFF")
        self.assertEqual(lookup([snap],"101","Texas Longhorns","2026-10-23T18:00:00Z")["player"],"Quarterback A")
        self.assertEqual(lookup([snap],"101","Georgia Bulldogs","2026-10-23T18:00:00Z")["status"],"UNKNOWN")
    def test_future_reviewed_announcement_rejected(self):
        g=copy.deepcopy(GAME)
        g["verified_qb_starters"]={"Texas Longhorns":claim(reviewed_at_utc="2026-10-23T09:00:00Z")}
        snap=observe(ctx(g),queue("VERIFIED_SOURCE","Quarterback A"),NOW)
        self.assertEqual(snap["summary"]["confirmed_reviewed"],0)
        self.assertEqual(snap["summary"]["slots_with_conflicts"],1)
    def test_queue_cannot_promote_unreviewed_news(self):
        snap=observe(ctx(),queue("VERIFIED_SOURCE","Quarterback A"),NOW)
        self.assertEqual(snap["summary"]["confirmed_reviewed"],0)
        self.assertIn("QUEUE_DISAGREES_WITH_REVIEWED_SOURCE",next(r for r in snap["rows"] if r["team"]=="Texas Longhorns")["evidence_conflicts"])
    def test_availability_conflict_quarantines_claim(self):
        g=copy.deepcopy(GAME)
        g["verified_qb_starters"]={"Texas Longhorns":claim()}
        g["qb_availability_reports"]=[{"team":"Texas Longhorns","position":"QB",
             "player":"Quarterback A","status":"OUT",
             "published_at_utc":"2026-10-22T09:00:00Z",
             "captured_at_utc":"2026-10-22T09:10:00Z",
             "source_url":"https://school.edu/out"}]
        snap=observe(ctx(g),queue("VERIFIED_SOURCE","Quarterback A"),NOW)
        self.assertEqual(snap["summary"]["confirmed_reviewed"],0)
        self.assertIn("CONFIRMED_STARTER_AVAILABILITY_CONFLICT",next(r for r in snap["rows"] if r["team"]=="Texas Longhorns")["evidence_conflicts"])
    def test_after_kickoff_slot_not_backfilled(self):
        g=copy.deepcopy(GAME)
        g["kickoff_utc"]="2026-10-22T09:00:00Z"
        with self.assertRaisesRegex(ValueError,"No pregame"):
            observe(ctx(g),queue(),NOW)
    def test_past_decision_cannot_see_later_snapshot(self):
        snap=observe(ctx(),queue(),NOW)
        self.assertEqual(lookup([snap],"101","Texas Longhorns","2026-10-22T09:59:00Z")["reason"],
                         "NO_PREDECISION_OBSERVATION")
    def test_after_kickoff_prediction_cannot_use_prior_snapshot(self):
        snap=observe(ctx(),queue(),NOW)
        self.assertEqual(lookup([snap],"101","Texas Longhorns",KICK)["status"],"UNKNOWN")
        self.assertEqual(lookup([snap],"101","Texas Longhorns",KICK)["reason"],
                         "NO_PREDECISION_OBSERVATION")
    def test_different_claims_same_game_require_review(self):
        g=copy.deepcopy(GAME)
        g["verified_qb_starters"]={"Texas Longhorns":claim("Quarterback A")}
        s1=observe(ctx(g),queue("VERIFIED_SOURCE","Quarterback A"),NOW)
        g["verified_qb_starters"]={"Texas Longhorns":claim("Quarterback B")}
        s2=observe(ctx(g),queue("VERIFIED_SOURCE","Quarterback B"),"2026-10-22T11:00:00Z")
        result=lookup([s1,s2],"101","Texas Longhorns","2026-10-23T18:00:00Z")
        self.assertEqual(result["status"],"CONFLICT_REQUIRES_REVIEW")
        self.assertIsNone(result["player"])
    def test_latest_unknown_cannot_carry_old_claim(self):
        g=copy.deepcopy(GAME)
        g["verified_qb_starters"]={"Texas Longhorns":claim()}
        s1=observe(ctx(g),queue("VERIFIED_SOURCE","Quarterback A"),NOW)
        s2=observe(ctx(),queue(),"2026-10-22T11:00:00Z")
        result=lookup([s1,s2],"101","Texas Longhorns","2026-10-23T18:00:00Z")
        self.assertEqual(result["status"],"UNKNOWN")
        self.assertIsNone(result["player"])
    def test_source_time_must_precede_observed_at(self):
        with self.assertRaisesRegex(ValueError,"newer"):
            observe(ctx(),queue(),"2026-10-22T09:47:00Z")
    def test_snapshot_integrity_blocks_postkickoff_claim(self):
        snap=observe(ctx(),queue(),NOW)
        snap["rows"][0]["observed_at_utc"]="2026-10-25T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"Postkickoff"):
            verify_observation(snap)
    def test_files_persist_without_network(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/"context.json").write_text(json.dumps(ctx()))
            (root/"queue.json").write_text(json.dumps(queue()))
            out=root/"history.json"
            result=run(root/"context.json",root/"queue.json",out,now=NOW)
            self.assertEqual(len(result["rows"]),2)
            with self.assertRaises(FileExistsError):
                run(root/"context.json",root/"queue.json",out,now=NOW)
if __name__=="__main__":
    unittest.main()

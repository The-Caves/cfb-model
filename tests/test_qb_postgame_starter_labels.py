"""Real starter labels require an explicit postgame QB flag, never passing leadership."""
import copy
import unittest
from scripts.qb_postgame_starter_labels import parse,collect,LABEL,UNKNOWN,STATUS

GAME={"game_id":"401856727","date":"2026-10-24",
      "away":"Texas A&M Aggies","home":"Alabama Crimson Tide",
      "away_score":"20","home_score":"31","kickoff_utc":"2026-10-24T19:30:00Z"}
AT="2026-10-29T16:00:00Z"

def player(name,starter=None,position="QB"):
    raw={"athlete":{"displayName":name,"position":{"abbreviation":position}}}
    if starter is not None:raw["starter"]=starter
    return raw

def payload():
    return {"header":{"competitions":[{
          "id":GAME["game_id"],"status":{"type":{"completed":True}},
          "competitors":[
            {"homeAway":"home","team":{"displayName":GAME["home"]},"score":"31"},
            {"homeAway":"away","team":{"displayName":GAME["away"]},"score":"20"}]}]},
       "boxscore":{"players":[
          {"team":{"displayName":GAME["home"]},"statistics":[{
             "name":"passing","athletes":[player("A Starter",True),player("A Backup",False)]}]},
          {"team":{"displayName":GAME["away"]},"statistics":[{
             "name":"passing","athletes":[player("B Starter")]}]}]}}

class ActualQBStarterEvidenceTests(unittest.TestCase):
    def test_accepts_only_explicit_flag_on_qb_and_retains_unknown(self):
        rows=parse(GAME,payload(),AT)
        self.assertEqual(rows[0]["starter_player"],None)
        self.assertEqual(rows[0]["label_status"],UNKNOWN)
        self.assertEqual(rows[0]["candidate_qb_passers"],["B Starter"])
        self.assertEqual(rows[1]["starter_player"],"A Starter")
        self.assertEqual(rows[1]["label_status"],LABEL)
        self.assertTrue(rows[0]["requires_manual_review"])
        self.assertFalse(rows[1]["requires_manual_review"])
        self.assertEqual(len(rows[0]["source_payload_sha256"]),64)
        self.assertTrue(rows[1]["not_from_passing_leader"])
    def test_high_pass_attempts_are_not_next_start(self):
        d=payload()
        d["boxscore"]["players"][0]["statistics"][0]["athletes"][0].pop("starter")
        rows=parse(GAME,d,AT)
        self.assertTrue(all(x["starter_player"] is None for x in rows))
    def test_double_official_qb_flags_conflict_without_training_label(self):
        d=payload();d["boxscore"]["players"][0]["statistics"][0]["athletes"][1]["starter"]=True
        rows=parse(GAME,d,AT)
        self.assertEqual(rows[1]["label_status"],"CONFLICT_MULTIPLE_EXPLICIT_QB_FLAGS")
        self.assertIsNone(rows[1]["starter_player"])
    def test_same_qb_in_two_stat_categories_is_not_two_starters(self):
        d=payload()
        d["boxscore"]["players"][0]["statistics"].append({
             "name":"rushing","athletes":[player("A Starter",True)]})
        self.assertEqual(parse(GAME,d,AT)[1]["label_status"],LABEL)
    def test_only_qb_explicit_flag_qualifies(self):
        d=payload();d["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["athlete"]["position"]["abbreviation"]="WR"
        self.assertIsNone(parse(GAME,d,AT)[1]["starter_player"])
    def test_numeric_and_string_flags_never_promote(self):
        d=payload();d["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["starter"]="true"
        self.assertIsNone(parse(GAME,d,AT)[1]["starter_player"])
        d["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["starter"]=1
        self.assertIsNone(parse(GAME,d,AT)[1]["starter_player"])
    def test_wrong_identity_score_and_unfinished_game_fail_closed(self):
        for action in ("wrong_team","wrong_final","not_completed","wrong_id"):
            d=payload()
            if action=="wrong_team":d["header"]["competitions"][0]["competitors"][0]["team"]["displayName"]="Different"
            if action=="wrong_final":d["header"]["competitions"][0]["competitors"][1]["score"]="21"
            if action=="not_completed":d["header"]["competitions"][0]["status"]["type"]["completed"]=False
            if action=="wrong_id":d["header"]["competitions"][0]["id"]="999999999"
            with self.subTest(action=action),self.assertRaises(ValueError):
                parse(GAME,d,AT)
    def test_no_player_boxscore_does_not_make_up_starters(self):
        d=payload();d["boxscore"].pop("players")
        r=parse(GAME,d,AT)
        self.assertEqual(len(r),2)
        self.assertTrue(all(v["label_status"]==UNKNOWN for v in r))
    def test_summary_capture_only_postgame(self):
        with self.assertRaisesRegex(ValueError,"Future"):
            parse(GAME,payload(),"2026-10-24T18:00:00Z")
    def test_batch_keeps_source_failures_out_of_training(self):
        d=payload()
        bad={**GAME,"game_id":"402000000"}
        x=collect([GAME,bad],AT,lambda gid:d if gid==GAME["game_id"] else {},workers=2)
        self.assertEqual(x["verified_game_identities"],1)
        self.assertEqual(x["explicit_starter_labels"],1)
        self.assertEqual(x["team_slots"],2)
        self.assertEqual(x["missing_or_rejected_games"],1)
        self.assertTrue(x["postgame_labels_never_pregame_features"])
        self.assertEqual(x["status"],STATUS)

if __name__=="__main__":unittest.main()

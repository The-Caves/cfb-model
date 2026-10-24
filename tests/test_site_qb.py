"""Current-context QB display must not promote unreviewed season stat leaders."""
import copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
from scripts.site_qb import overlay,season_passing_leader,team_ids_from_scoreboard,run,passer_from_game_summary,recent_completed_game_map,BASE
from scripts.qb_history import STATUS as QSTATUS
NOW=dt.datetime(2026,10,24,14,tzinfo=dt.timezone.utc)
GAME={"game_id":"401","home_team":"Home College","away_team":"Away College",
      "kickoff_utc":"2026-10-24T16:00:00Z"}
def board():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED","games":[copy.deepcopy(GAME)]}
def history(claim=False):
    record={"game_id":"401","team":"Home College","opponent":"Away College",
        "kickoff_utc":GAME["kickoff_utc"],"observed_at_utc":"2026-10-24T13:00:00Z",
        "starter_status":"CONFIRMED_REVIEWED_PREKICKOFF" if claim else "UNKNOWN",
        "starter_player":"Jane Quarterback" if claim else None,
        "starter_evidence":{"source_url":"https://example.edu/news/qb",
          "published_at_utc":"2026-10-23T13:00:00Z",
          "captured_at_utc":"2026-10-23T14:00:00Z",
          "reviewed_at_utc":"2026-10-23T15:00:00Z"} if claim else None,
        "evidence_conflicts":[]}
    return {"status":QSTATUS,"season":2026,"betting_status":"PASS_UNVALIDATED",
       "safe_for_betting":False,"observed_at_utc":"2026-10-24T13:00:00Z",
       "context_asof_utc":"2026-10-24T12:45:00Z",
       "review_queue_asof_utc":"2026-10-24T12:55:00Z","rows":[record]}
class Tests(unittest.TestCase):
    def test_no_source_is_unknown(self):
        r=overlay(board(),None,NOW)
        self.assertEqual(r["games"][0]["qb_home"]["status"],"UNKNOWN")
        self.assertEqual(r["qb_display"]["counts"]["unknown"],2)
    def test_recent_passer_never_confirmed(self):
        recent={"1":{"player":"Recent Passer","last_game_utc":"2026-10-17T17:00:00Z",
            "source_url":"https://www.espn.com/college-football/game/_/gameId/202"}}
        r=overlay(board(),None,NOW,{("401","Home College"):"1"},recent)
        self.assertEqual(r["games"][0]["qb_home"]["player"],"Recent Passer")
        self.assertEqual(r["games"][0]["qb_home"]["status"],"RECENT_GAME_PASSER")
        self.assertEqual(r["qb_display"]["counts"]["confirmed"],0)
        self.assertFalse(r["qb_display"]["model_features_updated"])
    def test_official_confirmed_overrides_stat_leader(self):
        r=overlay(board(),history(True),NOW,{("401","Home College"):"1"},{"1":{"player":"Other Passer","last_game_utc":"2026-10-17T17:00:00Z","source_url":"https://www.espn.com/college-football/game/_/gameId/202"}})
        self.assertEqual(r["games"][0]["qb_home"]["player"],"Jane Quarterback")
        self.assertEqual(r["games"][0]["qb_home"]["status"],"CONFIRMED_OFFICIAL")
        self.assertEqual(r["games"][0]["qb_away"]["status"],"UNKNOWN")
    def test_history_must_be_previous_capture(self):
        snap=history(True);snap["observed_at_utc"]="2026-10-25T15:00:00Z"
        with self.assertRaises(ValueError):overlay(board(),snap,NOW)
    def test_mismatched_game_ignored(self):
        snap=history(True);snap["rows"][0]["opponent"]="Other"
        r=overlay(board(),snap,NOW)
        self.assertEqual(r["games"][0]["qb_home"]["status"],"UNKNOWN")
    def test_explicit_season_category_and_name_required(self):
        data={"leaders":[{"name":"passingYards","leaders":[
            {"athlete":{"displayName":"Sam Pass","position":{"abbreviation":"QB"}}}]}]}
        self.assertEqual(season_passing_leader(data),"Sam Pass")
        self.assertIsNone(season_passing_leader({"leaders":[{"name":"rushing","leaders":data["leaders"][0]["leaders"]}]}))
        self.assertIsNone(season_passing_leader({"leaders":[{"name":"passing","leaders":[{"athlete":{"id":"444"}}]}]}))
    def test_game_identity_guards_scoreboard(self):
        fixture={"events":[{"id":"401","date":"2026-10-24T16:00:00Z",
           "competitions":[{"competitors":[{"homeAway":"home","team":{"displayName":"Home College","id":"9"}},
                 {"homeAway":"away","team":{"displayName":"Away College","id":"11"}}]}]}]}
        ids=team_ids_from_scoreboard(fixture,{"401":GAME},NOW)
        self.assertEqual(ids[("401","Home College")],"9")
        bad=copy.deepcopy(fixture);bad["events"][0]["competitions"][0]["competitors"][0]["team"]["displayName"]="Not Home"
        self.assertNotIn(("401","Home College"),team_ids_from_scoreboard(bad,{"401":GAME},NOW))
    def test_completed_box_score_passer_is_only_performance(self):
        summary={"boxscore":{"players":[
          {"team":{"id":"1","displayName":"Home College"},
           "statistics":[{"name":"passing","athletes":[
             {"athlete":{"displayName":"Passer One"},"stats":["21/31","214","1"]}]}]},
          {"team":{"id":"2","displayName":"Away College"},"statistics":[]}]}}
        self.assertEqual(passer_from_game_summary(summary,"1","Home College"),"Passer One")
        self.assertIsNone(passer_from_game_summary(summary,"2","Away College"))
        self.assertIsNone(passer_from_game_summary(summary,"1","Different"))
    def test_reject_future_and_incomplete_game_boxscore(self):
        def event(completed=True,date="2026-10-17T17:00:00Z"):
            return {"events":[{"id":"202","date":date,"status":{"type":{"completed":completed}},
                "competitions":[{"competitors":[
                    {"team":{"id":"1","displayName":"Home College"}},{"team":{"id":"2","displayName":"Away College"}}]}]}]}
        self.assertEqual(recent_completed_game_map(event(),{"1":"Home College"},NOW)["1"]["game_id"],"202")
        self.assertEqual(recent_completed_game_map(event(False),{"1":"Home College"},NOW),{})
        self.assertEqual(recent_completed_game_map(event(date="2026-10-25T17:00:00Z"),{"1":"Home College"},NOW),{})
        self.assertEqual(recent_completed_game_map(event(),{"1":"Wrong College"},NOW),{})
    def test_run_without_network_outputs_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"board.json";p.write_text(json.dumps(board()))
            result=run(p,Path(tmp)/"not_exist.json",NOW,collector=lambda *_: ({},{},[]))
            self.assertEqual(result["qb_display"]["counts"]["unknown"],2)
if __name__=="__main__":unittest.main()

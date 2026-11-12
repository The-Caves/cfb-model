"""Live CFB score status and independently frozen pre-kickoff pick matching."""
import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.site_live import live_events, overlay, STATUS, ARCHIVE

NOW="2026-11-05T21:00:00Z"
KICK="2026-11-05T19:00:00Z"
ID="401800001"

def scoreboard(state="in",completed=False,home="Akron Zips",away="Ohio Bobcats"):
    return {"events":[{
       "id":ID,"date":KICK,
       "status":{"period":3,"displayClock":"08:22","type":{
           "state":state,"completed":completed,"shortDetail":"3rd · 08:22"}},
       "competitions":[{"date":KICK,"competitors":[
           {"homeAway":"home","team":{"displayName":home},"score":"21"},
           {"homeAway":"away","team":{"displayName":away},"score":"17"}]}]}]}

def buildroot(root,capture="2026-11-05T18:30:00Z"):
    path="research_2026/site_board_snapshots/2026/11/05/run-400.json.gz"
    file=root/path
    file.parent.mkdir(parents=True,exist_ok=True)
    frozen={"status":"IMMUTABLE_DISPLAYED_RESEARCH_MARKET_SNAPSHOT",
      "betting_status":"PASS_UNVALIDATED","capture_utc":capture,
      "dashboard_run_id":"400","rows":[{
        "game_id":ID,"home":"Akron Zips","away":"Ohio Bobcats",
        "kickoff_utc":KICK,
        "v04_direct_home_points":25.1,"v04_direct_away_points":21.4,
        "v04_direct_home_margin":3.7,"v04_direct_total_points":46.5,
        "v04_research_not_promoted":True,"v04_research_ats_side":"PASS",
        "v04_research_ou_side":"UNDER",
        "market_home_spread":-2.5,"market_total":48.5,
        "market_provider":"DraftKings","market_home_moneyline":-135,
        "market_away_moneyline":115}]}
    file.write_bytes(gzip.compress(json.dumps(frozen).encode()))
    index={"status":"IMMUTABLE_DISPLAYED_RESEARCH_MARKET_SNAPSHOT",
       "schema_version":1,"runs":[{"run_id":"400","path":path,
                                    "capture_utc":capture}]}
    indexfile=root/ARCHIVE
    indexfile.parent.mkdir(parents=True,exist_ok=True)
    indexfile.write_text(json.dumps(index))
    return frozen

def board():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED",
       "forecast_run_id":"30","prospective_records":{
          "status":"ARCHIVED_PROSPECTIVE_MODEL_PERFORMANCE_RESEARCH_ONLY",
          "su":{"wins":52,"losses":33},"weekly":[{"week":"2026-W44"}]},
       "games":[{"game_id":"upcoming","home_team":"A","away_team":"B",
                 "model_home_margin":7.5}]}


class LiveSourceTests(unittest.TestCase):
    def test_espn_only_live_held_at_asof_and_previously_archived_pregame(self):
        captured=live_events(scoreboard(),NOW)
        self.assertEqual(list(captured),[ID])
        self.assertEqual(captured[ID]["home_score"],21)
        self.assertEqual(captured[ID]["away_score"],17)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            buildroot(root)
            source=board();old=copy.deepcopy(source)
            result=overlay(source,root,[("2026-11-05",captured)],NOW)
            game=result["live_games"][0]
            self.assertEqual(game["pregame"]["archived_model"],"V04 independent team scoring · research")
            self.assertEqual(game["pregame"]["archived_home_points"],25.1)
            self.assertEqual(game["pregame"]["archived_ats_side"],"PASS")
            self.assertTrue(game["pregame"]["pre_kickoff_archive_verified"])
            self.assertEqual(game["pregame"]["archived_market_provider"],"DraftKings")
            self.assertEqual(game["pregame"]["archived_market_home_moneyline"],-135)
            self.assertEqual(game["pregame"]["archived_market_away_moneyline"],115)
            self.assertIsNone(game["in_game_model_update"])
            self.assertEqual(result["prospective_records"],old["prospective_records"])
            self.assertEqual(result["games"],old["games"])
            self.assertFalse(result["live_display"]["historical_grades_changed"])

    def test_pregame_after_kickoff_must_not_be_used(self):
        events=live_events(scoreboard(),NOW)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            buildroot(root,capture="2026-11-05T20:00:00Z")
            result=overlay(board(),root,[("2026-11-05",events)],NOW)
            self.assertIsNone(result["live_games"][0]["pregame"])
            self.assertFalse(result["live_games"][0]["has_archived_pregame_model"])

    def test_completed_and_scheduled_games_not_mislabeled_live(self):
        self.assertEqual(live_events(scoreboard(state="post",completed=True),NOW),{})
        self.assertEqual(live_events(scoreboard(state="pre"),NOW),{})
        self.assertEqual(live_events(scoreboard(), "2026-11-05T17:00:00Z"),{})
        rows=live_events(scoreboard(home="Wrong Team"),NOW)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);buildroot(root)
            result=overlay(board(),root,[("2026-11-05",rows)],NOW)
            self.assertIsNone(result["live_games"][0]["pregame"])

    def test_no_live_events_does_not_erase_graded_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            result=overlay(board(),root,[],NOW)
            self.assertEqual(result["live_games"],[])
            self.assertEqual(result["prospective_records"]["su"]["wins"],52)
            self.assertFalse(result["live_display"]["in_game_model_updates_available"])

    def test_forged_future_observation_is_rejected(self):
        events=live_events(scoreboard(),NOW)
        events[ID]["source_observed_at_utc"]="2026-11-06T00:00:00Z"
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,"Future observed"):
                overlay(board(),Path(folder),[("2026-11-05",events)],NOW)


if __name__=="__main__":
    unittest.main()

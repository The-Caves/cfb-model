"""Future settlement tests: frozen source/time, missing category, fair cohorts."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts import context_archive as store
from scripts.player_prop_history import from_box_rows
from scripts.player_prop_prospective_stat_grade import grade,select_first,STATUS
from scripts.site_player_projection_archive import freeze,INDEX

KICK="2026-10-31T20:00:00Z"
OBS="2026-11-01T03:00:00Z"

def fixture():
    return [{
        "game_id":90,"season":2026,"start_date":KICK,"completed":True,
        "start_time_tbd":False,"fbs_participant":True,"home_id":10,"away_id":20,
        "home_team":"A","away_team":"B",
    }]

def box():
    games={"90":{"game_id":"90","kickoff_utc":KICK,
                  "date":"2026-10-31","home":"A","away":"B",
                  "home_id":"10","away_id":"20"}}
    raw=[
        {"game_id":90,"season":2026,"team_id":10,"athlete_id":1234,
         "athlete_name":"Athlete One","category":"rushing",
         "rushingYards":"100","rushingAttempts":"17","rushingTouchdowns":"0"},
        {"game_id":90,"season":2026,"team_id":10,"athlete_id":9876,
         "athlete_name":"Athlete Two","category":"receiving",
         "receivingYards":"0","receptions":"0","receivingTouchdowns":"0"},
    ]
    return from_box_rows(raw,games,OBS)

def archived(run,minute,projection,baseline=None):
    stamp=f"2026-10-30T23:{minute:02d}:00Z"
    rows=[
      {"game_id":"90","kickoff_utc":KICK,"home_team":"A","away_team":"B",
       "team_side":"home","team":"A","player_id":"1234","player":"Athlete One",
       "metric":"rushing_yards","model_version":"PlayerForm R1",
       "projection_conditional_yards":projection,
       "recent_four_baseline_yards":baseline,
       "original_V03_sha256":"a"*64,
       "player_participation_verified":False,
       "real_bookmaker_line":None,
       "real_bookmaker_over_probability":None,
       "source_observed_at_utc":stamp,
       "eligible_for_future_independent_player_stat_grading":True}
    ]
    return {"status":"ARCHIVED_PREKICKOFF_CONDITIONAL_PLAYER_STAT_DISPLAY_RESEARCH_ONLY",
       "schema_version":1,"season":2026,"betting_status":"PASS_UNVALIDATED",
       "safe_for_betting":False,"model_promoted":False,
       "dashboard_run_id":str(run),"captured_at_utc":stamp,
       "player_model_version":"PlayerForm R1","original_score_forecast_sha256":"a"*64,
       "summary":{"player_stat_projections":len(rows)},"rows":rows}

def setup(root,objects):
    index={"status":"ARCHIVED_PREKICKOFF_CONDITIONAL_PLAYER_STAT_DISPLAY_RESEARCH_ONLY",
           "schema_version":1,"runs":[]}
    for obj in objects:
        stamp=obj["captured_at_utc"];run=obj["dashboard_run_id"]
        path="research_2026/player_projection_snapshots/2026/10/30/run-"+run+".json.gz"
        file=root/path;file.parent.mkdir(parents=True,exist_ok=True)
        file.write_bytes(store.pack(obj))
        index["runs"].append({"run_id":run,"path":path,
            "capture_utc":stamp,
            "sha256":hashlib.sha256(store.encode(obj)).hexdigest(),
            "player_stat_projections":len(obj["rows"])})
    p=root/INDEX;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(index),encoding="utf-8")

class SettlementTests(unittest.TestCase):
    def test_first_pregame_forecast_wins_and_paired_baseline(self):
        with tempfile.TemporaryDirectory() as t:
            setup(Path(t),[archived(400,15,60,70),archived(401,30,99,80)])
            r=grade(t,fixture(),box(),OBS)
            self.assertEqual(r["status"],STATUS)
            self.assertEqual(r["eligible_unique_pre_kickoff_player_forecasts"],1)
            self.assertEqual(r["graded_recorded_player_stat_samples"],1)
            self.assertEqual(r["grade_records"][0]["forecast_run_id"],"400")
            self.assertEqual(r["grade_records"][0]["absolute_error"],40)
            self.assertEqual(r["metrics"]["rushing_yards"]["paired_mae_improvement"],10)
            self.assertFalse(r["model_promoted"])

    def test_unplayed_or_missing_player_cannot_be_zero_or_settled(self):
        with tempfile.TemporaryDirectory() as t:
            setup(Path(t),[archived(400,15,60)])
            d=fixture();d[0]["completed"]=False
            self.assertEqual(grade(t,d,box(),OBS)["graded_recorded_player_stat_samples"],0)
            b=box();b["rows"]=[x for x in b["rows"] if x["player_id"]!="1234"]
            g=grade(t,fixture(),b,OBS)
            self.assertEqual(g["graded_recorded_player_stat_samples"],0)
            self.assertEqual(g["missing_or_unsettled"]["COMPLETED_GAME_PLAYER_UNOBSERVED_DNP_UNKNOWN"],1)

    def test_observed_exact_zero_is_legitimate_when_category_recorded(self):
        with tempfile.TemporaryDirectory() as t:
            d=archived(400,15,60)
            d["rows"][0]["player_id"]="9876"
            d["rows"][0]["player"]="Athlete Two"
            d["rows"][0]["metric"]="receiving_yards"
            setup(Path(t),[d])
            r=grade(t,fixture(),box(),OBS)
            self.assertEqual(r["graded_recorded_player_stat_samples"],1)
            self.assertEqual(r["grade_records"][0]["actual_recorded_player_yards"],0)

    def test_missing_stat_category_is_not_assumed_zero(self):
        with tempfile.TemporaryDirectory() as t:
            d=archived(400,15,60)
            d["rows"][0]["metric"]="receiving_yards"
            setup(Path(t),[d])
            r=grade(t,fixture(),box(),OBS)
            self.assertEqual(r["graded_recorded_player_stat_samples"],0)
            self.assertEqual(r["missing_or_unsettled"]["PLAYER_STAT_CATEGORY_UNOBSERVED_NOT_ZERO"],1)

    def test_tampered_archive_or_future_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            d=archived(400,15,60)
            setup(Path(t),[d])
            path=Path(t)/"research_2026/player_projection_snapshots/2026/10/30/run-400.json.gz"
            d["rows"][0]["projection_conditional_yards"]=120
            path.write_bytes(store.pack(d))
            with self.assertRaises(ValueError):
                grade(t,fixture(),box(),OBS)
        with tempfile.TemporaryDirectory() as t:
            d=archived(400,15,60)
            d["rows"][0]["source_observed_at_utc"]="2026-11-01T00:00:00Z"
            setup(Path(t),[d])
            with self.assertRaises(ValueError):
                grade(t,fixture(),box(),OBS)

    def test_no_archive_yet_yields_empty_honest_status(self):
        with tempfile.TemporaryDirectory() as t:
            r=grade(t,fixture(),box(),OBS)
            self.assertEqual(r["archive_verification"]["archive_status"],"NO_ARCHIVE_INDEX_YET")
            self.assertEqual(r["eligible_unique_pre_kickoff_player_forecasts"],0)
            self.assertIsNone(r["player_category_coverage_rate"])

if __name__=="__main__":
    unittest.main()

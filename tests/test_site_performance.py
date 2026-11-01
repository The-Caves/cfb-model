"""Regression tests: real archived evidence, not placeholders or picked hindsight."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts import context_archive as store
from scripts.site_performance import compute,run,BOARD_INDEX,FINAL_INDEX,GRADE_INDEX
from scripts.site_decision_archive import STATUS as BOARD_STATUS
from scripts.weekly_profiles import canonical

NOW="2026-10-29T20:00:00Z"
KICK="2026-10-24T19:00:00Z"
FORECAST="2026-10-23T18:00:00Z"
CAPTURE="2026-10-24T17:00:00Z"
MARKET="2026-10-24T16:55:00Z"
SCORE_OBS="2026-10-24T20:20:00Z"

def sha(obj):return hashlib.sha256(store.encode(obj)).hexdigest()

class SitePerformanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.grade={"status":"OBSERVED_FORECAST_GRADED_RESEARCH_ONLY","season":2026,
            "game_id":"100","home":"A","away":"B","kickoff_utc":KICK,
            "forecast_run_id":"1","forecast_observed_utc":FORECAST,
            "frozen_forecast_row_sha256":"a"*64,"final_source_record_sha256":"b"*64,
            "final_outcome_known_at_utc":"2026-10-24T20:00:00Z",
            "final_observed_at_utc":SCORE_OBS,"forecast_model":"V03",
            "actual_home_score":28,"actual_away_score":17,
            "margin_abs_error":3.,"total_abs_error":3.,"su_correct":1,
            "ats_grade":None,"over_under_grade":None,
            "safe_for_betting":False,"model_validated":False,
            "betting_status":"PASS_UNVALIDATED"}
        self.gpath="research_2026/forecast_grades/2026/10/24/100.json.gz"
        self.grade_index={"status":"STEP3G_OBSERVED_PROSPECTIVE_GRADING_RESEARCH_ONLY",
            "season":2026,"safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
            "games":{"100":{"path":self.gpath,"grade_sha256":hashlib.sha256(canonical(self.grade)).hexdigest(),
                "forecast_row_sha256":"a"*64,"final_record_sha256":"b"*64,
                "forecast_run_id":"1"}}}
        self.final={"status":"OBSERVED_INDEPENDENT_MARKET_FINAL",
            "season":2026,"game_id":"100","home":"A","away":"B",
            "home_score":28,"away_score":17,"kickoff_utc":KICK,
            "outcome_known_at_utc":"2026-10-24T20:00:00Z",
            "observed_at_utc":SCORE_OBS,"scoreboard_sha256":"c"*64,
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
        self.fpath="research_2026/market_finals/100.json.gz"
        self.final_index={"status":"OBSERVED_MARKET_FINAL_INDEX_RESEARCH_ONLY",
            "season":2026,"safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
            "games":{"100":{"path":self.fpath,"sha256":sha(self.final),
                 **{k:self.final[k] for k in ("home","away","kickoff_utc","home_score","away_score")}}}}
        self.row={"game_id":"100","home":"A","away":"B","kickoff_utc":KICK,
            "forecast_model_version":"V03","frozen_forecast_run_id":"1","frozen_forecast_sha256":"e"*64,
            "frozen_forecast_observed_utc":FORECAST,
            "frozen_forecast_home_margin":14.,"frozen_forecast_total":48.,
            "market_home_spread":-6.5,"market_total":45.5,
            "market_provider":"TestSource","market_observed_utc":MARKET,
            "displayed_ats_side":"HOME","displayed_ou_side":"OVER"}
        self.bpath="research_2026/site_board_snapshots/2026/10/24/run-12.json.gz"
        self.bundle=self.make_bundle([self.row],CAPTURE,"12")
        self.board_index={"status":BOARD_STATUS,"schema_version":1,
            "runs":[self.entry(self.bundle,self.bpath)]}
        self.flush()

    def make_bundle(self,rows,capture,run_id):
        return {"status":BOARD_STATUS,"schema_version":1,
            "capture_utc":capture,"dashboard_run_id":run_id,
            "model_version":"V03","model_forecast_sha256":"e"*64,
            "betting_status":"PASS_UNVALIDATED","not_an_executed_bet":True,
            "summary":{"future_games":len(rows)},"rows":rows}
    def entry(self,bundle,path):
        return {"run_id":bundle["dashboard_run_id"],"path":path,
            "sha256":sha(bundle),"capture_utc":bundle["capture_utc"]}
    def write(self,path,value,packed=False):
        f=self.root/path;f.parent.mkdir(parents=True,exist_ok=True)
        f.write_bytes(store.pack(value) if packed else store.encode(value))
    def flush(self):
        self.write(GRADE_INDEX,self.grade_index);self.write(self.gpath,self.grade,True)
        self.write(FINAL_INDEX,self.final_index);self.write(self.fpath,self.final,True)
        self.write(BOARD_INDEX,self.board_index);self.write(self.bpath,self.bundle,True)

    def test_full_source_verified_su_and_original_website_choices(self):
        d=compute(self.root,NOW)
        self.assertEqual(d["su"]["wins"],1)
        self.assertEqual(d["ats"]["wins"],1)
        self.assertEqual(d["ou"]["losses"],1)
        self.assertEqual(d["scoring"]["margin_mae"],3.)
        self.assertEqual(d["scoring"]["total_mae"],3.)
        self.assertEqual(len(d["recent"]),1)
        self.assertEqual(d["recent"][0]["score"],"17–28")
        self.assertEqual(len(d["weekly"]),1)
        self.assertFalse(d["model_validated"])

    def test_quarantined_v03_ats_pass_retains_historical_su_and_ou(self):
        self.row["home_bias_quarantined"]=True
        self.row["opponent_rating_shadow_margin"]=-17.5
        self.row["displayed_ats_side"]="PASS"
        self.board_index["runs"]=[self.entry(self.bundle,self.bpath)]
        self.flush()
        report=compute(self.root,NOW)
        self.assertEqual(report["su"]["wins"],1)
        self.assertEqual(report["ats"]["decisions"],0)
        self.assertEqual(report["ou"]["losses"],1)
        self.assertEqual(report["scoring"]["duplicate_ats_snapshots_excluded"],0)
        # An attacker cannot relabel an explicit bias-suppressed pick as
        # the original computed HOME pick and collect an ATS win.
        self.row["displayed_ats_side"]="HOME"
        self.board_index["runs"]=[self.entry(self.bundle,self.bpath)]
        self.flush()
        with self.assertRaisesRegex(ValueError,"Archived website pick changed"):
            compute(self.root,NOW)

    def test_nonboolean_quarantine_provenance_rejected(self):
        self.row["home_bias_quarantined"]="false"
        self.board_index["runs"]=[self.entry(self.bundle,self.bpath)]
        self.flush()
        with self.assertRaisesRegex(ValueError,"quarantine provenance"):
            compute(self.root,NOW)

    def test_duplicate_site_refresh_cannot_count_twice_or_overwrite_earliest(self):
        b=self.make_bundle([{**self.row,"market_home_spread":-16.5,
            "displayed_ats_side":"AWAY"}],"2026-10-24T17:05:00Z","13")
        path="research_2026/site_board_snapshots/2026/10/24/run-13.json.gz"
        self.board_index["runs"].append(self.entry(b,path))
        self.write(path,b,True);self.write(BOARD_INDEX,self.board_index)
        d=compute(self.root,NOW)
        self.assertEqual(d["ats"]["wins"],1)
        self.assertEqual(d["ats"]["decisions"],1)
        self.assertEqual(d["scoring"]["duplicate_ats_snapshots_excluded"],1)

    def test_original_oct_24_site_archive_without_model_version_remains_gradeable(self):
        self.row.pop("forecast_model_version")
        self.bundle.pop("model_version")
        self.board_index["runs"]=[self.entry(self.bundle,self.bpath)]
        self.flush()
        d=compute(self.root,NOW)
        self.assertEqual(d["ats"]["wins"],1)
        self.assertEqual(d["ou"]["losses"],1)
        self.assertEqual(d["recent"][0]["forecast_model"],"V03")
        # The independently selected SU forecast has its real version.
        self.grade_index["games"]={}
        self.write(GRADE_INDEX,self.grade_index)
        d=compute(self.root,NOW)
        self.assertEqual(d["recent"][0]["forecast_model"],"LEGACY_MODEL_VERSION_NOT_CAPTURED")

    def test_partial_model_version_provenance_rejected(self):
        self.row.pop("forecast_model_version")
        self.bundle=self.make_bundle([self.row],CAPTURE,"12")
        self.board_index["runs"]=[self.entry(self.bundle,self.bpath)]
        self.flush()
        with self.assertRaisesRegex(ValueError,"chronology"):
            compute(self.root,NOW)

    def test_tampered_archived_record_fails(self):
        self.grade["su_correct"]=0
        self.write(self.gpath,self.grade,True)
        with self.assertRaisesRegex(ValueError,"checksum"):
            compute(self.root,NOW)

    def test_late_market_quote_is_rejected(self):
        self.row["market_observed_utc"]="2026-10-24T21:00:00Z"
        self.bundle=self.make_bundle([self.row],CAPTURE,"12")
        self.board_index["runs"]=[self.entry(self.bundle,self.bpath)]
        self.flush()
        with self.assertRaisesRegex(ValueError,"provenance"):
            compute(self.root,NOW)

    def test_missing_finished_game_does_not_invent_grade(self):
        self.final_index["games"]={}
        self.write(FINAL_INDEX,self.final_index)
        d=compute(self.root,NOW)
        self.assertEqual(d["ats"]["decisions"],0)
        self.assertEqual(d["ou"]["decisions"],0)
        self.assertEqual(d["scoring"]["unsettled_site_market_games"],1)
        self.assertEqual(d["su"]["decisions"],1)

    def test_new_v04_research_grades_are_separate_from_quarantined_v03(self):
        from scripts.v04_market_challenger import decide
        from scripts.v04_direct_scores import STATUS as V04_STATUS, MODEL as V04_MODEL
        self.row["home_bias_quarantined"]=True
        self.row["displayed_ats_side"]="PASS"
        self.row["v04_direct_score_model"]=V04_MODEL
        self.row["v04_direct_source_no_v03_total_reuse"]=True
        self.row["v04_research_not_promoted"]=True
        self.row["v04_direct_home_margin"]=14.
        self.row["v04_direct_total_points"]=58.
        self.row["v04_direct_home_points"]=36.
        self.row["v04_direct_away_points"]=22.
        self.row["qb_verified_at_forecast"]=2
        score={"status":V04_STATUS,"model":V04_MODEL,
               "home_margin":14.,"total_points":58.,
               "home_points":36.,"away_points":22.,
               "direct_scoring_fit_uses_v03_total":False,
               "no_market_lines_in_training":True,"model_promoted":False}
        receipt=decide(score,self.row["market_home_spread"],
             self.row["market_total"],self.row["market_provider"],
             self.row["market_observed_utc"],KICK,CAPTURE,2)
        mapping={"status":"v04_research_status","policy":"v04_research_policy",
             "ats_side":"v04_research_ats_side",
             "ou_side":"v04_research_ou_side",
             "ats_reason":"v04_research_ats_reason",
             "ou_reason":"v04_research_ou_reason",
             "raw_ats_model_market_gap":"v04_research_ats_gap",
             "raw_ou_model_market_gap":"v04_research_ou_gap",
             "market_anchored_home_margin":"v04_research_anchored_margin",
             "market_anchored_total":"v04_research_anchored_total",
             "missing_verified_qb_warning":"v04_research_qb_unknown"}
        for key,col in mapping.items():
            self.row[col]=receipt[key]
        self.board_index["runs"]=[self.entry(self.bundle,self.bpath)]
        self.flush()
        result=compute(self.root,NOW)
        self.assertEqual(result["ats"]["decisions"],0)
        v04=result["v04_challenger"]
        self.assertEqual(v04["eligible_with_quote"],{"ats":1,"ou":1})
        self.assertEqual(v04["ats"]["wins"],1)
        self.assertEqual(v04["ou"]["losses"],1)
        self.assertEqual(v04["explicit_passes"],{"ats":0,"ou":0})
        self.assertEqual(v04["v04_su_correct"],1)
        self.assertFalse(v04["model_promoted"])
        self.row["v04_research_ats_side"]="AWAY"
        # Recompute the wrapper digest to exercise the independent policy
        # validation, rather than only the outer tamper-check failure.
        self.board_index["runs"]=[self.entry(self.bundle,self.bpath)]
        self.flush()
        with self.assertRaisesRegex(ValueError,"V04 selection changed"):
            compute(self.root,NOW)

    def test_publish_to_site_dashboard_without_touching_upcoming_picks(self):
        board=self.root/"dashboard.json"
        source={"schema_version":2,"betting_status":"PASS_UNVALIDATED",
                "games":[{"game_id":"800","model_home_margin":17}]}
        board.write_text(json.dumps(source))
        d=run(self.root,board,NOW)
        self.assertEqual(d["games"],source["games"])
        self.assertEqual(d["prospective_records"]["ats"]["wins"],1)
        self.assertEqual(json.loads(board.read_text())["prospective_records"]["su"]["wins"],1)

if __name__=="__main__":unittest.main()

"""Unit tests for research-only public export."""
import datetime as dt,json,gzip,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.site_export import export_record,read_latest,INDEX
from scripts.personnel_forecast import checksum,STATUS
NOW=dt.datetime(2026,10,24,14,tzinfo=dt.timezone.utc)

def fixture():
    g={"game_id":"1","home":"Home","away":"Away","kickoff_utc":"2026-10-24T16:00:00Z",
       "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
       "reported_qb_coverage":0,"verified_team_report_coverage":1,"market":{"actual_quote_count":0},
       "policy_24_to_72h_eligible":False,
       "projection":{"predicted_home_margin":4.5,"predicted_total_points":51.0,
         "predicted_home_points":27.75,"predicted_away_points":23.25,
         "research_home_win_probability":0.59,"prediction_status":"UNVALIDATED_RESEARCH_PROJECTION"}}
    rec={"run_id":"44","forecast_observed_utc":"2026-10-24T12:00:00Z",
         "model_training":{"model":"research"},"games":[g]}
    ent={"run_id":"44","forecast_observed_utc":rec["forecast_observed_utc"],
         "forecast_sha256":checksum(rec),"actual_market_quotes":0}
    return rec,ent

class SiteExportTests(unittest.TestCase):
    def test_research_only_and_null_odds(self):
        r,e=fixture()
        with patch("scripts.site_export.verify"):d=export_record(r,e,NOW)
        self.assertEqual(d["betting_status"],"PASS_UNVALIDATED")
        self.assertEqual(d["games"][0]["model_home_margin"],4.5)
        self.assertIsNone(d["games"][0]["market_home_spread"])
        self.assertIsNone(d["prospective_records"]["ats"])
        self.assertNotIn("features",d["games"][0])
    def test_kickoff_filters(self):
        r,e=fixture()
        with patch("scripts.site_export.verify"):d=export_record(r,e,NOW+dt.timedelta(hours=3))
        self.assertEqual(d["games"],[])
    def test_checksum_gate(self):
        r,e=fixture();e["forecast_sha256"]="x"*64
        with patch("scripts.site_export.verify"),self.assertRaises(ValueError):export_record(r,e,NOW)
    def test_no_future_backdate(self):
        r,e=fixture()
        with patch("scripts.site_export.verify"),self.assertRaises(ValueError):export_record(r,e,NOW-dt.timedelta(hours=3))
    def test_no_market_export(self):
        r,e=fixture();e["actual_market_quotes"]=1
        with patch("scripts.site_export.verify"),self.assertRaises(ValueError):export_record(r,e,NOW)
    def test_path_traversal_blocked(self):
        r,e=fixture();e["path"]="../secret.json.gz"
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/INDEX;p.parent.mkdir(parents=True)
            p.write_text(json.dumps({"season":2026,"status":STATUS,"betting_status":"PASS_UNVALIDATED","runs":[e]}))
            with self.assertRaises(ValueError):read_latest(Path(tmp))
    def test_read_gzip(self):
        r,e=fixture();e["path"]="research_2026/forecasts/2026/10/24/run-44.json.gz"
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/INDEX;p.parent.mkdir(parents=True)
            p.write_text(json.dumps({"season":2026,"status":STATUS,"betting_status":"PASS_UNVALIDATED","runs":[e]}))
            f=Path(tmp)/e["path"];f.parent.mkdir(parents=True);f.write_bytes(gzip.compress(json.dumps(r).encode()))
            self.assertEqual(read_latest(Path(tmp))[0]["run_id"],"44")

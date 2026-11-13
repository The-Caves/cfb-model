"""Prospective V14 grading from first immutable source-observed website snapshot."""
import copy
import datetime as dt
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.site_decision_archive import freeze
from scripts.site_history import ARCHIVE_STATUS,FINAL_STATUS,INDEX,FINALS,_digest
from scripts.site_v14_performance import STATUS,summarize
from tests.test_site_v14_archive import board,NOW


def fixed_root(path,known="2026-11-14T23:00:00Z",twice=False):
    root=Path(path)
    instant=dt.datetime.fromisoformat(NOW.replace("Z","+00:00"))
    first=freeze(board(),instant,"888")
    receipts=[]
    for i in range(2 if twice else 1):
        snap=copy.deepcopy(first)
        if i:
            snap["capture_utc"]="2026-11-13T18:00:00+00:00"
            snap["dashboard_run_id"]="889"
        name=f"research_2026/site_board_snapshots/2026/11/13/run-{888+i}.json.gz"
        location=root/name
        location.parent.mkdir(parents=True,exist_ok=True)
        location.write_bytes(gzip.compress(json.dumps(snap).encode()))
        receipts.append({"path":name,"sha256":_digest(snap),
                         "capture_utc":snap["capture_utc"],
                         "run_id":str(888+i)})
    idx=root/INDEX
    idx.parent.mkdir(parents=True,exist_ok=True)
    idx.write_text(json.dumps({"status":ARCHIVE_STATUS,
                               "schema_version":1,"runs":receipts}))
    final=root/FINALS
    final.parent.mkdir(parents=True,exist_ok=True)
    final.write_text(json.dumps({"status":FINAL_STATUS,"season":2026,
        "safe_for_betting":False,"games":{"3":{
            "game_id":"3","home":"Home","away":"Away",
            "kickoff_utc":"2026-11-14T18:00:00Z",
            "outcome_known_at_utc":known,
            "home_score":27,"away_score":21}}}))
    return root


class V14ProspectiveGradeTests(unittest.TestCase):
    def test_first_forecast_only_and_v04_paired_same_game(self):
        with tempfile.TemporaryDirectory() as temp:
            root=fixed_root(temp,twice=True)
            result=summarize(root,"2026-11-15T12:00:00Z")
            self.assertEqual(result["status"],STATUS)
            self.assertEqual(result["first_frozen_v14_games"],1)
            self.assertEqual(result["settled_v14_games"],1)
            self.assertEqual(result["paired"]["v04_margin_error"]["n"],1)
            self.assertEqual(result["paired"]["v14_margin_error"]["n"],1)
            self.assertEqual(result["paired"]["v04_winner_correct"]["value"],1)
            self.assertFalse(result["model_promoted"])
            self.assertFalse(result["independent_validation_sufficient"])
            self.assertTrue(result["retrospective_2026_backtest_not_included"])

    def test_future_result_and_tampered_receipt_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=fixed_root(temp,known="2026-11-20T12:00:00Z")
            result=summarize(root,"2026-11-15T12:00:00Z")
            self.assertEqual(result["settled_v14_games"],0)
            self.assertEqual(result["unsettled_v14_games"],1)
        with tempfile.TemporaryDirectory() as temp:
            root=fixed_root(temp)
            snap=next(root.rglob("run-888.json.gz"))
            snap.write_bytes(gzip.compress(json.dumps({"forged":True}).encode()))
            with self.assertRaises(ValueError):
                summarize(root,"2026-11-15T12:00:00Z")

if __name__=="__main__":
    unittest.main()

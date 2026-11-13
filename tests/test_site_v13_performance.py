"""V13 prospective model grades never use retrospective recomputation."""
import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.site_decision_archive import freeze
from scripts.site_history import ARCHIVE_STATUS,FINAL_STATUS,_digest
from scripts.site_v13_performance import STATUS,summarize
from tests.test_site_v13_archive import V13ArchiveAcceptance,NOW


def source_folder(directory,final_known="2026-10-24T23:00:00Z",duplicate=False):
    root=Path(directory)
    receipt=freeze(V13ArchiveAcceptance().valid(),NOW,"888")
    files=[]
    for i in range(2 if duplicate else 1):
        snap=copy.deepcopy(receipt)
        if i:
            snap["capture_utc"]="2026-10-24T15:50:00+00:00"
            snap["dashboard_run_id"]="889"
        name=f"research_2026/site_board_snapshots/2026/10/24/run-{888+i}.json.gz"
        path=root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(gzip.compress(json.dumps(snap).encode()))
        files.append({"run_id":str(888+i),"capture_utc":snap["capture_utc"],
                      "path":name,"sha256":_digest(snap)})
    (root/"research_2026/site_board_snapshots/index.json").write_text(
        json.dumps({"status":ARCHIVE_STATUS,"schema_version":1,"runs":files}))
    (root/"research_2026/outcome_index.json").write_text(json.dumps({
        "status":FINAL_STATUS,"season":2026,"safe_for_betting":False,
        "games":{"3":{"game_id":"3","home":"Home","away":"Away",
               "kickoff_utc":"2026-10-24T17:00:00Z",
               "outcome_known_at_utc":final_known,
               "home_score":20,"away_score":27}}}))
    return root


class V13ProspectiveGrade(unittest.TestCase):
    def test_only_first_predicted_before_kickoff_and_independent_final(self):
        with tempfile.TemporaryDirectory() as name:
            root=source_folder(name,duplicate=True)
            r=summarize(root,"2026-11-13T12:00:00Z")
            self.assertEqual(r["status"],STATUS)
            self.assertEqual(r["first_frozen_pregame_v13_games"],1)
            self.assertEqual(r["settled_v13_games"],1)
            self.assertEqual(r["unsettled_v13_games"],0)
            self.assertEqual(r["scoring"]["winner_eligible"],1)
            self.assertGreaterEqual(r["scoring"]["winner_brier"],0)
            self.assertGreaterEqual(r["scoring"]["total_crps"],0)
            self.assertFalse(r["model_promoted"])
            self.assertFalse(r["independent_validation_sufficient"])
            self.assertTrue(r["original_v04_predictions_unchanged"])

    def test_never_grades_result_available_after_requested_asof(self):
        with tempfile.TemporaryDirectory() as name:
            root=source_folder(name,final_known="2026-11-20T12:00:00Z")
            r=summarize(root,"2026-11-13T12:00:00Z")
            self.assertEqual(r["settled_v13_games"],0)
            self.assertEqual(r["unsettled_v13_games"],1)
            self.assertIsNone(r["scoring"]["winner_brier"])

    def test_corrupted_immutable_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=source_folder(name)
            p=next((root/"research_2026/site_board_snapshots").rglob("run-888.json.gz"))
            p.write_bytes(gzip.compress(json.dumps({"tampered":True}).encode()))
            with self.assertRaises(ValueError):summarize(root,"2026-11-13T12:00:00Z")

if __name__=="__main__":
    unittest.main()

"""V04 controls are *archived before QB decision*, never posthoc recomputed."""
import copy
import datetime as dt
import hashlib
import json
import unittest

from scripts import context_archive as store
from scripts.candidate_shadow_grade import evaluate
from scripts.qb_v04_archive_pair import (
    enrich, read_site_snapshots, STATUS, MAX_CAPTURE_LAG_HOURS)
from scripts.site_decision_archive import INDEX as SITE_INDEX, STATUS as SITE_STATUS
from scripts.v04_direct_scores import MODEL as V04_MODEL
from test_candidate_shadow_grade import candidate, grade

NOW="2026-11-02T00:00:00Z"
QB_TIME="2026-10-29T14:00:00Z"


def sample(issued="2026-10-29T13:00:00Z",home="Home",margin=2.):
    # Test source clock must ALWAYS precede the claimed captured website
    # snapshot, even for scenarios captured far from the candidate.
    forecast_stamp=(dt.datetime.fromisoformat(issued.replace("Z","+00:00"))-
                    dt.timedelta(minutes=10)).isoformat()
    snapshot={
        "status":SITE_STATUS,"schema_version":1,"betting_status":"PASS_UNVALIDATED",
        "capture_utc":issued,"dashboard_run_id":"777",
        "model_forecast_observed_utc":forecast_stamp,
        "model_forecast_sha256":"c"*64,
        "rows":[{
            "game_id":"123","home":home,"away":"Away",
            "kickoff_utc":"2026-10-31T19:00:00Z",
            "frozen_forecast_observed_utc":forecast_stamp,
            "frozen_forecast_sha256":"c"*64,
            "v04_direct_score_model":V04_MODEL,
            "v04_direct_home_margin":margin,
            "v04_direct_source_no_v03_total_reuse":True,
            "v04_research_not_promoted":True,
            "home_bias_quarantined":True,
        }]}
    return {"snapshot":snapshot,"source_snapshot_run_id":"777",
            "source_snapshot_sha256":hashlib.sha256(store.encode(snapshot)).hexdigest()}


def match():
    q=candidate("qb")
    report=evaluate({"qb":[q],"venue":[]},[grade()],NOW)
    return report,q


class SourceV04PairTests(unittest.TestCase):
    def test_exact_preresearch_same_game_pair(self):
        report,q=match()
        paired=enrich(report,[q],[sample()])
        self.assertEqual(paired["status"],report["status"])
        self.assertEqual(paired["v04_comparison_audit"]["status"],STATUS)
        self.assertEqual(paired["v04_comparison_audit"]["same_game_v04_pair_count"],1)
        self.assertTrue(paired["v04_comparison_audit"]["fully_matched_cohort"])
        metric=paired["metrics"]["qb_conditional"]
        self.assertEqual(metric["same_game_baseline_v04_games"],1)
        self.assertEqual(metric["same_game_baseline_v04_mae"],2.)
        self.assertEqual(metric["v04_paired_subset_qb_mae"],1.)
        self.assertTrue(metric["same_game_v04_pregame_source_hashed"])
        self.assertEqual(paired["per_game"][0]["v04_paired_reference"]["site_snapshot_run_id"],"777")
        self.assertTrue(paired["per_game"][0]["v04_paired_reference"]["no_hindsight_recalculation"])
        self.assertFalse(paired["model_promoted"])
        self.assertEqual(report["metrics"]["qb_conditional"].get("same_game_baseline_v04_mae"),None)

    def test_no_snapshot_refuses_to_invent_v04_margin(self):
        report,q=match()
        paired=enrich(report,[q],[])
        a=paired["v04_comparison_audit"]
        self.assertEqual((a["qb_candidate_games"],a["same_game_v04_pair_count"]),(1,0))
        self.assertEqual(a["unpaired_game_count"],1)
        self.assertFalse(a["fully_matched_cohort"])
        self.assertIsNone(paired["metrics"]["qb_conditional"]["same_game_baseline_v04_mae"])
        self.assertFalse(paired["metrics"]["qb_conditional"]["same_game_v04_pregame_source_hashed"])

    def test_late_captured_or_too_old_or_wrong_horizon_are_unpaired(self):
        report,q=match()
        for date in ("2026-10-29T14:05:00Z","2026-10-29T07:59:00Z",
                     "2026-10-31T00:00:00Z"):
            with self.subTest(captured=date):
                result=enrich(report,[q],[sample(issued=date)])
                self.assertEqual(result["v04_comparison_audit"]["same_game_v04_pair_count"],0)
        fresh=sample()
        fresh["snapshot"]["rows"][0]["v04_direct_home_margin"]=None
        fresh["source_snapshot_sha256"]=hashlib.sha256(store.encode(fresh["snapshot"])).hexdigest()
        self.assertEqual(enrich(report,[q],[fresh])["v04_comparison_audit"]["same_game_v04_pair_count"],0)

    def test_wrong_team_and_forged_v04_control_are_rejected(self):
        report,q=match()
        wrong=sample(home="Wrong")
        with self.assertRaisesRegex(ValueError,"team or kickoff"):
            enrich(report,[q],[wrong])
        forged=sample()
        forged["snapshot"]["rows"][0]["v04_direct_source_no_v03_total_reuse"]=False
        forged["source_snapshot_sha256"]=hashlib.sha256(store.encode(forged["snapshot"])).hexdigest()
        with self.assertRaisesRegex(ValueError,"Untrusted independently archived V04"):
            enrich(report,[q],[forged])
        altered=sample()
        altered["snapshot"]["rows"][0]["v04_direct_home_margin"]=99.
        with self.assertRaisesRegex(ValueError,"source hash"):
            enrich(report,[q],[altered])

    def test_nearest_earlier_v04_captured_wins_not_later(self):
        report,q=match()
        early=sample(issued="2026-10-29T11:00:00Z",margin=-12.)
        late=sample(issued="2026-10-29T13:45:00Z",margin=3.)
        late["snapshot"]["dashboard_run_id"]="778"
        late["source_snapshot_run_id"]="778"
        late["source_snapshot_sha256"]=hashlib.sha256(store.encode(late["snapshot"])).hexdigest()
        paired=enrich(report,[q],[early,late])
        self.assertEqual(paired["per_game"][0]["v04_paired_reference"]["site_snapshot_run_id"],"778")
        self.assertEqual(paired["per_game"][0]["v04_paired_reference"]["v04_frozen_home_margin"],3.)

    def test_archive_index_and_sha_bytes_checked_and_read_bounded(self):
        report,q=match()
        entry=sample()
        path="research_2026/site_board_snapshots/2026/10/29/run-777.json.gz"
        index={"status":SITE_STATUS,"schema_version":1,"runs":[
            {"run_id":"777","capture_utc":entry["snapshot"]["capture_utc"],
             "sha256":entry["source_snapshot_sha256"],"path":path}]}
        blobs={SITE_INDEX:json.dumps(index).encode(),path:store.pack(entry["snapshot"])}
        def reader(p):return blobs.get(p)
        picked=read_site_snapshots([q],read_blob=reader)
        self.assertEqual(len(picked),1)
        self.assertEqual(enrich(report,[q],picked)["v04_comparison_audit"]["same_game_v04_pair_count"],1)
        invalid=copy.deepcopy(index)
        invalid["runs"][0]["sha256"]="0"*64
        blobs[SITE_INDEX]=json.dumps(invalid).encode()
        with self.assertRaisesRegex(ValueError,"source hash"):
            read_site_snapshots([q],read_blob=reader)
        blobs[SITE_INDEX]=json.dumps(index).encode()
        distant=copy.deepcopy(entry["snapshot"])
        distant["capture_utc"]="2026-10-24T12:00:00Z"
        index["runs"][0]["capture_utc"]=distant["capture_utc"]
        blobs[SITE_INDEX]=json.dumps(index).encode()
        def no_unneeded_read(path_requested):
            if path_requested==SITE_INDEX:return blobs[SITE_INDEX]
            raise AssertionError("Too old; source should not download")
        self.assertEqual(read_site_snapshots([q],read_blob=no_unneeded_read),[])


if __name__=="__main__":
    unittest.main()

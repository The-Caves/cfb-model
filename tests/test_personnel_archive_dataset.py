"""Step 3E fail-closed reconstruction and chronological research-only evaluation."""
import copy
import datetime as dt
import json
import unittest

from scripts.personnel_archive_dataset import (
    STATUS, _check_pregame_bundle, _check_label, audit, build_report,
    evaluation_gate, safe_path)
from scripts.personnel_results_archive import (
    _empty_index, _observe_index, _link_observed_finals, _finals,
    ROOT)
from scripts.personnel_features import sha256, join_capture
from scripts.pregame_evidence import sha
from scripts.weekly_profiles import canonical

HOME = "Texas Longhorns"
AWAY = "Georgia Bulldogs"
KICK = "2026-10-24T20:00:00Z"
CAPTURED = "2026-10-22T20:00:00Z"
ARCHIVED = "2026-10-22T20:03:00Z"
KNOWN = "2026-10-25T02:00:00Z"
PATH = ROOT+"/pregame/2026/10/22/run-123456.json.gz"


def originals():
    profile = {
        "recent_form": {
            "margin":2,"points_for":22,"points_against":20,
            "win":.5,"epa_off_adj":.1,"epa_def_adj":.2},
        "prior_game_ids":["old"]}
    profiles = {"home":{**profile,"team":HOME},
                "away":{**profile,"team":AWAY}}
    capture = {
        "status":"OBSERVED_PREGAME_RESEARCH_CAPTURE",
        "season":2026,"run_id":"123456","captured_at_utc":CAPTURED,
        "sources":{
            "score_retrieved_utc":"2026-10-22T19:40:00Z",
            "advanced_retrieved_utc":"2026-10-22T19:41:00Z",
            "context_asof_utc":"2026-10-22T19:45:00Z",
            "context_captured_utc":"2026-10-22T19:50:00Z"},
        "games":[{
            "game_id":"101","home":HOME,"away":AWAY,
            "kickoff_utc":KICK,"team_profiles":profiles,
            "team_profiles_sha256":sha(canonical(profiles)),
            "profile_source":"RETROSPECTIVE_RECONSTRUCTION_UNVERIFIED"}],
        "historical_publication_times_verified":False,
        "capture_artifact_authenticity_verified":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    joined = join_capture(capture,[],[])
    bundle = {
        "status":"OBSERVED_PREGAME_ARCHIVE_BUNDLE",
        "season":2026,"run_id":"123456","capture_sha256":sha256(capture),
        "joined_sha256":sha256(joined),
        "capture":capture,"joined":joined,
        "archived_at_utc":ARCHIVED,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    index,added = _observe_index(_empty_index(), {
        "101":(capture["games"][0],joined["games"][0])},PATH,CAPTURED)
    assert added==1
    return bundle,index


def settled():
    bundle,index=originals()
    when=dt.datetime(2026,10,25,2,tzinfo=dt.timezone.utc)
    finals=_finals([{
        "game_id":"101","home":HOME,"away":AWAY,"kickoff_utc":KICK,
        "home_score":"28","away_score":"17"}],when)
    outcomes,labels,_ = _link_observed_finals(
        index,_empty_index(),finals,when,"a"*64,
        when+dt.timedelta(minutes=1))
    assert len(labels)==1
    path,label=labels[0]
    return index,outcomes,{PATH:bundle},{path:label}


class Step3EDatasetTests(unittest.TestCase):
    def test_initial_live_like_state_has_coverage_but_no_labels(self):
        bundle,index=originals()
        result=build_report(index,_empty_index(),{PATH:bundle},{},
                            "2026-10-22T21:00:00Z")
        self.assertEqual(result["status"],STATUS)
        self.assertEqual(result["quality"]["distinct_archived_game_ids"],1)
        self.assertEqual(result["quality"]["original_bundle_files"],1)
        self.assertEqual(result["quality"]["linked_final_game_ids_total"],0)
        self.assertEqual(result["quality"]["observations_available_asof"],1)
        self.assertEqual(result["quality"]["eligible_observation_game_ids_asof"],1)
        self.assertEqual(result["quality"]["team_slots"],2)
        self.assertEqual(result["quality"]["reviewed_qb_slots"],0)
        self.assertEqual(result["quality"]["verified_report_slots"],0)
        self.assertEqual(result["quality"]["missing_value_denominator_game_ids"],1)
        self.assertFalse(result["feature_records"])
        self.assertFalse(result["postgame_labels"])
        self.assertEqual(result["evaluation"]["gate"]["status"],
                         "INSUFFICIENT_PAIRED_OBSERVED_EVIDENCE")
        self.assertFalse(result["evaluation"]["gate"]["model_ready_for_promotion"])
        self.assertFalse(result["model_promoted"])
        self.assertFalse(result["safe_for_betting"])

    def test_final_loaded_with_separate_labels_and_no_pregame_results(self):
        index,outcomes,bundles,labels=settled()
        result=build_report(index,outcomes,bundles,labels,
                            "2026-10-25T02:05:00Z")
        self.assertEqual(len(result["feature_records"]),1)
        self.assertEqual(len(result["postgame_labels"]),1)
        game=result["feature_records"][0]
        label=result["postgame_labels"][0]
        self.assertNotIn("home_score",game)
        self.assertNotIn("away_score",game)
        self.assertNotIn("settlement",game)
        self.assertEqual(label["home_score"],28)
        self.assertEqual(label["away_score"],17)
        self.assertEqual(label["game_id"],game["game_id"])
        self.assertEqual(result["quality"]["linked_final_game_ids_total"],1)
        self.assertEqual(result["evaluation"]["gate"]["status"],
                         "INSUFFICIENT_PAIRED_OBSERVED_EVIDENCE")
        self.assertFalse(result["evaluation"]["gate"]["model_ready_for_promotion"])
        self.assertFalse(result["ats_ou_grades_available"])

    def test_no_future_label_at_prior_evaluation_instant(self):
        index,outcomes,bundles,labels=settled()
        prior=build_report(index,outcomes,bundles,labels,
                           "2026-10-24T20:10:00Z")
        self.assertEqual(len(prior["feature_records"]),0)
        self.assertEqual(prior["quality"]["future_or_unavailable_labels_excluded"],1)
        self.assertEqual(prior["quality"]["observations_available_asof"],1)

    def test_bundle_hash_and_pregame_profile_mutation_rejected(self):
        b,idx=originals()
        tampered=copy.deepcopy(b)
        tampered["joined"]["games"][0]["features"]["win_rate_form"]=999.
        with self.assertRaises(ValueError):
            audit(idx,_empty_index(),{PATH:tampered},{},
                  "2026-10-22T21:00:00Z")
        tampered=copy.deepcopy(b)
        tampered["capture"]["games"][0]["team_profiles"]["home"]["recent_form"]["margin"]=999
        with self.assertRaises(ValueError):
            audit(idx,_empty_index(),{PATH:tampered},{},
                  "2026-10-22T21:00:00Z")

    def test_missing_original_capture_rejected(self):
        b,idx=originals()
        with self.assertRaisesRegex(ValueError,"Missing original"):
            audit(idx,_empty_index(),{},{},"2026-10-22T21:00:00Z")

    def test_tampered_index_metadata_rejected(self):
        b,idx=originals()
        idx["games"]["101"][0]["profile_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"metadata"):
            audit(idx,_empty_index(),{PATH:b},{},"2026-10-22T21:00:00Z")

    def test_postgame_label_hash_and_score_correction_rejected(self):
        ix,out,bs,labels=settled()
        path=next(iter(labels))
        edited=copy.deepcopy(labels)
        edited[path]["home_score"]=29
        with self.assertRaisesRegex(ValueError,"checksum"):
            audit(ix,out,bs,edited,"2026-10-25T02:05:00Z")
        changed=copy.deepcopy(out)
        changed["games"]["101"]["home_score"]=30
        with self.assertRaisesRegex(ValueError,"score/identity"):
            audit(ix,changed,bs,labels,"2026-10-25T02:05:00Z")

    def test_label_cannot_steal_another_pregame_source(self):
        ix,out,bs,labels=settled()
        altered=copy.deepcopy(out)
        altered["games"]["101"]["selected_pregame"]["path"]="research_2026/pregame/2026/10/22/run-88888.json.gz"
        with self.assertRaises(ValueError):
            audit(ix,altered,bs,labels,"2026-10-25T02:05:00Z")

    def test_deferred_final_timestamp_does_not_backfill_previously_unknown_result(self):
        ix,out,bs,labels=settled()
        last=build_report(ix,out,bs,labels,"2026-10-25T01:59:00Z")
        self.assertEqual(len(last["postgame_labels"]),0)
        after=build_report(ix,out,bs,labels,"2026-10-25T02:05:00Z")
        self.assertEqual(len(after["postgame_labels"]),1)

    def test_fail_closed_unsafe_paths_and_extra_bundles(self):
        ix,out,bs,labels=settled()
        for path in ("../secret",ROOT+"/pregame/2025/12/31/run-2.json.gz",
                     ROOT+"/pregame/2026/10/22/../../secret.json.gz",
                     ROOT+"/pregame/2026/10/22/run-123456.json"):
            with self.assertRaises(ValueError):
                safe_path(path,True)
        extra=copy.deepcopy(bs)
        extra["research_2026/pregame/2026/10/22/run-555.json.gz"]=bs[PATH]
        with self.assertRaises(ValueError):
            audit(ix,out,extra,labels,"2026-10-25T02:05:00Z")

    def test_research_diagnostics_do_not_claim_market_quality_or_promotion(self):
        gate=evaluation_gate({},[])
        self.assertFalse(gate["model_ready_for_promotion"])
        self.assertFalse(gate["independent_pbp_publication_proof_available"])
        self.assertFalse(gate["timestamped_market_su_ats_ou_available"])
        self.assertEqual(gate["status"],"INSUFFICIENT_PAIRED_OBSERVED_EVIDENCE")

    def test_full_source_capture_even_without_formal_score_attestation(self):
        ix,out,bs,labels=settled()
        result=build_report(ix,out,bs,labels,"2026-10-25T02:05:00Z")
        self.assertFalse(result["historical_publication_times_independently_verified"])
        self.assertFalse(result["quality"]["historical_source_publication_attested"])
        self.assertFalse(result["quality"]["independent_write_once_storage_attested"])

if __name__=="__main__":
    unittest.main()

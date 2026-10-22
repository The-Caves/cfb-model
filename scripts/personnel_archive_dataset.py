"""Step 3E: audited 2026 pregame/outcome dataset and research-only ablation gate.

The public GitHub context-state branch is a historical *observation* archive.
Its timestamps and hashes are checked; neither upstream publication timing nor
independent immutability is established. No hindsight backfill, bets, or picks.
"""
import argparse
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

from scripts import context_archive as github_store
from scripts.game_context import parse_time
from scripts.personnel_ablation import ablate, VARIANTS
from scripts.personnel_features import verify_joined, sha256
from scripts.personnel_results_archive import (
    _choose, _metadata, _valid_index, INDEX, OUTCOMES, ROOT,
    POLICY, STATUS as ARCHIVE_STATUS)
from scripts.pregame_evidence import get_asof_feature

STATUS = "STEP3E_AUDITED_OBSERVED_DATASET_RESEARCH_ONLY"
SHA = re.compile(r"^[0-9a-f]{64}$")
PREGAME_PATH = re.compile(r"^research_2026/pregame/(?:2026/\d{2}|2027/01)/\d{2}/run-\d+\.json\.gz$")
OUTCOME_PATH = re.compile(r"^research_2026/outcomes/(?:2026/\d{2}|2027/01)/\d{2}/\d+\.json\.gz$")


def at(value):
    return parse_time(value)


def safe_path(path, pregame):
    if type(path) is not str or not (
        PREGAME_PATH.fullmatch(path) if pregame else OUTCOME_PATH.fullmatch(path)):
        raise ValueError("Unsafe or invalid historical archive path")
    return path


def _check_clearance(obj):
    if not isinstance(obj, dict) or obj.get("safe_for_betting") is not False or (
        obj.get("betting_status") != "PASS_UNVALIDATED"):
        raise ValueError("Unexpected archived betting clearance")


def _check_pregame_bundle(path, blob):
    safe_path(path, True)
    if not isinstance(blob, dict) or blob.get("status") != "OBSERVED_PREGAME_ARCHIVE_BUNDLE" or blob.get("season") != 2026:
        raise ValueError("Invalid pregame bundle identity")
    _check_clearance(blob)
    capture, joined = blob["capture"], blob["joined"]
    _check_clearance(capture)
    _check_clearance(joined)
    verify_joined(joined)
    if capture.get("season") != 2026 or str(capture.get("run_id")) != str(blob["run_id"]) or (
        str(joined["run_id"]) != str(blob["run_id"])):
        raise ValueError("Pregame bundle run/season conflict")
    if sha256(capture) != blob["capture_sha256"] or sha256(joined) != blob["joined_sha256"] or (
        joined["profile_source_sha256"] != sha256(capture)):
        raise ValueError("Pregame bundle checksum disagreement")
    captured = at(capture["captured_at_utc"])
    if at(joined["captured_at_utc"]) != captured or at(blob["archived_at_utc"]) < captured:
        raise ValueError("Archived before original capture")
    if path != (ROOT + "/pregame/" + captured.strftime("%Y/%m/%d") +
                "/run-" + str(blob["run_id"]) + ".json.gz"):
        raise ValueError("Pregame bundle archive path mismatch")
    if capture.get("historical_publication_times_verified") is not False or (
        capture.get("capture_artifact_authenticity_verified") is not False):
        raise ValueError("Retroactive pregame proof claimed")
    rows = {str(r["game_id"]): r for r in joined["games"]}
    original = {str(g["game_id"]): g for g in capture["games"]}
    if len(rows) != len(joined["games"]) or len(original) != len(capture["games"]) or (
        set(rows) != set(original)):
        raise ValueError("Pregame bundle duplicate or missing ESPN matchup")
    for gid, g in original.items():
        get_asof_feature(capture, gid, captured.isoformat())
        j = rows[gid]
        if (g["home"], g["away"], at(g["kickoff_utc"]), g["team_profiles_sha256"]) != (
            j["home"], j["away"], at(j["kickoff_utc"]), j["profile_sha256"]):
            raise ValueError("Pregame profile/personnel game identity mismatch")
        if at(j["kickoff_utc"]) <= at(blob["archived_at_utc"]):
            raise ValueError("Late archive after game kickoff")
    return blob


def _check_label(path, record, outcome_index_row, indexed_capture, evaluation):
    safe_path(path, False)
    if (not isinstance(record, dict) or record.get("status") != "OBSERVED_POSTGAME_FINAL" or
        record.get("season") != 2026 or record.get("research_only") is not True):
        raise ValueError("Invalid postgame final evidence")
    _check_clearance(record)
    if sha256(record) != outcome_index_row["record_sha256"]:
        raise ValueError("Postgame final checksum mismatch")
    if path != outcome_index_row["archive_path"]:
        raise ValueError("Postgame label file path mismatch")
    gid = str(record["game_id"])
    if path != ROOT + "/outcomes/" + at(record["kickoff_utc"]).strftime("%Y/%m/%d") + "/" + gid + ".json.gz":
        raise ValueError("Postgame final dated path mismatch")
    if record["observation_policy"] != POLICY or record["selected_pregame"] != indexed_capture:
        raise ValueError("Final score is not linked to frozen observation")
    if (not SHA.fullmatch(str(record["source_scoreboard_sha256"])) or
        record["source_url"] != "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"):
        raise ValueError("Postgame result source not auditable")
    if (type(record["home_score"]) is not int or type(record["away_score"]) is not int or
        min(record["home_score"],record["away_score"]) < 0 or
        record["actual_margin"] != record["home_score"] - record["away_score"] or
        record["actual_total"] != record["home_score"] + record["away_score"]):
        raise ValueError("Postgame outcome arithmetic/identity invalid")
    issue = at(record["outcome_known_at_utc"])
    kickoff = at(record["kickoff_utc"])
    if not at(indexed_capture["captured_at_utc"]) < kickoff < issue <= at(record["observed_at_utc"]):
        raise ValueError("Impossible pregame/outcome timestamp order")
    if record["observed_at_utc"] and at(record["observed_at_utc"]) > evaluation:
        # A fully valid record may be unavailable at an earlier evaluation cutoff.
        return False
    return issue <= evaluation


def audit(index, outcomes, bundles, labels_by_path, evaluation_asof_utc):
    """Pure, reproducible join from independently stored bytes.

    Returns a QA board and the *exact* source-verified one-game captures/labels
    suitable for the old chronological research evaluator. Never return new
    scores mixed into per-game pregame feature vectors.
    """
    now = at(evaluation_asof_utc)
    _valid_index(index, "pregame")
    _valid_index(outcomes, "outcome")
    if not index["games"] and outcomes["games"]:
        raise ValueError("Outcomes without any historical pregame observations")
    for path, b in bundles.items():
        _check_pregame_bundle(path, b)
    by_id = {}
    unique_paths = set()
    for gid, observations in index["games"].items():
        if not gid or not isinstance(observations, list) or not observations:
            raise ValueError("Invalid per-game observation history")
        prior_stamp = None
        seen = set()
        for meta in observations:
            path = safe_path(meta["path"], True)
            unique_paths.add(path)
            if path not in bundles:
                raise ValueError("Missing original archived pregame evidence")
            blob = bundles[path]
            capture, joined = blob["capture"],blob["joined"]
            c = {str(row["game_id"]): row for row in capture["games"]}
            j = {str(row["game_id"]): row for row in joined["games"]}
            if gid not in c or gid not in j:
                raise ValueError("Archive index game missing from source capture")
            expected = _metadata(path,c[gid],j[gid],capture["captured_at_utc"])
            if expected != meta:
                raise ValueError("Index metadata mismatches original capture bytes")
            stamp = at(meta["captured_at_utc"])
            if stamp > now:
                continue  # source capture is not yet available at this evaluation cutoff
            if prior_stamp is not None and prior_stamp >= stamp:
                raise ValueError("Duplicate or unordered per-game observations")
            prior_stamp = stamp
            if stamp in seen:
                raise ValueError("Duplicate observation timestamp")
            seen.add(stamp)
            if at(blob["archived_at_utc"]) > now:
                continue  # bundle cannot enter an earlier research evaluation
            by_id.setdefault(gid, []).append(meta)
    if unique_paths != set(bundles):
        raise ValueError("Unexpected unindexed archive bundle")
    observations_total = sum(len(v) for v in by_id.values())
    selected = {}
    qa = Counter()
    for gid, history in by_id.items():
        # Unsettled games can have rescheduled kickoff versions. The most
        # recent eligible observation is only a *candidate*, not a label.
        candidates = [
            row for row in history
            if 24 <= (at(row["kickoff_utc"]) - at(row["captured_at_utc"])).total_seconds()/3600 <= 72]
        if candidates:
            selected[gid] = max(candidates,key=lambda r: at(r["captured_at_utc"]))
            qa["games_with_policy_eligible_observation"] += 1
        else:
            qa["games_missing_24_to_72h_observation"] += 1
    evaluable_rows, postgame_labels = [], []
    known_labels, delayed_labels = 0, 0
    used_label_paths = set()
    for gid, summary in sorted(outcomes["games"].items()):
        if gid not in index["games"]:
            raise ValueError("Final result is missing corresponding indexed pregame game")
        path = safe_path(summary["archive_path"], False)
        if path in used_label_paths:
            raise ValueError("Duplicate final file referenced by multiple game IDs")
        used_label_paths.add(path)
        if path not in labels_by_path:
            raise ValueError("Missing original postgame evidence bytes")
        label = labels_by_path[path]
        frozen = summary["selected_pregame"]
        if frozen not in index["games"][gid]:
            raise ValueError("Frozen result points to unindexed pregame capture")
        true_selected = _choose(index["games"][gid], at(summary["kickoff_utc"]),
                                summary["home"], summary["away"])
        if true_selected is None or frozen != true_selected:
            raise ValueError("Outcome has non-policy or revised pregame selection")
        for field in ("game_id","home","away","kickoff_utc","home_score",
                      "away_score","outcome_known_at_utc"):
            if field == "kickoff_utc":
                if at(summary[field]) != at(label[field]):
                    raise ValueError("Final index kickoff mismatch")
            elif str(summary[field]) != str(label[field]):
                raise ValueError("Postgame indexed score/identity mismatch")
        available = _check_label(path, label, summary, frozen, now)
        if not available or at(frozen["captured_at_utc"]) > now or (
            at(bundles[frozen["path"]]["archived_at_utc"]) > now):
            delayed_labels += 1
            continue
        if gid not in by_id:
            raise ValueError("Final game lacks as-of pregame source")
        original = bundles[frozen["path"]]["joined"]
        game = next((r for r in original["games"] if str(r["game_id"]) == gid),None)
        if game is None or game["record_sha256"] != frozen["personnel_record_sha256"]:
            raise ValueError("Final references tampered feature record")
        # Already validated original joined snapshot. Curate *one* genuine game
        # per observed capture so reschedules/duplicate capture files do not
        # violate the fold evaluator's game-disjoint contract.
        curated = dict(original)
        curated["games"] = [game]
        verify_joined(curated)
        evaluable_rows.append(curated)
        postgame_labels.append({
            "evidence_status": "OBSERVED_POSTGAME_FINAL",
            "game_id": gid, "home":game["home"],"away":game["away"],
            "kickoff_utc":game["kickoff_utc"],
            "home_score":label["home_score"],"away_score":label["away_score"],
            "outcome_known_at_utc":label["outcome_known_at_utc"],
            "source_url":label["source_url"]})
        known_labels += 1
    if set(labels_by_path) != used_label_paths:
        raise ValueError("Unexpected unindexed archived outcome record")
    if len(evaluable_rows) != len({r["games"][0]["game_id"] for r in evaluable_rows}):
        raise ValueError("Repeated ESPN game across audit outcomes")
    coverage = Counter()
    missing_by_feature = Counter()
    for gid, meta in selected.items():
        source = bundles[meta["path"]]["joined"]
        game = next(r for r in source["games"] if str(r["game_id"]) == gid)
        if game["record_sha256"] != meta["personnel_record_sha256"]:
            raise ValueError("Mismatched selected per-game feature digest")
        sides = game["personnel_by_side"]
        for side in ("home","away"):
            coverage["team_slots"] += 1
            coverage["reviewed_qb_slots"] += int(sides[side]["qb_reviewed"])
            coverage["verified_report_slots"] += int(sides[side]["report_verified"])
        coverage["matchups_both_reports_verified"] += int(
            sides["home"]["report_verified"] and sides["away"]["report_verified"])
        for name,value in game["features"].items():
            if value is None:
                missing_by_feature[name] += 1
    qa["labeled_final_games_known_at_evaluation"] = known_labels
    qa["future_or_unavailable_labels_excluded"] = delayed_labels
    qa["indexed_final_games_total"] = len(outcomes["games"])
    qa["unlinked_archived_matchups"] = len(index["games"])-len(outcomes["games"])
    return {
        "status": STATUS,"season":2026,"evaluation_asof_utc":now.isoformat(),
        "prediction_policy": POLICY,
        "quality": {
            "distinct_archived_game_ids":len(index["games"]),
            "original_bundle_files":len(bundles),
            "observations_available_asof":observations_total,
            "eligible_observation_game_ids_asof":len(selected),
            "linked_final_game_ids_total":len(outcomes["games"]),
            **dict(qa),
            **dict(coverage),
            "missing_features_among_selected_games": dict(sorted(missing_by_feature.items())),
            "missing_value_denominator_game_ids":len(selected),
            "historical_source_publication_attested":False,
            "independent_write_once_storage_attested":False,
        },
        "feature_records": [{
            "game_id":r["games"][0]["game_id"],
            "home":r["games"][0]["home"],"away":r["games"][0]["away"],
            "kickoff_utc":r["games"][0]["kickoff_utc"],
            "capture_utc":r["captured_at_utc"],
            "record_sha256":r["games"][0]["record_sha256"],
            "features":r["games"][0]["features"],
            "betting_status":"PASS_UNVALIDATED"
        } for r in evaluable_rows],
        "postgame_labels":postgame_labels,
        "_evaluator_captures":evaluable_rows,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}


def evaluation_gate(assessment, folds):
    # Do not promote using in-sample, retrospectively mutable EPA, or missing
    # sportsbook sources. The model itself is never promoted by this module.
    valid = [f for f in folds if f["status"] == "RESEARCH_FOLD_EVALUATED" and
             f["models"].get("profile_baseline",{}).get("status") ==
             "RETROSPECTIVE_EVALUATION_OF_CAPTURED_EVIDENCE"]
    matched = {name:sum(
        f["models"][name]["games"] for f in valid
        if f["models"].get(name,{}).get("status") ==
        "RETROSPECTIVE_EVALUATION_OF_CAPTURED_EVIDENCE")
        for name in VARIANTS if name != "profile_baseline"}
    n = sum(f["models"]["profile_baseline"]["games"] for f in valid)
    threshold_met = len(valid)>=3 and n>=60 and all(
        len([f for f in valid if f["models"].get(name,{}).get("status") ==
             "RETROSPECTIVE_EVALUATION_OF_CAPTURED_EVIDENCE"])>=3 and
        matched[name] == n for name in matched)
    return {
        "observed_research_training_and_test_thresholds_met":threshold_met,
        "evaluated_walkforward_folds":len(valid),
        "tested_games_in_folds":n,
        "variant_matched_test_games":matched,
        "required_minimum_heldout_folds":3,
        "required_minimum_heldout_games":60,
        "independent_pbp_publication_proof_available":False,
        "timestamped_market_su_ats_ou_available":False,
        "statistical_significance_established":False,
        "model_ready_for_promotion":False,
        "model_promoted":False,
        "status": ("RESEARCH_DIAGNOSTICS_ONLY" if threshold_met
                   else "INSUFFICIENT_PAIRED_OBSERVED_EVIDENCE")}


def build_report(index, outcomes, bundles, labels, asof_utc):
    board = audit(index,outcomes,bundles,labels,asof_utc)
    captures = board.pop("_evaluator_captures")
    diagnostics = ablate(captures, board["postgame_labels"], asof_utc,
                        min_train_games=90, min_test_games=20)
    board["evaluation"] = {
        "status":diagnostics["status"],"folds":diagnostics["folds"],
        "aggregates":diagnostics["aggregate"],
        "comparisons":diagnostics["comparisons"],
        "qa":diagnostics["qa"],
        "game_selection_policy":diagnostics["prediction_policy"],
        "gate":evaluation_gate(board,diagnostics["folds"]),
        "model_promoted":False,
        "betting_status":"PASS_UNVALIDATED",
    }
    board["postgame_labels_present_in_feature_records"] = False
    board["ats_ou_grades_available"] = False
    board["historical_publication_times_independently_verified"] = False
    board["statistical_significance_established"] = False
    board["model_promoted"] = False
    return board


def read_context_state():
    idx = github_store.get_blob_file(INDEX)
    outs = github_store.get_blob_file(OUTCOMES)
    if idx is None or outs is None:
        raise ValueError("Step 3D archived pregame/outcome indexes not initialized")
    index = json.loads(idx)
    outcome_index = json.loads(outs)
    _valid_index(index,"pregame")
    _valid_index(outcome_index,"outcome")
    prepaths = sorted({safe_path(meta["path"],True)
                       for v in index["games"].values() for meta in v})
    outcome_paths = sorted({safe_path(row["archive_path"],False)
                            for row in outcome_index["games"].values()})
    bundle = {}
    outcome = {}
    for path in prepaths:
        blob = github_store.get_blob_file(path)
        if blob is None:
            raise ValueError("Missing GitHub history pregame bundle")
        bundle[path] = github_store.unpack(blob)
    for path in outcome_paths:
        blob = github_store.get_blob_file(path)
        if blob is None:
            raise ValueError("Missing GitHub history result")
        outcome[path] = github_store.unpack(blob)
    return index, outcome_index, bundle, outcome


def run(output, evaluation_asof_utc=None):
    when = evaluation_asof_utc or dt.datetime.now(dt.timezone.utc).isoformat()
    board = build_report(*read_context_state(),when)
    root = Path(output)
    root.mkdir(parents=True,exist_ok=True)
    outputs = {
        "quality.json": {
            "status":board["status"],"quality":board["quality"],
            "evaluation_gate":board["evaluation"]["gate"],
            "evaluated_at_utc":board["evaluation_asof_utc"],
            "betting_status":"PASS_UNVALIDATED"},
        "pregame_features.json": board["feature_records"],
        "postgame_labels.json": board["postgame_labels"],
        "personnel_ablation.json": board["evaluation"],
    }
    if any(root.joinpath(name).exists() for name in outputs):
        raise FileExistsError("Refusing to overwrite historical dataset audit")
    for name,obj in outputs.items():
        with root.joinpath(name).open("x",encoding="utf-8") as handle:
            json.dump(obj,handle,sort_keys=True,indent=2,allow_nan=False)
            handle.write("\n")
    print(json.dumps({"status":board["status"],
                      "distinct_archived_game_ids":board["quality"]["distinct_archived_game_ids"],
                      "linked_finals":board["quality"]["linked_final_game_ids_total"],
                      "matched_evaluable":len(board["postgame_labels"]),
                      "gate":board["evaluation"]["gate"]["status"],
                      "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}))
    return board


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    p.add_argument("--evaluation-asof-utc",default=None)
    args=p.parse_args()
    run(args.output,args.evaluation_asof_utc)

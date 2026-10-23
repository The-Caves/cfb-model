"""Step 3D — free GitHub pregame/settlement archive with explicit as-of joins.

Public football data only. Captures retain original bytes and checksums; labels
are saved separately. Git history is NOT independent immutable attestation.
Only actual observed pregame evidence qualifies, not recreated September data.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from scripts import context_archive as store
from scripts.game_context import parse_time
from scripts.pregame_evidence import get_asof_feature
from scripts.personnel_features import verify_joined, sha256 as digest
from scripts.weekly_profiles import canonical

ROOT = "research_2026"
INDEX = ROOT + "/pregame_index.json"
OUTCOMES = ROOT + "/outcome_index.json"
STATUS = "ASOF_OUTCOME_ARCHIVE_RESEARCH_ONLY"
POLICY = "LATEST_OBSERVED_24_TO_72_HOURS_PREKICKOFF"
MAX_RUN_AGE_SECONDS = 1800


def _hash(blob):
    return hashlib.sha256(blob).hexdigest()


def _time(value):
    return parse_time(value)


def _valid_index(obj, name):
    if not isinstance(obj, dict) or obj.get("status") != STATUS or obj.get("season") != 2026:
        raise ValueError("Invalid archived " + name + " manifest")
    if obj.get("safe_for_betting") is not False or obj.get("betting_status") != "PASS_UNVALIDATED":
        raise ValueError("Unexpected betting status for " + name)
    if not isinstance(obj.get("games"), dict):
        raise ValueError("Malformed archived " + name + " index")


def _fresh_capture(capture, joined, now, expected_run):
    if not str(expected_run).isdigit() or str(capture.get("run_id")) != str(expected_run):
        raise ValueError("Run ID does not match current workflow")
    if str(joined.get("run_id")) != str(expected_run):
        raise ValueError("Joined source run ID mismatch")
    verify_joined(joined)
    if (capture.get("season") != 2026 or
        capture.get("historical_publication_times_verified") is not False or
        capture.get("capture_artifact_authenticity_verified") is not False or
        capture.get("safe_for_betting") is not False or
        capture.get("betting_status") != "PASS_UNVALIDATED"):
        raise ValueError("Unsupported pregame capture provenance")
    stamp = _time(capture["captured_at_utc"])
    observed = _time(joined["captured_at_utc"])
    if stamp != observed or not 0 <= (now-stamp).total_seconds() <= MAX_RUN_AGE_SECONDS:
        raise ValueError("Unfresh capture or mismatched observation time")
    if joined["profile_source_sha256"] != digest(capture):
        raise ValueError("Profile capture source digest mismatch")
    cgames = {str(x["game_id"]): x for x in capture["games"]}
    jgames = {str(x["game_id"]): x for x in joined["games"]}
    if len(cgames) != len(capture["games"]) or set(cgames) != set(jgames):
        raise ValueError("Incomplete joined capture")
    for gid, g in cgames.items():
        get_asof_feature(capture, gid, stamp.isoformat())
        j = jgames[gid]
        if (g["home"], g["away"], _time(g["kickoff_utc"])) != (
            j["home"], j["away"], _time(j["kickoff_utc"])):
            raise ValueError("Prematchup identity discrepancy")
        if _time(g["kickoff_utc"]) <= stamp:
            raise ValueError("Postkickoff pregame capture")
    return cgames, jgames


def _empty_index():
    return {"status": STATUS, "season": 2026, "games": {},
            "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"}


def _valid_manifest(manifest, now):
    if manifest.get("status") != "SUCCESS" or manifest.get("failures") or (
        manifest.get("scoreboard_date_timezone") != "America/New_York"):
        raise ValueError("Incomplete, unverified score ingestion")
    retrieved = _time(manifest["retrieved_at_utc"])
    if retrieved > now or (now-retrieved).total_seconds() > MAX_RUN_AGE_SECONDS:
        raise ValueError("Scores not freshly captured")
    return retrieved


def _finals(rows, retrieved):
    seen = set()
    finals = {}
    for r in rows:
        gid = str(r["game_id"])
        if gid in seen:
            raise ValueError("Duplicate ESPN final ID")
        seen.add(gid)
        kickoff = _time(r["kickoff_utc"])
        if kickoff >= retrieved:
            raise ValueError("Future result in completed-game ledger")
        home, away = r["home"], r["away"]
        if not home or not away or home == away:
            raise ValueError("Invalid completed-game identity")
        scores = {}
        for key in ("home_score", "away_score"):
            text = str(r[key])
            if not text.isdigit():
                raise ValueError("Noninteger final score")
            scores[key] = int(text)
        finals[gid] = {"game_id": gid, "home": home, "away": away,
                       "kickoff_utc": kickoff.isoformat(),
                       "home_score": scores["home_score"],
                       "away_score": scores["away_score"]}
    return finals


def _metadata(path, g, j, captured):
    return {"path": path, "captured_at_utc": captured,
            "game_id": str(g["game_id"]), "home": g["home"], "away": g["away"],
            "kickoff_utc": g["kickoff_utc"],
            "profile_sha256": g["team_profiles_sha256"],
            "personnel_record_sha256": j["record_sha256"],
            "historical_publication_times_verified": False}


def _observe_index(index, current, artifact_path, captured):
    result = json.loads(json.dumps(index))
    _valid_index(result, "pregame")
    additions = 0
    for gid, (g, j) in current.items():
        meta = _metadata(artifact_path, g, j, captured)
        rows = result["games"].setdefault(gid, [])
        if not isinstance(rows, list):
            raise ValueError("Invalid pregame index entries")
        for old in rows:
            if (old["home"], old["away"]) != (meta["home"], meta["away"]):
                raise ValueError("Opposing team identity changed across observations")
            # A game may genuinely be rescheduled. Keep both timestamped
            # versions and only select observations matching the played kickoff.
        match = [row for row in rows if row["path"] == artifact_path]
        if match:
            if len(match) != 1 or match[0] != meta:
                raise ValueError("Conflicting retry of pregame capture")
            continue
        if any(_time(row["captured_at_utc"]) == _time(captured) for row in rows):
            raise ValueError("Duplicate observation time")
        rows.append(meta)
        rows.sort(key=lambda x: _time(x["captured_at_utc"]))
        additions += 1
    return result, additions


def _choose(rows, kickoff, home=None, away=None):
    eligible = [r for r in rows if
        _time(r["kickoff_utc"]) == kickoff and
        (home is None or r["home"] == home) and
        (away is None or r["away"] == away) and
        24 <= (kickoff-_time(r["captured_at_utc"])).total_seconds()/3600 <= 72]
    if not eligible:
        return None
    return max(eligible, key=lambda r:_time(r["captured_at_utc"]))


def _link_observed_finals(index, outcome_index, finals, retrieved, source_sha256, now):
    """Only link previously observed time-valid game data to later final scores."""
    _valid_index(index, "pregame")
    _valid_index(outcome_index, "outcome")
    next_outcomes = json.loads(json.dumps(outcome_index))
    created = []
    pending = Counter()
    for gid, observations in sorted(index["games"].items()):
        final = finals.get(gid)
        if final is None:
            pending["no_observed_final_yet"] += 1
            continue
        match = _choose(observations, _time(final["kickoff_utc"]), final["home"], final["away"])
        if match is None:
            pending["missing_24_to_72_hour_capture"] += 1
            continue
        if (final["home"], final["away"], _time(final["kickoff_utc"])) != (
            match["home"], match["away"], _time(match["kickoff_utc"])):
            pending["espn_identity_mismatch"] += 1
            continue
        if _time(match["captured_at_utc"]) >= _time(final["kickoff_utc"]):
            raise ValueError("Postkickoff pregame observation selected")
        previous = next_outcomes["games"].get(gid)
        if previous:
            # Never revise a final label or a chosen pregame observation silently.
            if (previous["home_score"],previous["away_score"]) != (
                final["home_score"], final["away_score"]):
                pending["conflicting_later_score_requires_review"] += 1
            elif previous["selected_pregame"] != match:
                pending["existing_observation_selection_frozen"] += 1
            else:
                pending["already_archived"] += 1
            continue
        outcome_path = ROOT + "/outcomes/" + _time(final["kickoff_utc"]).strftime(
            "%Y/%m/%d") + "/" + gid + ".json.gz"
        record = {
            "status": "OBSERVED_POSTGAME_FINAL",
            "season": 2026, **final,
            "selected_pregame": match,
            "observation_policy": POLICY,
            "source_url": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
            "source_scoreboard_sha256": source_sha256,
            "outcome_known_at_utc": retrieved.isoformat(),
            "observed_at_utc": now.isoformat(),
            "actual_margin": final["home_score"]-final["away_score"],
            "actual_total": final["home_score"]+final["away_score"],
            "research_only": True, "safe_for_betting": False,
            "betting_status": "PASS_UNVALIDATED"}
        next_outcomes["games"][gid] = {**final,
            "selected_pregame":match,"outcome_known_at_utc":retrieved.isoformat(),
            "archive_path": outcome_path,"record_sha256":digest(record)}
        created.append((outcome_path, record))
    return next_outcomes, created, pending


def plan(capture, joined, index, outcome_index, games, scoreboard_manifest,
         now_utc, run_id, source_sha256):
    """Pure planning; never use final results to select future pregame inputs."""
    now = _time(now_utc)
    cgames, jgames = _fresh_capture(capture, joined, now, run_id)
    retrieved = _valid_manifest(scoreboard_manifest, now)
    finals = _finals(games, retrieved)
    _valid_index(index, "pregame")
    _valid_index(outcome_index, "outcome")
    date = _time(capture["captured_at_utc"]).strftime("%Y/%m/%d")
    archive_file = ROOT + "/pregame/" + date + "/run-" + str(run_id) + ".json.gz"
    candidates = {gid: (g, jgames[gid]) for gid,g in cgames.items()}
    next_index, added = _observe_index(index, candidates, archive_file, capture["captured_at_utc"])
    next_outcomes, created, pending = _link_observed_finals(
        next_index, outcome_index, finals, retrieved, source_sha256, now)
    bundle = {
        "status": "OBSERVED_PREGAME_ARCHIVE_BUNDLE",
        "season": 2026, "run_id": str(run_id),
        "capture_sha256": digest(capture),
        "joined_sha256": digest(joined),
        "capture": capture, "joined": joined,
        "archived_at_utc": now.isoformat(),
        "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"}
    summary = {
        "status": STATUS, "run_id": str(run_id), "archived_at_utc": now.isoformat(),
        "new_pregame_game_slots": added,
        "distinct_games_observed": len(next_index["games"]),
        "newly_linked_final_games": len(created),
        "cumulative_linked_final_games": len(next_outcomes["games"]),
        "pending": dict(pending),
        "pregame_path": archive_file,
        "external_immutability_verified": False,
        "scoreboard_publication_time_verified": False,
        "historical_publication_times_verified": False,
        "model_promoted": False, "safe_for_betting": False,
        "betting_status": "PASS_UNVALIDATED"}
    return bundle, next_index, next_outcomes, created, summary


def _read_json(path):
    blob = store.get_blob_file(path)
    return json.loads(blob) if blob is not None else _empty_index()


def _commit_material(material, run_id):
    repo = store.repo_path()
    parent = store.branch_head()
    commit = store.api("GET",repo+"/git/commits/"+parent)
    entries = []
    import base64
    for path, content in material.items():
        if path not in (INDEX, OUTCOMES, ROOT+"/summary.json",
                        ROOT+"/forecast_index.json",
                        ROOT+"/forecast_grades_index.json",
                        ROOT+"/free_market_comparisons/index.json"):
            prior = store.get_blob_file(path)
            if prior is not None and prior != content:
                raise ValueError("Immutable archive collision")
        blob = store.api("POST",repo+"/git/blobs",{
            "content":base64.b64encode(content).decode(),"encoding":"base64"})
        entries.append({"path":path,"mode":"100644","type":"blob","sha":blob["sha"]})
    tree = store.api("POST",repo+"/git/trees",{
        "base_tree":commit["tree"]["sha"],"tree":entries})
    new = store.api("POST",repo+"/git/commits",{
        "message":"Save as-of pregame and observed finals, run "+run_id,
        "tree":tree["sha"],"parents":[parent]})
    store.api("PATCH",repo+"/git/refs/heads/"+store.BRANCH,{
        "sha":new["sha"],"force":False})
    # Verify the exact committed Git blob SHAs, not the eventually consistent
    # contents API on a moving branch (which can temporarily return old bytes).
    committed = {entry["path"]: entry["sha"] for entry in entries}
    for path, expected in material.items():
        blob = store.api("GET", repo+"/git/blobs/"+committed[path])
        if not blob or blob.get("encoding") != "base64" or (
                base64.b64decode(blob["content"]) != expected):
            raise ValueError("Persistent GitHub archive blob readback mismatch: " + path)
    return new["sha"]


def run(capture_path, personnel_path, score_csv, manifest_path, output):
    capture = json.loads(Path(capture_path).read_text())
    joined = json.loads(Path(personnel_path).read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    scores_blob = Path(score_csv).read_bytes()
    games = list(csv.DictReader(scores_blob.decode("utf-8-sig").splitlines()))
    now = dt.datetime.now(dt.timezone.utc)
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    branch = store.branch_head()
    if branch is None:
        raise ValueError("Existing context-state branch required")
    old_index = _read_json(INDEX)
    old_outcomes = _read_json(OUTCOMES)
    bundle, index, outcomes, labels, summary = plan(
        capture, joined, old_index, old_outcomes, games, manifest,
        now.isoformat(), run_id, _hash(scores_blob))
    material = {
        summary["pregame_path"]: store.pack(bundle),
        INDEX: store.encode(index),
        OUTCOMES: store.encode(outcomes),
        ROOT+"/summary.json": store.encode(summary)}
    for path, label in labels:
        material[path] = store.pack(label)
    # Branch update and byte-for-byte verification are shared by both workflows.
    summary["archive_commit_sha"] = _commit_material(material, run_id)
    p = Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8") as f:
        f.write(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))
    return summary



def settle_only(score_csv, manifest_path, output):
    """Archive new final labels without needing any upcoming pregame game."""
    manifest = json.loads(Path(manifest_path).read_text())
    blob = Path(score_csv).read_bytes()
    scores = list(csv.DictReader(blob.decode("utf-8-sig").splitlines()))
    now = dt.datetime.now(dt.timezone.utc)
    retrieved = _valid_manifest(manifest, now)
    finals = _finals(scores, retrieved)
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not str(run_id).isdigit() or store.branch_head() is None:
        raise ValueError("Observed run and context-state branch are required")
    index = _read_json(INDEX)
    outcomes = _read_json(OUTCOMES)
    next_outcomes, labels, pending = _link_observed_finals(
        index, outcomes, finals, retrieved, _hash(blob), now)
    summary = {
        "status": STATUS, "run_id": str(run_id),
        "archived_at_utc": now.isoformat(), "settlement_only": True,
        "new_pregame_game_slots": 0, "distinct_games_observed": len(index["games"]),
        "newly_linked_final_games": len(labels),
        "cumulative_linked_final_games": len(next_outcomes["games"]),
        "pending": dict(pending), "external_immutability_verified": False,
        "scoreboard_publication_time_verified": False,
        "historical_publication_times_verified": False,
        "model_promoted": False, "safe_for_betting": False,
        "betting_status": "PASS_UNVALIDATED"}
    if labels:
        material = {OUTCOMES: store.encode(next_outcomes),
                    ROOT+"/summary.json": store.encode(summary)}
        for path, label in labels:
            material[path] = store.pack(label)
        summary["archive_commit_sha"] = _commit_material(material, run_id)
    else:
        summary["write_skipped_no_new_finals"] = True
    p = Path(output)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x",encoding="utf-8") as handle:
        handle.write(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--capture")
    p.add_argument("--personnel")
    p.add_argument("--games",required=True)
    p.add_argument("--manifest",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--settle-only",action="store_true")
    a = p.parse_args()
    if a.settle_only:
        if a.capture or a.personnel:
            p.error("--settle-only must not use a pregame capture")
        settle_only(a.games,a.manifest,a.output)
    else:
        if not a.capture or not a.personnel:
            p.error("Normal archive mode requires --capture and --personnel")
        run(a.capture,a.personnel,a.games,a.manifest,a.output)

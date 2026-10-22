"""Step 3C: join independently observed QB/availability evidence to pregame captures.

This is a provenance-bearing research feature board, NOT a medical model or
betting engine. Only source observations actually captured by the pregame
profile's capture instant are usable; missing is always explicitly unknown.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts.game_context import parse_time
from scripts.pregame_evidence import get_asof_feature, STATUS as PROFILE_STATUS
from scripts.qb_history import lookup as qb_lookup, verify_observation as verify_qb
from scripts.injury_history import lookup as injury_lookup, verify_observation as verify_injury
from scripts.weekly_profiles import canonical

STATUS = "PERSONNEL_PROFILE_JOIN_RESEARCH_ONLY"
BASE_FIELDS = (
    "score_margin_form", "scoring_total_form", "win_rate_form",
    "off_epa_matchup", "def_epa_matchup", "pass_epa_form", "rush_epa_form",
    "success_form", "explosive_pass_form", "explosive_rush_form",
    "pressure_form", "drive_yards_form", "pass_rate_form", "epa_coverage_form")
QB_FIELDS = ("home_qb_reviewed", "away_qb_reviewed")
COVERAGE_FIELDS = ("home_report_verified", "away_report_verified")
STATUS_FIELDS = ("availability_out_diff", "availability_questionable_diff",
                 "availability_limited_diff", "availability_qb_out_diff")
FEATURE_FIELDS = BASE_FIELDS + QB_FIELDS + COVERAGE_FIELDS + STATUS_FIELDS
ALLOWED_AVAILABILITY = ("OUT", "QUESTIONABLE", "LIMITED")


def sha256(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _diff(a, b, name):
    x, y = a.get(name), b.get(name)
    return x - y if x is not None and y is not None else None


def _base_profiles(profiles):
    h = profiles["home"]["recent_form"]
    a = profiles["away"]["recent_form"]
    total = None
    if all(x.get("points_for") is not None and x.get("points_against") is not None for x in (h, a)):
        total = ((h["points_for"] + h["points_against"]) +
                 (a["points_for"] + a["points_against"])) / 2
    paired = (lambda x, first, y, second:
              x[first] - y[second] if x.get(first) is not None and y.get(second) is not None else None)
    return {
        "score_margin_form": _diff(h, a, "margin"),
        "scoring_total_form": total,
        "win_rate_form": _diff(h, a, "win"),
        "off_epa_matchup": paired(h, "epa_off_adj", a, "epa_def_adj"),
        "def_epa_matchup": paired(a, "epa_off_adj", h, "epa_def_adj"),
        "pass_epa_form": _diff(h, a, "epa_pass"),
        "rush_epa_form": _diff(h, a, "epa_rush"),
        "success_form": _diff(h, a, "success"),
        "explosive_pass_form": _diff(h, a, "explosive_pass"),
        "explosive_rush_form": _diff(h, a, "explosive_rush"),
        "pressure_form": _diff(h, a, "pressure"),
        "drive_yards_form": _diff(h, a, "drive_yards"),
        "pass_rate_form": _diff(h, a, "pass_rate"),
        "epa_coverage_form": _diff(h, a, "epa_coverage"),
    }


def _observed_snapshots(snapshots, game, capture, verifier, kind):
    if not isinstance(snapshots, list):
        raise ValueError("Expected historical "+kind+" observations")
    at = parse_time(capture["captured_at_utc"])
    context_asof = parse_time(capture["sources"]["context_asof_utc"])
    seen = set()
    usable = []
    for snapshot in snapshots:
        verifier(snapshot)
        observed = parse_time(snapshot["observed_at_utc"])
        if observed > at:
            continue
        ident = observed.isoformat()
        if ident in seen:
            raise ValueError("Duplicate "+kind+" observation instant")
        seen.add(ident)
        if parse_time(snapshot["context_asof_utc"]) > context_asof:
            raise ValueError("Personnel history from later context than profile")
        if kind == "qb" and parse_time(snapshot["review_queue_asof_utc"]) > at:
            raise ValueError("Future QB review source")
        for row in snapshot["rows"]:
            if str(row["game_id"]) != str(game["game_id"]):
                continue
            if (row["team"] not in (game["home"], game["away"]) or
                row["opponent"] != (game["away"] if row["team"] == game["home"] else game["home"]) or
                parse_time(row["kickoff_utc"]) != parse_time(game["kickoff_utc"])):
                raise ValueError("Historical personnel matchup identity mismatch")
        usable.append(snapshot)
    return usable


def _side(game_id, team, qb_snapshots, injury_snapshots, instant):
    qb = qb_lookup(qb_snapshots, game_id, team, instant)
    injury = injury_lookup(injury_snapshots, game_id, team, instant)
    reviewed = qb["status"] == "CONFIRMED_REVIEWED_PREKICKOFF"
    covered = injury.get("coverage_status") == "VERIFIED_REPORT_REVIEWED"
    # Only source-backed report rows. Never equate an unlisted player to AVAILABLE.
    players = injury.get("reported_players") or []
    counts = {status: sum(r["reported_status"] == status for r in players)
              for status in ALLOWED_AVAILABILITY}
    qb_out = sum(r["position"] == "QB" and r["reported_status"] == "OUT" for r in players)
    if covered and reviewed and any(
        r["player"].casefold() == qb["player"].casefold() and
        r["reported_status"] in ("OUT", "SUSPENDED", "DOUBTFUL", "LIMITED")
        for r in players):
        # Do not turn a cross-feed contradictory claim into a reliable starter.
        reviewed = False
        qb_status = "CONFLICT_REQUIRES_REVIEW"
        qb_player = None
    else:
        qb_status = qb["status"]
        qb_player = qb.get("player") if reviewed else None
    return {
        "qb_status": qb_status,
        "reviewed_qb_player": qb_player,
        "qb_observed_at_utc": qb.get("asof_utc"),
        "availability_coverage": injury.get("coverage_status", "UNKNOWN"),
        "availability_observed_at_utc": injury.get("asof_utc"),
        "unlisted_player_status": "UNKNOWN",
        "reported_status_counts": counts if covered else None,
        "reported_qb_out_count": qb_out if covered else None,
        "qb_reviewed": int(reviewed),
        "report_verified": int(covered),
        "diagnosis_verified": False,
        "participation_verified": False,
    }


def join_capture(capture, qb_snapshots, injury_snapshots):
    if (capture.get("status") != PROFILE_STATUS or
        capture.get("safe_for_betting") is not False or
        capture.get("betting_status") != "PASS_UNVALIDATED" or
        capture.get("historical_publication_times_verified") is not False):
        raise ValueError("Invalid pregame profile capture")
    instant = capture["captured_at_utc"]
    if parse_time(capture["sources"]["context_asof_utc"]) > parse_time(instant):
        raise ValueError("Future context source")
    seen = set()
    output = []
    for game in capture["games"]:
        gid = str(game["game_id"])
        if gid in seen:
            raise ValueError("Duplicate profile capture game")
        seen.add(gid)
        if not game["home"] or not game["away"] or game["home"] == game["away"]:
            raise ValueError("Invalid profile matchup")
        get_asof_feature(capture, gid, instant)  # verifies profile hash and source times
        qb = _observed_snapshots(qb_snapshots, game, capture, verify_qb, "qb")
        injury = _observed_snapshots(injury_snapshots, game, capture, verify_injury, "injury")
        home = _side(gid, game["home"], qb, injury, instant)
        away = _side(gid, game["away"], qb, injury, instant)
        both = home["report_verified"] and away["report_verified"]
        features = {
            **_base_profiles(game["team_profiles"]),
            "home_qb_reviewed": home["qb_reviewed"],
            "away_qb_reviewed": away["qb_reviewed"],
            "home_report_verified": home["report_verified"],
            "away_report_verified": away["report_verified"],
            "availability_out_diff": (home["reported_status_counts"]["OUT"] -
                                      away["reported_status_counts"]["OUT"]) if both else None,
            "availability_questionable_diff": (
                home["reported_status_counts"]["QUESTIONABLE"] -
                away["reported_status_counts"]["QUESTIONABLE"]) if both else None,
            "availability_limited_diff": (
                home["reported_status_counts"]["LIMITED"] -
                away["reported_status_counts"]["LIMITED"]) if both else None,
            "availability_qb_out_diff": (home["reported_qb_out_count"] -
                                         away["reported_qb_out_count"]) if both else None,
        }
        if set(features) != set(FEATURE_FIELDS):
            raise ValueError("Feature schema mismatch")
        record = {"game_id": gid, "home": game["home"], "away": game["away"],
                  "kickoff_utc": game["kickoff_utc"],
                  "captured_at_utc": instant,
                  "profile_sha256": game["team_profiles_sha256"],
                  "team_profiles": game["team_profiles"],
                  "personnel_by_side": {"home": home, "away": away},
                  "features": features,
                  "historical_publication_times_verified": False,
                  "safe_for_betting": False,
                  "betting_status": "PASS_UNVALIDATED"}
        record["record_sha256"] = sha256(record)
        output.append(record)
    if not output:
        raise ValueError("Empty joined capture")
    result = {
        "status": STATUS, "season": 2026, "run_id": capture["run_id"],
        "captured_at_utc": instant, "profile_source_sha256": sha256(capture),
        "qb_observation_count": len(qb_snapshots),
        "injury_observation_count": len(injury_snapshots),
        "games": output,
        "summary": {
            "matchups": len(output),
            "matchups_with_both_availability_reports": sum(
                g["personnel_by_side"]["home"]["report_verified"] and
                g["personnel_by_side"]["away"]["report_verified"] for g in output),
            "reviewed_qb_slots": sum(s["qb_reviewed"] for g in output
                for s in g["personnel_by_side"].values()),
            "matchups_without_complete_availability": sum(
                g["features"]["availability_out_diff"] is None for g in output)},
        "historical_publication_times_verified": False,
        "model_validated": False, "safe_for_betting": False,
        "betting_status": "PASS_UNVALIDATED"}
    verify_joined(result)
    return result


def verify_joined(joined):
    if (joined.get("status") != STATUS or joined.get("season") != 2026 or
        joined.get("historical_publication_times_verified") is not False or
        joined.get("safe_for_betting") is not False or
        joined.get("model_validated") is not False or
        joined.get("betting_status") != "PASS_UNVALIDATED"):
        raise ValueError("Invalid joined feature clearance")
    when = parse_time(joined["captured_at_utc"])
    if not joined.get("games"):
        raise ValueError("Empty joined feature record")
    seen = set()
    for row in joined["games"]:
        if str(row["game_id"]) in seen:
            raise ValueError("Duplicate joined game ID")
        seen.add(str(row["game_id"]))
        if parse_time(row["captured_at_utc"]) != when or parse_time(row["kickoff_utc"]) <= when:
            raise ValueError("Postkickoff joined feature")
        for banned in ("home_score", "away_score", "actual_margin", "settlement", "result"):
            if banned in row or banned in row["features"]:
                raise ValueError("Postgame outcomes in pregame features")
        if row.get("safe_for_betting") is not False or row.get("betting_status") != "PASS_UNVALIDATED":
            raise ValueError("Unsafe joined game")
        if sha256(row["team_profiles"]) != row["profile_sha256"]:
            raise ValueError("Joined profile checksum mismatch")
        if set(row["features"]) != set(FEATURE_FIELDS):
            raise ValueError("Invalid personnel feature schema")
        for name, value in row["features"].items():
            if value is not None and (type(value) not in (int, float) or
                                      not __import__("math").isfinite(value)):
                raise ValueError("Non-numeric research feature")
        for side in ("home", "away"):
            state = row["personnel_by_side"][side]
            if (state.get("unlisted_player_status") != "UNKNOWN" or
                state.get("diagnosis_verified") is not False or
                state.get("participation_verified") is not False):
                raise ValueError("Unsafe personnel inference")
            if (state.get("availability_observed_at_utc") is not None and
                parse_time(state["availability_observed_at_utc"]) > when):
                raise ValueError("Future availability evidence")
            if (state.get("qb_observed_at_utc") is not None and
                parse_time(state["qb_observed_at_utc"]) > when):
                raise ValueError("Future QB evidence")
            if state.get("report_verified") not in (0, 1) or state.get("qb_reviewed") not in (0, 1):
                raise ValueError("Invalid knownness encoding")
            if state["report_verified"] == 0 and (
                state["reported_status_counts"] is not None or
                state["reported_qb_out_count"] is not None):
                raise ValueError("Unverified report converted to count features")
            if state["qb_reviewed"] == 0 and state.get("reviewed_qb_player") is not None:
                raise ValueError("Unsupported QB identity")
            if row["features"][side+"_report_verified"] != state["report_verified"] or (
                row["features"][side+"_qb_reviewed"] != state["qb_reviewed"]):
                raise ValueError("Knownness metadata mismatch")
        if (not all(row["personnel_by_side"][s]["report_verified"] for s in ("home","away"))
            and any(row["features"][f] is not None for f in STATUS_FIELDS)):
            raise ValueError("Uncovered status used as differential")
        proof = dict(row)
        token = proof.pop("record_sha256", None)
        if not isinstance(token, str) or sha256(proof) != token:
            raise ValueError("Joined record checksum mismatch")
    return True


def run(capture_path, qb_path, injury_path, output_path):
    capture = json.loads(Path(capture_path).read_text())
    qb = json.loads(Path(qb_path).read_text())
    injury = json.loads(Path(injury_path).read_text())
    joined = join_capture(capture, [qb], [injury])
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(joined, indent=2, allow_nan=False)+"\n")
    print(json.dumps(joined["summary"]))
    return joined


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", required=True)
    parser.add_argument("--qb-history", required=True)
    parser.add_argument("--injury-history", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.capture, args.qb_history, args.injury_history, args.output)

"""Audited, full-roster pregame availability coverage; no guessed player values.

Consumes the existing timestamped replacement-count capture for every upcoming
game. A published roster report is not a complete healthy roster, and counts
are never directly converted into a score adjustment.
"""
import argparse
import json
from pathlib import Path

from scripts.game_context import parse_time
from scripts.player_replacement import POSITIONS

STATUS = "ROSTER_AVAILABILITY_READINESS_RESEARCH_ONLY"
INPUT_STATUS = "OBSERVED_REPLACEMENT_COUNT_FEATURES_RESEARCH_ONLY"
COVERED = "VERIFIED_REPORT_REVIEWED"


def _check_side(side):
    if not isinstance(side, dict):
        raise ValueError("Missing team availability source")
    covered = side.get("coverage") == COVERED
    if not covered:
        if side.get("coverage") != "UNKNOWN" or side.get("absences") is not None or side.get("uncertain") is not None:
            raise ValueError("Unknown coverage cannot imply zero absences")
        return False
    for name in ("absences", "uncertain"):
        values = side.get(name)
        if not isinstance(values, dict) or set(values) != set(POSITIONS):
            raise ValueError("Incomplete positional status map")
        if any(type(n) is not int or n < 0 for n in values.values()):
            raise ValueError("Invalid reported positional count")
    return True


def evaluate(bundle, decision_utc):
    if (bundle.get("status") != INPUT_STATUS or bundle.get("season") != 2026
            or bundle.get("safe_for_betting") is not False
            or bundle.get("betting_status") != "PASS_UNVALIDATED"
            or bundle.get("trained_replacement_points") is not False):
        raise ValueError("Unsupported replacement capture")
    now = parse_time(decision_utc)
    capture = parse_time(bundle["captured_at_utc"])
    if capture > now:
        raise ValueError("Future capture is not a predecision observation")
    seen = set()
    result = []
    for game in bundle.get("games", []):
        gid = str(game["game_id"])
        if gid in seen or not game["home"] or not game["away"] or game["home"] == game["away"]:
            raise ValueError("Duplicate or invalid game identity")
        seen.add(gid)
        kickoff = parse_time(game["kickoff_utc"])
        issued = parse_time(game["decision_asof_utc"])
        if not capture == issued <= now < kickoff:
            raise ValueError("Postkickoff or future personnel observation")
        sides = {}
        for key in ("home", "away"):
            original = game[key+"_report_by_position"]
            known = _check_side(original)
            sides[key] = {
                "team": game[key], "coverage": original["coverage"],
                "unlisted_players": "UNKNOWN",
                "reported_out_or_suspended": original["absences"] if known else None,
                "reported_uncertain": original["uncertain"] if known else None,
                "injury_source_is_participation_proof": False,
                "verified_individual_replacement_value": False,
            }
        both = all(sides[k]["coverage"] == COVERED for k in ("home", "away"))
        if both != (game.get("coverage") == "BOTH_REPORTS"):
            raise ValueError("Two-sided report coverage disagreement")
        if game.get("injury_adjustment_applied_to_live_model") is not False:
            raise ValueError("Do not treat these counts as validated injury points")
        result.append({
            "game_id": gid, "home": game["home"], "away": game["away"],
            "kickoff_utc": game["kickoff_utc"], "personnel_asof_utc": game["decision_asof_utc"],
            "teams": sides, "both_reports_verified": both,
            "learned_player_impact_ready": False,
            "reason": "PLAYER_IDENTITY_AND_REPLACEMENT_EFFECT_NOT_VERIFIED" if both
                      else "UNVERIFIED_REPORT_COVERAGE",
            "candidate_home_margin_adjustment": None,
        })
    if not result:
        raise ValueError("No forthcoming game/team slots")
    known_sides = [s for game in result for s in game["teams"].values() if s["coverage"] == COVERED]
    totals = {
        position: {
            "reported_absent": sum(s["reported_out_or_suspended"][position] for s in known_sides),
            "reported_uncertain": sum(s["reported_uncertain"][position] for s in known_sides),
        } for position in POSITIONS
    }
    return {
        "status": STATUS, "season": 2026, "run_id": str(bundle["run_id"]),
        "audited_at_utc": now.isoformat(), "source_capture_utc": capture.isoformat(),
        "summary": {
            "games": len(result), "game_team_slots": 2*len(result),
            "sides_with_verified_reports": len(known_sides),
            "games_with_two_verified_reports": sum(g["both_reports_verified"] for g in result),
            "games_without_complete_injury_coverage": sum(not g["both_reports_verified"] for g in result),
            "position_report_counts": totals,
            "valid_learned_player_impacts": 0,
            "live_injury_score_adjustments": 0,
        }, "games": result, "model_promoted": False, "safe_for_betting": False,
        "betting_status": "PASS_UNVALIDATED",
    }


def run(source, output, asof=None):
    bundle = json.loads(Path(source).read_text(encoding="utf-8"))
    result = evaluate(bundle, asof or bundle["captured_at_utc"])
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result["summary"].items() if k != "position_report_counts"}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--asof")
    args = parser.parse_args()
    run(args.input, args.output, args.asof)

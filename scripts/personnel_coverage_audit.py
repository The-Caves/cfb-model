"""Step 3H: audit actual verified two-team QB and availability coverage."""
import argparse
import json
from pathlib import Path
from scripts.game_context import parse_time

STATUS = "STEP3H_PERSONNEL_COVERAGE_RESEARCH_ONLY"
VERIFIED = "VERIFIED_REPORT_REVIEWED"

def audit(context):
    if context.get("betting_status") != "PASS_UNVALIDATED":
        raise ValueError("Untrusted context")
    issue = parse_time(context["asof_utc"])
    capture = parse_time(context["captured_at_utc"])
    if issue > capture:
        raise ValueError("Context chronology invalid")
    games = context.get("games")
    if not isinstance(games, list):
        raise ValueError("Missing game records")
    rows = []
    seen = set()
    for game in games:
        gid = str(game["game_id"])
        if gid in seen:
            raise ValueError("Duplicate game ID")
        seen.add(gid)
        if parse_time(game["kickoff_utc"]) <= issue:
            continue
        teams = [game["home"], game["away"]]
        if teams[0] == teams[1]:
            raise ValueError("Invalid matchup")
        reports = game.get("injury_coverage_by_team") or {}
        qbs = game.get("verified_qb_starters") or {}
        if not isinstance(reports, dict) or not isinstance(qbs, dict):
            raise ValueError("Malformed personnel evidence")
        slots = []
        for team in teams:
            status = reports.get(team, "UNKNOWN")
            if status not in ("UNKNOWN", VERIFIED):
                raise ValueError("Unsupported availability designation")
            qb = qbs.get(team)
            if qb is not None:
                if not isinstance(qb, dict) or not qb.get("player"):
                    raise ValueError("Malformed QB review")
                times = [parse_time(qb[key]) for key in
                         ("published_at_utc", "captured_at_utc", "reviewed_at_utc")]
                if not times[0] <= times[1] <= times[2] <= issue:
                    raise ValueError("QB source after cutoff")
            slots.append({"team": team, "report_status": status,
                          "qb_status": "REVIEWED_STARTER" if qb else "UNKNOWN",
                          "qb_player": qb["player"] if qb else None,
                          "report_missing": status != VERIFIED,
                          "qb_missing": qb is None})
        rows.append({"game_id": gid, "home": teams[0], "away": teams[1],
                     "kickoff_utc": game["kickoff_utc"], "teams": slots,
                     "complete_reports": all(not s["report_missing"] for s in slots),
                     "complete_qb_review": all(not s["qb_missing"] for s in slots)})
    slots = [s for row in rows for s in row["teams"]]
    n = len(slots)
    verified = sum(s["report_status"] == VERIFIED for s in slots)
    reviewed = sum(s["qb_status"] == "REVIEWED_STARTER" for s in slots)
    return {"status": STATUS, "season": 2026,
            "asof_utc": context["asof_utc"], "captured_at_utc": context["captured_at_utc"],
            "summary": {"games": len(rows), "team_slots": n,
                        "verified_report_slots": verified,
                        "reviewed_qb_slots": reviewed,
                        "report_coverage_fraction": round(verified/n, 5) if n else None,
                        "qb_coverage_fraction": round(reviewed/n, 5) if n else None,
                        "both_reports_games": sum(r["complete_reports"] for r in rows),
                        "both_qbs_games": sum(r["complete_qb_review"] for r in rows)},
            "games": rows, "missing_information_means": "UNKNOWN_NOT_HEALTHY",
            "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"}

def run(source, output):
    result = audit(json.loads(Path(source).read_text()))
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps(result["summary"]))
    return result

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--context", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    run(a.context, a.output)

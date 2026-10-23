"""Fail-closed pregame injury-source readiness audit (research only).

This is a coverage/triage report, not a diagnosis or player-value model.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from scripts.game_context import parse_time

VERIFIED = "VERIFIED_REPORT_REVIEWED"
STATUS = "INJURY_SOURCE_READINESS_RESEARCH_ONLY"

def audit(context, now=None):
    if context.get("safe_for_betting") is True or context.get("betting_status", "PASS_UNVALIDATED") != "PASS_UNVALIDATED":
        raise ValueError("Untrusted context")
    asof = parse_time(context["asof_utc"])
    captured = parse_time(context["captured_at_utc"])
    decision = parse_time(now) if now else asof
    if asof > captured or decision < asof or decision > captured:
        raise ValueError("Decision outside observed context window")
    games = context.get("games")
    if not isinstance(games, list):
        raise ValueError("Missing game list")
    rows = []
    seen = set()
    for game in games:
        gid = str(game["game_id"])
        if gid in seen:
            raise ValueError("Duplicate game")
        seen.add(gid)
        kickoff = parse_time(game["kickoff_utc"])
        if kickoff <= decision:
            continue
        home, away = game["home"], game["away"]
        if not home or not away or home == away:
            raise ValueError("Invalid matchup")
        coverage = game.get("injury_coverage_by_team") or {}
        if not isinstance(coverage, dict):
            raise ValueError("Invalid report coverage")
        hours = (kickoff - decision).total_seconds() / 3600
        window = "FINAL_6H" if hours <= 6 else "GAME_DAY_24H" if hours <= 24 else "EARLY"
        for team, opponent in ((home, away), (away, home)):
            state = coverage.get(team, "UNKNOWN")
            if state not in ("UNKNOWN", VERIFIED):
                raise ValueError("Invalid coverage designation")
            rows.append({"game_id": gid, "team": team, "opponent": opponent,
                         "kickoff_utc": game["kickoff_utc"], "hours_to_kickoff": round(hours, 2),
                         "window": window, "report_status": state,
                         "needs_verified_report": state != VERIFIED,
                         "priority": ("URGENT" if hours <= 6 else "GAME_DAY" if hours <= 24 else "SCHEDULED")
                         if state != VERIFIED else "COVERED"})
    missing = [r for r in rows if r["needs_verified_report"]]
    summary = {"upcoming_games": len(rows)//2, "team_slots": len(rows),
               "verified_report_slots": len(rows)-len(missing),
               "missing_report_slots": len(missing),
               "verified_fraction": round((len(rows)-len(missing))/len(rows), 5) if rows else None,
               "urgent_missing_slots": sum(r["priority"] == "URGENT" for r in missing),
               "game_day_missing_slots": sum(r["priority"] == "GAME_DAY" for r in missing)}
    return {"status": STATUS, "asof_utc": decision.isoformat(), "summary": summary,
            "rows": sorted(rows, key=lambda r: (r["kickoff_utc"], r["team"])),
            "unknown_means": "NOT_VERIFIED_NOT_HEALTHY", "replacement_values_validated": False,
            "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"}

def run(context_path, output_path):
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    result = audit(context)
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.context, args.output)

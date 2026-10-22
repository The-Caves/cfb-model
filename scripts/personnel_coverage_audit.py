"""Step 3H: audit actual verified two-team QB and availability coverage."""
import argparse
import json
from pathlib import Path
from scripts.game_context import parse_time

STATUS = "STEP3H_PERSONNEL_COVERAGE_RESEARCH_ONLY"
VERIFIED = "VERIFIED_REPORT_REVIEWED"

def audit(context, review_queue=None):
    if context.get("betting_status", "PASS_UNVALIDATED") != "PASS_UNVALIDATED" or context.get("safe_for_betting") is True:
        raise ValueError("Untrusted context")
    issue = parse_time(context["asof_utc"])
    capture = parse_time(context["captured_at_utc"])
    if issue > capture:
        raise ValueError("Context chronology invalid")
    games = context.get("games")
    if not isinstance(games, list):
        raise ValueError("Missing game records")
    queue_by_key = {}
    if review_queue is not None:
        if (review_queue.get("status") != "QB_REVIEW_RESEARCH_ONLY"
                or review_queue.get("betting_status") != "PASS_UNVALIDATED"
                or review_queue.get("safe_for_betting") is True):
            raise ValueError("Untrusted QB review queue")
        if parse_time(review_queue["asof_utc"]) < issue:
            raise ValueError("QB review queue predates context cutoff")
        for entry in review_queue.get("rows", []):
            key = (str(entry["game_id"]), entry["team"])
            if key in queue_by_key:
                raise ValueError("Duplicate QB review queue entry")
            queue_by_key[key] = entry
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
            queued = queue_by_key.get((gid, team))
            if queued is not None and queued.get("opponent") != (teams[1] if team == teams[0] else teams[0]):
                raise ValueError("QB review queue opponent mismatch")
            candidates = queued.get("candidate_count", 0) if queued else 0
            if not isinstance(candidates, int) or candidates < 0:
                raise ValueError("Invalid candidate count")
            slots.append({"team": team, "report_status": status,
                          "qb_review_priority": queued.get("review_priority") if queued else "UNKNOWN_NEEDS_SOURCE",
                          "official_news_candidates": candidates,
                          "official_feed_status": queued.get("feed_status") if queued else "UNKNOWN",
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
            "review_queue_summary": {
                "unverified_qb_with_official_news_candidates": sum(
                    s["qb_missing"] and s["official_news_candidates"] > 0 for s in slots),
                "qb_slots_with_no_official_feed": sum(
                    s["qb_missing"] and s["official_feed_status"] == "NOT_CONFIGURED" for s in slots),
                "qb_slots_with_failed_official_feed": sum(
                    s["qb_missing"] and s["official_feed_status"] == "FETCH_FAILED" for s in slots),
                "missing_report_team_slots": sum(s["report_missing"] for s in slots),
                "missing_qb_team_slots": sum(s["qb_missing"] for s in slots)},
            "games": rows, "missing_information_means": "UNKNOWN_NOT_HEALTHY",
            "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"}

def run(source, output, queue_path=None):
    result = audit(json.loads(Path(source).read_text()), json.loads(Path(queue_path).read_text()) if queue_path else None)
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
    p.add_argument("--review-queue")
    a = p.parse_args()
    run(a.context, a.output, a.review_queue)

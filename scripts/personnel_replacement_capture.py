"""Join independently observed injury slots to pregame replacement count features."""
import argparse
import json
from pathlib import Path
from scripts.game_context import parse_time
from scripts.injury_history import observe, lookup
from scripts.personnel_features import verify_joined
from scripts.player_replacement import observed_absences, build_game

STATUS = "OBSERVED_REPLACEMENT_COUNT_FEATURES_RESEARCH_ONLY"

def build(joined, context):
    verify_joined(joined)
    decision = parse_time(joined["captured_at_utc"])
    if (parse_time(context["asof_utc"]) > parse_time(context["captured_at_utc"])
        or parse_time(context["captured_at_utc"]) > decision):
        raise ValueError("Future injury context")
    if context.get("betting_status", "PASS_UNVALIDATED") != "PASS_UNVALIDATED":
        raise ValueError("Untrusted injury context")
    snapshot = observe(context, context["captured_at_utc"])
    records = []
    for game in joined["games"]:
        gid = str(game["game_id"])
        home = lookup([snapshot], gid, game["home"], joined["captured_at_utc"])
        away = lookup([snapshot], gid, game["away"], joined["captured_at_utc"])
        if (home.get("status") == "UNKNOWN" or away.get("status") == "UNKNOWN"):
            raise ValueError("Missing matchup in observed injury history")
        h = observed_absences(home, joined["captured_at_utc"])
        a = observed_absences(away, joined["captured_at_utc"])
        record = build_game(h, a)
        # A single verified report is useful team evidence even when the
        # opponent's report is absent. Keep its actual position counts;
        # never manufacture a two-team differential from an UNKNOWN side.
        records.append({"game_id": gid, "home": game["home"], "away": game["away"],
                        "kickoff_utc": game["kickoff_utc"],
                        "decision_asof_utc": joined["captured_at_utc"],
                        "home_report_by_position": h,
                        "away_report_by_position": a,
                        "injury_adjustment_applied_to_live_model": False,
                        **record})
    verified_sides = [r[key] for r in records
                      for key in ("home_report_by_position", "away_report_by_position")
                      if r[key]["coverage"] == "VERIFIED_REPORT_REVIEWED"]
    partial_games = sum(
        (r["home_report_by_position"]["coverage"] == "VERIFIED_REPORT_REVIEWED") !=
        (r["away_report_by_position"]["coverage"] == "VERIFIED_REPORT_REVIEWED")
        for r in records)
    return {"status": STATUS, "season": 2026, "run_id": joined["run_id"],
            "captured_at_utc": joined["captured_at_utc"],
            "games": records,
            "summary": {"games": len(records),
                        "both_reports": sum(r["coverage"] == "BOTH_REPORTS" for r in records),
                        "verified_team_slots": len(verified_sides),
                        "partially_covered_games": partial_games,
                        "observed_absences": sum(sum(s["absences"].values()) for s in verified_sides),
                        "observed_uncertain": sum(sum(s["uncertain"].values()) for s in verified_sides),
                        "observed_first_half_out": sum(sum(s["partial_absences"].values())
                                                       for s in verified_sides),
                        "live_injury_adjustments_applied": 0},
            "trained_replacement_points": False, "safe_for_betting": False,
            "betting_status": "PASS_UNVALIDATED"}

def run(joined_path, context_path, output_path):
    joined = json.loads(Path(joined_path).read_text())
    context = json.loads(Path(context_path).read_text())
    result = build(joined, context)
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result["summary"]))
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--joined", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.joined, args.context, args.output)

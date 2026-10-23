"""Research-only same-day archive reconciliation; does not alter the 24–72h policy."""
import argparse
import datetime as dt
import json
from pathlib import Path
from scripts.game_context import parse_time

STATUS = "SAME_DAY_PREGAME_RECONCILIATION_RESEARCH_ONLY"

def reconcile(index, outcomes, day):
    dt.date.fromisoformat(day)
    if index.get("season") != 2026 or outcomes.get("season") != 2026:
        raise ValueError("Unexpected archive season")
    games = []
    for gid, captures in index.get("games", {}).items():
        if not isinstance(captures, list) or not captures:
            raise ValueError("Invalid observation history")
        original = captures[0]
        kickoff = parse_time(original["kickoff_utc"])
        if kickoff.astimezone(dt.timezone(dt.timedelta(hours=-4))).date().isoformat() != day:
            continue
        if any(r["home"] != original["home"] or r["away"] != original["away"] or
               parse_time(r["kickoff_utc"]) != kickoff for r in captures):
            raise ValueError("Conflicting matchup observations")
        before = [r for r in captures if parse_time(r["captured_at_utc"]) < kickoff]
        if not before:
            classification = "NO_PREGAME_CAPTURE"
            selected = None
        else:
            selected = max(before, key=lambda r: parse_time(r["captured_at_utc"]))
            hours = (kickoff - parse_time(selected["captured_at_utc"])).total_seconds()/3600
            classification = "POLICY_24_TO_72H" if 24 <= hours <= 72 else "SAME_DAY_EXPLORATORY_ONLY" if 0 < hours < 24 else "OTHER_PREGAME_WINDOW"
        games.append({"game_id": gid, "home": original["home"], "away": original["away"],
                      "kickoff_utc": original["kickoff_utc"],
                      "pregame_observations": len(before),
                      "selected_capture_utc": selected["captured_at_utc"] if selected else None,
                      "classification": classification,
                      "final_linked": gid in outcomes.get("games", {}),
                      "qualified_for_official_backtest": classification == "POLICY_24_TO_72H" and gid in outcomes.get("games", {})})
    return {"status": STATUS, "day_eastern": day, "games": sorted(games,key=lambda r:r["kickoff_utc"]),
            "summary": {"games": len(games),
                        "same_day_exploratory": sum(r["classification"] == "SAME_DAY_EXPLORATORY_ONLY" for r in games),
                        "linked_finals": sum(r["final_linked"] for r in games),
                        "official_backtest_eligible": sum(r["qualified_for_official_backtest"] for r in games)},
            "policy_changed": False, "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pregame-index", required=True)
    p.add_argument("--outcome-index", required=True)
    p.add_argument("--day-eastern", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = reconcile(json.loads(Path(a.pregame_index).read_text()),
                       json.loads(Path(a.outcome_index).read_text()), a.day_eastern)
    target = Path(a.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x") as out:
        json.dump(result,out,indent=2)
        out.write("\n")
    print(json.dumps(result["summary"]))

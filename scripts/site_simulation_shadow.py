"""Research-only, optional drive simulation shadow for source-verified CFB history.

No synthetic historical drives and no model promotion. The simulation runs
automatically only if a complete, independently reviewed drive event bundle
has been provided. Otherwise the static site declares verified-source missing.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts.game_context import parse_time
from scripts.observed_drive_fit import fit, SOURCE_STATUS
from scripts.game_simulation_research import simulate

STATUS = "SOURCE_GATED_DRIVE_SIMULATION_SHADOW"
PENDING = "AWAITING_VERIFIED_DRIVE_BUNDLE"
AVAILABLE = "INDEPENDENT_DRIVE_SIMULATION_RESEARCH_SHADOW"


def attach(board, bundle, decision_utc, trials=1000):
    now = parse_time(decision_utc)
    if board.get("schema_version") != 2 or board.get("betting_status") != "PASS_UNVALIDATED":
        raise ValueError("Untrusted simulation publication dashboard")
    if type(trials) is not int or not 100 <= trials <= 10000:
        raise ValueError("Invalid research simulator trial count")
    old_forecasts = json.dumps([{k: v for k, v in g.items()
        if k.startswith("model_") or k in ("v04_direct_scores", "home_bias_quarantined")}
        for g in board["games"]], sort_keys=True)
    old_grades = json.dumps(board.get("prospective_records"), sort_keys=True)
    for g in board["games"]:
        g["simulation_shadow"] = None
    if bundle is None:
        board["simulation_display"] = {
            "status": STATUS, "readiness": PENDING, "games_with_fit": 0,
            "replaces_v04": False, "calibrated": False,
            "source": "No complete source-reviewed historical drives supplied",
            "safe_for_betting": False,
        }
        return board
    if (bundle.get("status") != SOURCE_STATUS or bundle.get("season") != 2026 or
            bundle.get("betting_status") != "PASS_UNVALIDATED" or
            bundle.get("safe_for_betting") is not False or
            not isinstance(bundle.get("games"), list)):
        raise ValueError("Research simulation requires reviewed 2026 official drive records")
    used = 0
    incomplete = 0
    for game in board["games"]:
        if parse_time(game["kickoff_utc"]) <= now:
            continue
        identity = {"game_id": str(game["game_id"]), "home": game["home_team"],
                    "away": game["away_team"], "kickoff_utc": game["kickoff_utc"]}
        report = fit(bundle, identity, now.isoformat())
        if not report["ready"]:
            incomplete += 1
            continue
        seed = int(hashlib.sha256(str(game["game_id"]).encode()).hexdigest()[:8], 16)
        # No market quote is passed: its observation time may be newer than
        # the frozen model forecast. This shadow does NOT price ATS bets.
        outcome = simulate(report["simulator_input"], now.isoformat(),
                           market=None, trials=trials, seed=seed)
        game["simulation_shadow"] = {
            "status": AVAILABLE, "trials": trials,
            "home_points_mean": outcome["home_points_mean"],
            "away_points_mean": outcome["away_points_mean"],
            "home_win_regulation_probability": outcome["home_win_regulation_probability"],
            "away_win_regulation_probability": outcome["away_win_regulation_probability"],
            "regulation_tie_probability": outcome["regulation_tie_probability"],
            "margin_p05_p50_p95": outcome["margin_p05_p50_p95"],
            "total_p05_p50_p95": outcome["total_p05_p50_p95"],
            "total_mean": outcome["total_mean"],
            "source_provenance": report["simulator_input"]["source_provenance"],
            "source_captured_at_utc": report["simulator_input"]["source_captured_at_utc"],
            "decision_utc": now.isoformat(), "validated_win_probabilities": False,
            "model_promoted": False, "safe_for_betting": False,
        }
        used += 1
    board["simulation_display"] = {
        "status": STATUS, "readiness": AVAILABLE if used else "VERIFIED_SOURCE_COVERAGE_INSUFFICIENT",
        "reviewed_source_games": len(bundle["games"]), "games_with_fit": used,
        "games_incomplete": incomplete, "trials_per_fit": trials,
        "replaces_v04": False, "calibrated": False,
        "source": SOURCE_STATUS, "safe_for_betting": False,
    }
    current = json.dumps([{k: v for k, v in g.items()
        if k.startswith("model_") or k in ("v04_direct_scores", "home_bias_quarantined")}
        for g in board["games"]], sort_keys=True)
    if current != old_forecasts or json.dumps(board.get("prospective_records"), sort_keys=True) != old_grades:
        raise ValueError("Simulation shadow modified frozen scores or historical grades")
    return board


def run(dashboard_path, bundle_path, trials=1000, now=None):
    path = Path(dashboard_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    source = Path(bundle_path)
    bundle = json.loads(source.read_text(encoding="utf-8")) if source.is_file() else None
    result = attach(data, bundle, now or dt.datetime.now(dt.timezone.utc).isoformat(), trials)
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["simulation_display"], sort_keys=True))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dashboard", required=True)
    p.add_argument("--drive-bundle", required=True)
    p.add_argument("--trials", type=int, default=1000)
    args = p.parse_args()
    run(args.dashboard, args.drive_bundle, args.trials)

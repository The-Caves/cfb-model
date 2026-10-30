"""As-of player absence features and *training-only* replacement-value estimation.

A report is not a diagnosis, snap-count confirmation, or measured player value.
Player IDs and depth/participation histories must be independently sourced.
"""
import argparse
import json
import math
from pathlib import Path
from scripts.game_context import parse_time

STATUS = "PLAYER_REPLACEMENT_RESEARCH_ONLY"
ABSENT = {"OUT", "SUSPENDED"}
UNCERTAIN = {"DOUBTFUL", "QUESTIONABLE", "GAME_TIME_DECISION", "LIMITED"}
PARTIAL_GAME = {"OUT_FIRST_HALF"}  # Confirmed first-half unavailability, NOT full-game absence.
POSITIONS = ("QB", "RB", "WR", "TE", "OL", "DL", "EDGE", "LB", "CB", "DB", "S", "K", "P", "OTHER")

def observed_absences(injury_snapshot, decision_utc):
    """Only reported designations; never infer unlisted players are available."""
    decision = parse_time(decision_utc)
    if parse_time(injury_snapshot["asof_utc"]) > decision:
        raise ValueError("Future injury snapshot")
    if injury_snapshot.get("coverage_status") != "VERIFIED_REPORT_REVIEWED":
        return {"coverage": "UNKNOWN", "absences": None, "uncertain": None, "partial_absences": None}
    rows = injury_snapshot.get("reported_players")
    if not isinstance(rows, list):
        raise ValueError("Verified report lacks player records")
    seen = set()
    absent = {p: 0 for p in POSITIONS}
    uncertain = {p: 0 for p in POSITIONS}
    partial = {p: 0 for p in POSITIONS}
    for row in rows:
        player = row.get("player")
        pos = row.get("position")
        state = row.get("reported_status")
        if not isinstance(player, str) or not player.strip() or pos not in POSITIONS:
            raise ValueError("Ambiguous player identity or position")
        identity = player.casefold().strip()
        if identity in seen:
            raise ValueError("Duplicate player status in report")
        seen.add(identity)
        if state in ABSENT:
            absent[pos] += 1
        elif state in UNCERTAIN:
            uncertain[pos] += 1
        elif state in PARTIAL_GAME:
            partial[pos] += 1
        elif state not in ("AVAILABLE", "PROBABLE", "UNKNOWN"):
            raise ValueError("Unrecognized availability designation")
    return {"coverage": "VERIFIED_REPORT_REVIEWED", "absences": absent,
            "uncertain": uncertain, "partial_absences": partial,
            "player_identity_globally_verified": False}

def build_game(home, away):
    if home["coverage"] != "VERIFIED_REPORT_REVIEWED" or away["coverage"] != "VERIFIED_REPORT_REVIEWED":
        return {"coverage": "INCOMPLETE", "absence_differentials": None,
                "uncertain_differentials": None, "partial_game_differentials": None,
                "replacement_points": None}
    return {"coverage": "BOTH_REPORTS",
            "absence_differentials": {p: home["absences"][p]-away["absences"][p] for p in POSITIONS},
            "uncertain_differentials": {p: home["uncertain"][p]-away["uncertain"][p] for p in POSITIONS},
            "partial_game_differentials": {p: home["partial_absences"][p]-away["partial_absences"][p]
                                           for p in POSITIONS},
            "replacement_points": None}

def train_coefficients(train, test_decision_utc, minimum=30, ridge=25.0):
    """Learn conditional position-count effects from prior observed results only.

    Target is home margin residual relative to a separately frozen baseline.
    No test outcomes or later-captured reports are accepted.
    """
    if type(minimum) is not int or minimum < 2 or ridge <= 0:
        raise ValueError("Invalid training policy")
    decision = parse_time(test_decision_utc)
    if len(train) < minimum:
        return {"status": "INSUFFICIENT_TRAINING", "coefficients": None,
                "training_games": len(train)}
    import numpy as np
    x = []
    y = []
    seen = set()
    for row in train:
        gid = str(row["game_id"])
        if gid in seen:
            raise ValueError("Duplicate training game")
        seen.add(gid)
        kickoff = parse_time(row["kickoff_utc"])
        capture = parse_time(row["captured_at_utc"])
        outcome = parse_time(row["outcome_known_at_utc"])
        if not capture < kickoff < outcome < decision:
            raise ValueError("Future or invalid training evidence")
        if row.get("coverage") != "BOTH_REPORTS":
            continue
        diff = row.get("absence_differentials")
        if not isinstance(diff, dict) or set(diff) != set(POSITIONS):
            raise ValueError("Invalid position differential schema")
        vector = [diff[p] for p in POSITIONS]
        if any(type(v) is not int for v in vector):
            raise ValueError("Invalid absence count")
        residual = row["actual_home_margin"] - row["frozen_baseline_home_margin"]
        if type(residual) not in (int, float) or not math.isfinite(residual):
            raise ValueError("Invalid residual")
        x.append(vector)
        y.append(float(residual))
    if len(x) < minimum:
        return {"status": "INSUFFICIENT_COVERED_TRAINING", "coefficients": None,
                "training_games": len(x)}
    design = np.asarray(x, dtype=float)
    if not np.any(np.std(design, axis=0) > 0):
        return {"status": "NO_TRAINING_VARIATION", "coefficients": None,
                "training_games": len(x)}
    # No intercept: residual is relative to an independently frozen baseline.
    matrix = design.T @ design + np.eye(len(POSITIONS)) * ridge
    beta = np.linalg.solve(matrix, design.T @ np.asarray(y, dtype=float))
    return {"status": "FITTED_RESEARCH_ONLY",
            "coefficients": {p: float(beta[i]) for i, p in enumerate(POSITIONS)},
            "training_games": len(x), "heldout_performance_verified": False,
            "individual_player_value_verified": False}

def estimate(game, fitted):
    if game.get("coverage") != "BOTH_REPORTS" or fitted.get("status") != "FITTED_RESEARCH_ONLY":
        return None
    return sum(game["absence_differentials"][p] * fitted["coefficients"][p] for p in POSITIONS)

def run(input_path, output_path):
    source = json.loads(Path(input_path).read_text(encoding="utf-8"))
    result = {"status": STATUS, "records": [build_game(
        observed_absences(r["home"], r["decision_asof_utc"]),
        observed_absences(r["away"], r["decision_asof_utc"]))
        for r in source["games"]],
        "trained_replacement_points": False, "safe_for_betting": False,
        "betting_status": "PASS_UNVALIDATED"}
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps({"status": STATUS, "games": len(result["records"])}))
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.input, args.output)

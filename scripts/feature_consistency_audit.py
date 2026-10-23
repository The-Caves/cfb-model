"""Exploratory, chronological feature-ablation comparison for the 2026 CFB model.

Historical play-by-play publication timestamps are not authenticated. This is
research-only, never a verified pregame evaluation or a promotion decision.
"""
import argparse
import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scripts.model_v03 import SCORE, ADV, fit_ridge, predict, timestamp

ALL = SCORE + ADV
VARIANTS = {
    "score_only": SCORE,
    "full_v03": ALL,
    "without_off_epa": [x for x in ALL if x != "off_epa_matchup"],
    "without_opponent_epa": [x for x in ALL if x not in ("off_epa_matchup", "def_epa_matchup")],
    "without_pressure": [x for x in ALL if x != "pressure_form"],
    "without_drive_yards": [x for x in ALL if x != "drive_yards_form"],
    "without_explosives": [x for x in ALL if x not in ("explosive_pass_form", "explosive_rush_form")],
    "score_plus_epa": SCORE + ["off_epa_matchup", "def_epa_matchup"],
    "score_plus_pass_rush": SCORE + ["pass_epa_form", "rush_epa_form"],
}


def load_rows(features_path, labels_path):
    with open(features_path, newline="", encoding="utf-8-sig") as f:
        features = list(csv.DictReader(f))
    with open(labels_path, newline="", encoding="utf-8-sig") as f:
        labels = list(csv.DictReader(f))
    lookup = {r["game_id"]: r for r in labels}
    if not features or len(features) != len(labels) or len(lookup) != len(labels):
        raise ValueError("Incomplete or duplicated 2026 feature/outcome data")
    seen, rows = set(), []
    for src in features:
        gid = src["game_id"]
        if gid in seen or gid not in lookup:
            raise ValueError("Missing or duplicated feature game ID")
        seen.add(gid)
        outcome = lookup[gid]
        if (src["date"], src["kickoff_utc"]) != (outcome["date"], outcome["kickoff_utc"]):
            raise ValueError("Mismatched feature/outcome chronology")
        if not src["date"].startswith("2026-") or timestamp(src["kickoff_utc"]).year != 2026:
            raise ValueError("Out-of-season game")
        if src["betting_status"] != "PASS_UNVALIDATED" or src["feature_evidence_status"] != "RETROSPECTIVE_NOT_PUBLICATION_VERIFIED":
            raise ValueError("Invalid retrospective evidence status")
        g = dict(src)
        for field in ALL:
            raw = g[field]
            g[field] = float(raw) if raw.strip() else None
            if g[field] is not None and not math.isfinite(g[field]):
                raise ValueError("Nonfinite input feature")
        for field in ("home_games_prior", "away_games_prior"):
            g[field] = int(g[field])
        for field in ("home_score", "away_score"):
            g[field] = int(outcome[field])
            if g[field] < 0:
                raise ValueError("Negative score")
        rows.append(g)
    return sorted(rows, key=lambda r: (timestamp(r["kickoff_utc"]), r["game_id"]))


def metrics(items):
    n = len(items)
    if n == 0:
        raise ValueError("Empty evaluation fold")
    return {
        "games": n,
        "correct": sum(r["su_correct"] for r in items),
        "su_accuracy": round(sum(r["su_correct"] for r in items)/n, 5),
        "margin_mae": round(sum(r["margin_abs_error"] for r in items)/n, 4),
        "total_mae": round(sum(r["total_abs_error"] for r in items)/n, 4),
        "brier": round(sum(r["brier"] for r in items)/n, 5),
    }


def evaluate(rows, first_week="2026-09-26", min_train=90):
    weeks, predictions = [], defaultdict(list)
    anchor = dt.date.fromisoformat(first_week)
    if not rows or min_train < 1:
        raise ValueError("Empty dataset or invalid training minimum")
    last = max(dt.date.fromisoformat(r["date"]) for r in rows)
    seen = set()
    for n in range(35):
        first = anchor + dt.timedelta(days=7*n)
        if first > last:
            break
        end = first + dt.timedelta(days=7)
        train = [r for r in rows if dt.date.fromisoformat(r["date"]) < first and r["home_games_prior"] >= 1 and r["away_games_prior"] >= 1]
        test = [r for r in rows if first <= dt.date.fromisoformat(r["date"]) < end and r["home_games_prior"] >= 1 and r["away_games_prior"] >= 1]
        if len(train) < min_train or not test:
            continue
        if seen.intersection(g["game_id"] for g in test):
            raise ValueError("Overlapping holdout windows")
        seen.update(g["game_id"] for g in test)
        fold = {"week_start": first.isoformat(), "train_games": len(train),
                "test_games": len(test), "variants": {}}
        for variant, fields in VARIANTS.items():
            scores, sigma = predict(test, fields, fit_ridge(train, fields))
            current = []
            for game, vector in zip(test, scores):
                margin = float(np.clip(vector[0], -55, 55))
                total = float(np.clip(vector[1], 0, 110))
                actual_margin = game["home_score"] - game["away_score"]
                actual_total = game["home_score"] + game["away_score"]
                prob = .5*(1 + math.erf(margin/(sigma*math.sqrt(2))))
                current.append({
                    "variant": variant, "week_start": first.isoformat(),
                    "game_id": game["game_id"], "date": game["date"],
                    "away": game["away"], "home": game["home"],
                    "projected_home_margin": round(margin, 4),
                    "projected_total": round(total, 4),
                    "actual_away_score": game["away_score"],
                    "actual_home_score": game["home_score"],
                    "actual_home_margin": actual_margin,
                    "actual_total": actual_total,
                    "su_correct": int((margin>0)==(actual_margin>0)),
                    "margin_abs_error": abs(margin-actual_margin),
                    "total_abs_error": abs(total-actual_total),
                    "brier": (prob-int(actual_margin>0))**2,
                })
            fold["variants"][variant] = metrics(current)
            predictions[variant].extend(current)
        weeks.append(fold)
    if not weeks:
        raise ValueError("No valid walk-forward evaluation weeks")
    reference = metrics(predictions["full_v03"])
    ref_by_id = {r["game_id"]: r for r in predictions["full_v03"]}
    comparisons = {}
    for name, values in predictions.items():
        out = metrics(values)
        by_id = {r["game_id"]: r for r in values}
        if set(by_id) != set(ref_by_id):
            raise ValueError("Unpaired variant predictions")
        out["correct_change_vs_full"] = out["correct"]-reference["correct"]
        out["margin_mae_change_vs_full"] = round(out["margin_mae"]-reference["margin_mae"], 4)
        out["brier_change_vs_full"] = round(out["brier"]-reference["brier"], 5)
        out["flipped_to_correct"] = sum(not r["su_correct"] and by_id[k]["su_correct"] for k,r in ref_by_id.items())
        out["flipped_to_incorrect"] = sum(r["su_correct"] and not by_id[k]["su_correct"] for k,r in ref_by_id.items())
        out["weeks_improved_su_vs_full"] = sum(w["variants"][name]["correct"] > w["variants"]["full_v03"]["correct"] for w in weeks)
        comparisons[name] = out
    return ({
        "status": "RETROSPECTIVE_FEATURE_ABLATION_RESEARCH_ONLY",
        "season": 2026, "model_version": "v0.3-candidate",
        "historical_pregame_source_provenance_verified": False,
        "model_promoted": False, "safe_for_betting": False,
        "betting_status": "PASS_UNVALIDATED",
        "selection_warning": "Feature ablations evaluated repeatedly on same four weeks: exploratory only, no automatic promotion.",
        "folds": weeks, "comparisons": comparisons,
    }, predictions)


def run(features, labels, output):
    report, predictions = evaluate(load_rows(features, labels))
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    with (root/"feature_consistency_audit.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    with (root/"feature_consistency_predictions.csv").open("x", newline="") as stream:
        columns = list(predictions["full_v03"][0])
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for name in VARIANTS:
            writer.writerows(predictions[name])
    print(json.dumps({"status": report["status"], "folds": len(report["folds"]),
                      "games": report["comparisons"]["full_v03"]["games"],
                      "variants": len(VARIANTS), "model_promoted": False}))
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--features", required=True)
    p.add_argument("--labels", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    run(a.features, a.labels, a.output)

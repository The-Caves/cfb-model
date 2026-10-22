"""Step 3C observed-capture personnel ablations with honest insufficient-data gate.

Historical outputs require captured pregame profiles AND personnel observations
for that game, plus a separately sourced postgame label with known-at time.
No reconstruction of September injuries from October feeds; no market ATS/O-U.
"""
import argparse
import datetime as dt
import json
import math
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from scripts.game_context import parse_time
from scripts.model_v03 import fit_ridge, predict
from scripts.personnel_features import (
    BASE_FIELDS, QB_FIELDS, COVERAGE_FIELDS, STATUS_FIELDS, verify_joined)

STATUS = "OBSERVED_PERSONNEL_ABLATION_RESEARCH_ONLY"
VARIANTS = {
    "profile_baseline": BASE_FIELDS,
    "plus_qb_coverage": BASE_FIELDS + QB_FIELDS,
    "plus_availability_coverage": BASE_FIELDS + COVERAGE_FIELDS,
    "plus_reported_availability": BASE_FIELDS + STATUS_FIELDS,
    "all_personnel": BASE_FIELDS + QB_FIELDS + COVERAGE_FIELDS + STATUS_FIELDS,
}


def _source(value):
    if not isinstance(value, str):
        return False
    try:
        uri = urlsplit(value)
        return uri.scheme == "https" and bool(uri.hostname) and not uri.username and not uri.password
    except ValueError:
        return False


def choose_capture_rows(captures, min_lead_hours=24, max_lead_hours=72):
    """Predeclared selection: latest capture 24-72 hours before kickoff."""
    if not 0 < min_lead_hours < max_lead_hours:
        raise ValueError("Invalid predeclared prediction window")
    candidates = {}
    identities = {}
    duplicate_times = set()
    for capture in captures:
        verify_joined(capture)
        observed = parse_time(capture["captured_at_utc"])
        for game in capture["games"]:
            gid = str(game["game_id"])
            identity = (game["home"], game["away"], parse_time(game["kickoff_utc"]))
            if gid in identities and identities[gid] != identity:
                raise ValueError("ESPN game changed opponents or kickoff across captures")
            identities[gid] = identity
            stamp = (gid, observed)
            if stamp in duplicate_times:
                raise ValueError("Duplicate game observation in capture archive")
            duplicate_times.add(stamp)
            lead = (identity[2]-observed).total_seconds()/3600
            if not min_lead_hours <= lead <= max_lead_hours:
                continue
            if gid not in candidates or observed > candidates[gid][0]:
                candidates[gid] = (observed, game)
    return {gid: row for gid, (_, row) in candidates.items()}


def _read_labels(labels, games):
    if not isinstance(labels, list):
        raise ValueError("Separate audited label list required")
    known = {}
    for r in labels:
        gid = str(r["game_id"])
        if gid in known:
            raise ValueError("Duplicate final label")
        if r.get("evidence_status") != "OBSERVED_POSTGAME_FINAL" or not _source(r.get("source_url")):
            raise ValueError("Postgame result requires observed public final and source URL")
        if type(r.get("home_score")) is not int or type(r.get("away_score")) is not int or (
            r["home_score"] < 0 or r["away_score"] < 0):
            raise ValueError("Invalid final score")
        published = parse_time(r["outcome_known_at_utc"])
        kickoff = parse_time(r["kickoff_utc"])
        if published <= kickoff:
            raise ValueError("Outcome timestamp must follow kickoff")
        if gid in games and (
            r["home"] != games[gid]["home"] or r["away"] != games[gid]["away"] or
            kickoff != parse_time(games[gid]["kickoff_utc"])):
            raise ValueError("Label mismatch to pregame ESPN identity")
        known[gid] = {**r, "_known": published}
    return known


def _has_signal(rows, fields):
    """Cannot claim an injury/QB ablation if its added columns have no variation."""
    for field in fields:
        vals = [r["features"].get(field) for r in rows]
        present = [float(v) for v in vals if v is not None]
        if len(present) >= 2 and len(set(present)) > 1:
            return True
    return False


def _fit_rows(rows, labels):
    return [{**r["features"], "home_score": labels[str(r["game_id"])]["home_score"],
             "away_score": labels[str(r["game_id"])]["away_score"]} for r in rows]


def _score(rows, labels, fields, fitted):
    outputs, _ = predict(_fit_rows(rows, labels), fields, fitted)
    stats = {"graded": 0, "straight_up_correct": 0, "straight_up_graded": 0,
             "margin_absolute_error_sum": 0., "total_absolute_error_sum": 0.}
    for r, values in zip(rows, outputs):
        true = labels[str(r["game_id"])]
        actual_margin = true["home_score"]-true["away_score"]
        actual_total = true["home_score"]+true["away_score"]
        pred_margin = float(max(-55, min(55, values[0])))
        pred_total = float(max(0, min(110, values[1])))
        stats["margin_absolute_error_sum"] += abs(pred_margin-actual_margin)
        stats["total_absolute_error_sum"] += abs(pred_total-actual_total)
        stats["graded"] += 1
        if actual_margin != 0 and pred_margin != 0:
            stats["straight_up_graded"] += 1
            stats["straight_up_correct"] += int((pred_margin > 0) == (actual_margin > 0))
    return stats


def _finish(stats):
    n = stats["graded"]
    if not n:
        return None
    su = stats["straight_up_graded"]
    return {"games": n, "su_accuracy": round(stats["straight_up_correct"]/su, 5) if su else None,
            "su_graded": su,
            "margin_mae": round(stats["margin_absolute_error_sum"]/n, 4),
            "total_mae": round(stats["total_absolute_error_sum"]/n, 4)}


def ablate(captures, labels, evaluation_asof_utc, start_date="2026-09-26",
           min_train_games=90, min_test_games=20):
    if type(min_train_games) is not int or type(min_test_games) is not int or (
        min_train_games < 2 or min_test_games < 1):
        raise ValueError("Minimum train/test games must be positive")
    evaluation = parse_time(evaluation_asof_utc)
    games = choose_capture_rows(captures)
    finals = _read_labels(labels, games)
    selected = {gid: r for gid, r in games.items()
                if gid in finals and finals[gid]["_known"] <= evaluation}
    start = dt.date.fromisoformat(start_date)
    if start.year != 2026:
        raise ValueError("2026-only evaluation")
    most_recent = max((parse_time(r["kickoff_utc"]).date() for r in selected.values()),
                      default=None)
    total = {name: {"graded": 0, "straight_up_correct": 0,
                    "straight_up_graded": 0, "margin_absolute_error_sum": 0.,
                    "total_absolute_error_sum": 0.} for name in VARIANTS}
    attempted = Counter()
    folds = []
    if most_recent:
        for i in range(30):
            beginning = start+dt.timedelta(days=7*i)
            if beginning > most_recent:
                break
            end = beginning+dt.timedelta(days=7)
            boundary = parse_time(beginning.isoformat()+"T00:00:00Z")
            def inside(row, left, right):
                return left <= parse_time(row["kickoff_utc"]).date() < right
            # Only game outcomes already known BEFORE training cutoff.
            train = [r for gid, r in selected.items() if
                     parse_time(r["kickoff_utc"]) < boundary and finals[gid]["_known"] < boundary]
            test = [r for r in selected.values() if inside(r, beginning, end)]
            # Frozen ESPN memberships are essential to prove chronological
            # train/test disjointness; aggregate game counts alone cannot.
            membership = {
                "train_game_ids": sorted(str(r["game_id"]) for r in train),
                "test_game_ids": sorted(str(r["game_id"]) for r in test)}
            if len(train) < min_train_games or len(test) < min_test_games:
                folds.append({"train_before_utc": boundary.isoformat(),
                              "train_games": len(train), "test_games": len(test),
                              **membership,
                              "status": "INSUFFICIENT_OBSERVED_TRAINING_OR_TEST",
                              "models": {}})
                continue
            outcomes = {}
            for name, fields in VARIANTS.items():
                added = [f for f in fields if f not in BASE_FIELDS]
                if added and not _has_signal(train, added):
                    outcomes[name] = {"status": "SKIPPED_NO_TRAINING_FEATURE_VARIATION"}
                    attempted[name+"_skipped"] += 1
                    continue
                # Equal game sets for every variant; no reselecting held-out games.
                fit = fit_ridge(_fit_rows(train, finals), fields)
                scored = _score(test, finals, fields, fit)
                for key in total[name]:
                    total[name][key] += scored[key]
                outcomes[name] = {"status": "RETROSPECTIVE_EVALUATION_OF_CAPTURED_EVIDENCE",
                                  **_finish(scored)}
                attempted[name+"_folds"] += 1
            folds.append({"train_before_utc": boundary.isoformat(),
                          "train_games": len(train), "test_games": len(test),
                          **membership,
                          "status": "RESEARCH_FOLD_EVALUATED", "models": outcomes})
    aggregates = {name: _finish(v) for name, v in total.items()}
    baseline = aggregates["profile_baseline"]
    comparison = {}
    for name in VARIANTS:
        if name == "profile_baseline":
            continue
        result = aggregates[name]
        if result and baseline and result["games"] == baseline["games"]:
            comparison[name] = {
                "paired_games": result["games"],
                "margin_mae_delta_vs_baseline": round(result["margin_mae"]-baseline["margin_mae"], 4),
                "total_mae_delta_vs_baseline": round(result["total_mae"]-baseline["total_mae"], 4),
                "su_accuracy_delta_vs_baseline": (
                    round(result["su_accuracy"]-baseline["su_accuracy"], 5)
                    if result["su_accuracy"] is not None and baseline["su_accuracy"] is not None else None)}
        else:
            comparison[name] = {"status": "NOT_COMPARABLE_MISSING_MATCHED_FOLDS"}
    return {
        "status": STATUS, "season": 2026,
        "evaluation_asof_utc": evaluation.isoformat(),
        "prediction_policy": "LATEST_CAPTURE_24_TO_72_HOURS_BEFORE_KICKOFF",
        "captures_total": len(captures),
        "eligible_distinct_games": len(games),
        "labeled_eligible_games": len(selected),
        "unlabeled_or_not_yet_known": len(games)-len(selected),
        "folds": folds, "aggregate": aggregates,
        "comparisons": comparison,
        "qa": dict(attempted),
        "evidence_sufficient_for_real_ablation": bool(baseline and
            baseline["games"] >= min_test_games and
            any(comparison[n].get("paired_games") for n in comparison)),
        "historical_publication_times_independently_verified": False,
        "statistical_significance_established": False,
        "ats_and_totals_betting_grades": "UNAVAILABLE_NO_VERIFIED_POINT_IN_TIME_MARKET",
        "model_promoted": False, "safe_for_betting": False,
        "betting_status": "PASS_UNVALIDATED"}


def run(captures_dir, output, labels_file=None, evaluation_asof_utc=None):
    root = Path(captures_dir)
    snapshots = [json.loads(p.read_text()) for p in sorted(root.glob("personnel-joined-*.json"))]
    # Deliberately empty if no independently observed, separately supplied finals.
    labels = json.loads(Path(labels_file).read_text()) if labels_file else []
    result = ablate(snapshots, labels, evaluation_asof_utc or
                    dt.datetime.now(dt.timezone.utc).isoformat())
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"status": STATUS, "captures": len(snapshots),
                      "eligible_games": result["eligible_distinct_games"],
                      "labeled": result["labeled_eligible_games"],
                      "evidence_sufficient": result["evidence_sufficient_for_real_ablation"],
                      "betting_status": "PASS_UNVALIDATED"}))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--captures-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--labels", default=None)
    p.add_argument("--evaluation-asof", default=None)
    a = p.parse_args()
    run(a.captures_dir, a.output, a.labels, a.evaluation_asof)

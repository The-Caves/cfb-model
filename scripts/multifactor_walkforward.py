"""Strict chronological held-out margin/total/SU evaluation of observed features.

Uses original pregame captures and independently observed finals. Weather and
availability feature variants are evaluated on the SAME test games. This does
not invent historical odds, predict bets, or authenticate revised PBP releases.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
from scripts.game_context import parse_time
from scripts.model_v03 import fit_ridge, predict
from scripts.personnel_features import BASE_FIELDS
from scripts.weather_matchups import FIELDS as WEATHER_FIELDS
from scripts.player_replacement import POSITIONS

STATUS = "MULTIFACTOR_OBSERVED_WALKFORWARD_RESEARCH_ONLY"
WX = tuple("wx_" + field for field in WEATHER_FIELDS)
ABS = tuple("absence_" + position.lower() for position in POSITIONS)
INJURY_STRESS = ("verified_ol_absence_pressure_interaction",
                 "verified_qb_absence_pressure_interaction")
VARIANTS = {"baseline": tuple(BASE_FIELDS),
            "plus_weather": tuple(BASE_FIELDS) + WX,
            "plus_absences": tuple(BASE_FIELDS) + ABS,
            "plus_injury_pressure_interaction": tuple(BASE_FIELDS) + ABS + INJURY_STRESS,
            "all_features": tuple(BASE_FIELDS) + WX + ABS + INJURY_STRESS}

def injury_pressure_interaction(report, matchup_pressure):
    """As-of observed OL/QB absences × relative historical pressure *proxy*.

    Both schools' position-count reports must be verified. Missing coverage
    yields None (not zero). This is not an estimated player-value coefficient.
    """
    if (report.get("coverage") != "BOTH_REPORTS" or
        type(matchup_pressure) not in (int,float) or
        not math.isfinite(matchup_pressure)):
        return (None,None)
    h,a=report.get("home_report_by_position"),report.get("away_report_by_position")
    if not isinstance(h,dict) or not isinstance(a,dict) or any(
        r.get("coverage")!="VERIFIED_REPORT_REVIEWED" or not isinstance(r.get("absences"),dict)
        for r in (h,a)):
        return (None,None)
    def count(r,position):
        value=r["absences"].get(position)
        if type(value) is not int or value<0:
            raise ValueError("Invalid verified personnel position count")
        return value
    # The pregame score-profile pressure_form is a relative rate, not an
    # absolute pass-rush grade. Coefficient must be learned out of sample.
    ol=(count(h,"OL")-count(a,"OL"))*float(matchup_pressure)
    qb=(count(h,"QB")-count(a,"QB"))*float(matchup_pressure)
    return (ol,qb)

def prepare(features, labels, weather=(), replacement=(), evaluation_asof_utc=None):
    evaluation = parse_time(evaluation_asof_utc or dt.datetime.now(dt.timezone.utc).isoformat())
    def by_id(records, kind):
        out = {}
        for row in records:
            gid = str(row["game_id"])
            if gid in out:
                raise ValueError("Duplicate " + kind + " game")
            out[gid] = row
        return out
    w = by_id(weather, "weather")
    p = by_id(replacement, "replacement")
    source = by_id(features, "feature")
    finals = by_id(labels, "label")
    if any(gid not in source for gid in finals):
        raise ValueError("Final without original pregame feature")
    rows = []
    for gid, feature in source.items():
        if feature.get("betting_status") != "PASS_UNVALIDATED":
            raise ValueError("Untrusted source feature")
        decision = parse_time(feature["capture_utc"])
        kickoff = parse_time(feature["kickoff_utc"])
        if not decision < kickoff or decision > evaluation:
            raise ValueError("Pregame feature after kickoff or evaluation")
        fields = feature["features"]
        if any(name not in fields for name in BASE_FIELDS):
            raise ValueError("Missing baseline feature")
        row = {"game_id": gid, "kickoff_utc": feature["kickoff_utc"],
               "capture_utc": feature["capture_utc"],
               **{name: fields[name] for name in BASE_FIELDS}}
        if gid in w:
            weather_row = w[gid]
            if (parse_time(weather_row["decision_asof_utc"]) != decision or
                parse_time(weather_row["forecast_issued_at_utc"]) > decision or
                parse_time(weather_row["forecast_captured_at_utc"]) > decision or
                parse_time(weather_row["kickoff_utc"]) != kickoff):
                raise ValueError("Weather unavailable at original decision")
            for name in WEATHER_FIELDS:
                row["wx_" + name] = weather_row["features"].get(name)
        else:
            row.update({name: None for name in WX})
        if gid in p:
            injury = p[gid]
            if (parse_time(injury["decision_asof_utc"]) != decision or
                parse_time(injury["kickoff_utc"]) != kickoff):
                raise ValueError("Availability unavailable at original decision")
            diff = injury.get("absence_differentials")
            if injury.get("coverage") != "BOTH_REPORTS":
                diff = None
            if diff is not None and set(diff) != set(POSITIONS):
                raise ValueError("Invalid replacement schema")
            for position in POSITIONS:
                row["absence_" + position.lower()] = diff[position] if diff is not None else None
            x,y=injury_pressure_interaction(
                injury,fields.get("pressure_form")) if diff is not None else (None,None)
            row[INJURY_STRESS[0]]=x
            row[INJURY_STRESS[1]]=y
        else:
            row.update({name: None for name in ABS})
            row.update({name: None for name in INJURY_STRESS})
        label = finals.get(gid)
        if label is None:
            continue
        known = parse_time(label["outcome_known_at_utc"])
        if (known <= kickoff or known > evaluation or
            label.get("evidence_status") != "OBSERVED_POSTGAME_FINAL" or
            label["home"] != feature["home"] or label["away"] != feature["away"] or
            parse_time(label["kickoff_utc"]) != kickoff):
            raise ValueError("Invalid or future outcome evidence")
        if any(type(label[name]) is not int or label[name] < 0
               for name in ("home_score", "away_score")):
            raise ValueError("Invalid final score")
        row.update(home_score=label["home_score"], away_score=label["away_score"],
                   outcome_known_at_utc=label["outcome_known_at_utc"])
        rows.append(row)
    return sorted(rows, key=lambda r:(r["kickoff_utc"], r["game_id"]))

def walkforward(rows, first_test_utc, evaluation_asof_utc, weeks=12,
                min_train=90, min_test=20):
    first = parse_time(first_test_utc)
    evaluation = parse_time(evaluation_asof_utc)
    if type(weeks) is not int or weeks < 1 or min_train < 2 or min_test < 1:
        raise ValueError("Invalid evaluation policy")
    if len({r["game_id"] for r in rows}) != len(rows):
        raise ValueError("Repeated game")
    folds = []
    for week in range(weeks):
        start = first + dt.timedelta(days=7*week)
        end = start + dt.timedelta(days=7)
        if start > evaluation:
            break
        train = [r for r in rows if parse_time(r["kickoff_utc"]) < start
                 and parse_time(r["outcome_known_at_utc"]) < start]
        test = [r for r in rows if start <= parse_time(r["kickoff_utc"]) < end
                and parse_time(r["outcome_known_at_utc"]) <= evaluation]
        if set(r["game_id"] for r in train) & set(r["game_id"] for r in test):
            raise ValueError("Training/test game overlap")
        fold = {"training_cutoff_utc": start.isoformat(),
                "train_game_ids": sorted(r["game_id"] for r in train),
                "test_game_ids": sorted(r["game_id"] for r in test),
                "models": {}}
        if len(train) < min_train or len(test) < min_test:
            fold["status"] = "INSUFFICIENT_OBSERVED_GAMES"
            folds.append(fold)
            continue
        fold["status"] = "RESEARCH_EVALUATED"
        for name, columns in VARIANTS.items():
            extras = [field for field in columns if field not in BASE_FIELDS]
            if name == "plus_injury_pressure_interaction" and not any(
                len({r[field] for r in train if r.get(field) is not None}) > 1
                for field in INJURY_STRESS):
                fold["models"][name] = {"status": "SKIPPED_NO_VERIFIED_INJURY_INTERACTION_VARIATION"}
                continue
            if extras and not any(
                len({r[field] for r in train if r.get(field) is not None}) > 1
                for field in extras):
                fold["models"][name] = {"status": "SKIPPED_NO_TRAINING_VARIATION"}
                continue
            params = fit_ridge(train, columns)
            estimates, sigma = predict(test, columns, params)
            margin_err = total_err = 0.0
            su_correct = su_count = 0
            for row, predicted in zip(test, estimates):
                margin = float(max(-55, min(55, predicted[0])))
                total = float(max(0, min(110, predicted[1])))
                actual_margin = row["home_score"] - row["away_score"]
                margin_err += abs(margin-actual_margin)
                total_err += abs(total-row["home_score"]-row["away_score"])
                if actual_margin and margin:
                    su_count += 1
                    su_correct += int((margin > 0) == (actual_margin > 0))
            fold["models"][name] = {
                "status": "HELDOUT_RESEARCH_ONLY", "games": len(test),
                "margin_mae": round(margin_err/len(test), 4),
                "total_mae": round(total_err/len(test), 4),
                "su_accuracy": round(su_correct/su_count, 5) if su_count else None}
        folds.append(fold)
    return {"status": STATUS, "season": 2026,
            "folds": folds, "labeled_games": len(rows),
            "evaluation_asof_utc": evaluation.isoformat(),
            "same_heldout_games_per_variant": True,
            "historical_pbp_publication_authenticated": False,
            "historical_market_grades_available": False,
            "model_promoted": False, "safe_for_betting": False,
            "betting_status": "PASS_UNVALIDATED"}

def run(dataset, output, first_test_utc, weather_file=None, replacement_file=None):
    root = Path(dataset)
    features = json.loads((root/"pregame_features.json").read_text())
    labels = json.loads((root/"postgame_labels.json").read_text())
    wx = json.loads(Path(weather_file).read_text())["games"] if weather_file else []
    rp = json.loads(Path(replacement_file).read_text())["games"] if replacement_file else []
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    rows = prepare(features, labels, wx, rp, now)
    report = walkforward(rows, first_test_utc, now)
    dest = Path(output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps({"status": STATUS, "labeled_games": len(rows),
                      "folds": len(report["folds"]), "model_promoted": False}))
    return report

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--first-test", default="2026-09-26T00:00:00Z")
    p.add_argument("--weather")
    p.add_argument("--replacement")
    a = p.parse_args()
    run(a.dataset, a.output, a.first_test, a.weather, a.replacement)

"""Prospective paired challenger audit; immutable input hashes and no auto promotion.

Compare all versions on identical game IDs and actual archived outcomes.
No retroactive game scoring, no in-sample selection, no made-up market grades.
This is an extensible research evaluator, not a substitute for archive receipts.
"""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.game_context import parse_time

STATUS = "PAIRED_MODEL_COMPETITION_RESEARCH_ONLY"


def digest(record):
    data = {k: v for k, v in record.items() if k != "record_sha256"}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _number(x):
    if type(x) not in (float, int) or not math.isfinite(x):
        raise ValueError("Invalid model forecast or observed score")
    return float(x)


def _forecast(row, asof):
    if row.get("record_sha256") != digest(row):
        raise ValueError("Tampered or unbound frozen forecast")
    if row.get("betting_status") != "PASS_UNVALIDATED" or row.get("safe_for_betting") is not False:
        raise ValueError("Unsafe forecast clearance")
    if not row.get("game_id") or not row.get("model_version") or row.get("home") == row.get("away"):
        raise ValueError("Malformed game/model identity")
    issued = parse_time(row["issued_at_utc"])
    kickoff = parse_time(row["kickoff_utc"])
    if not issued < kickoff or issued > asof:
        raise ValueError("Unfrozen or future forecast")
    for name in ("predicted_margin", "predicted_total"):
        _number(row[name])


def evaluate(forecasts, finals, evaluated_at_utc, reference="V03", minimum_pairs=100):
    if type(minimum_pairs) is not int or minimum_pairs < 2:
        raise ValueError("Invalid validation sample floor")
    now = parse_time(evaluated_at_utc)
    by_game = defaultdict(dict)
    for row in forecasts:
        _forecast(row, now)
        gid = str(row["game_id"])
        version = row["model_version"]
        if version in by_game[gid]:
            raise ValueError("Multiple forecasts for one game/version: freeze one cutoff")
        by_game[gid][version] = row
    completed = {}
    for row in finals:
        gid = str(row["game_id"])
        if gid in completed:
            raise ValueError("Duplicate independently observed final")
        kickoff, known = parse_time(row["kickoff_utc"]), parse_time(row["outcome_known_at_utc"])
        if not kickoff < known <= now or not str(row.get("source_url","")).startswith("https://"):
            raise ValueError("Future or unsourced actual final")
        completed[gid] = row
    variants = sorted({v for bundle in by_game.values() for v in bundle if v != reference})
    compared = {}
    for version in variants:
        paired = []
        for gid, versions in by_game.items():
            base, challenger = versions.get(reference), versions.get(version)
            result = completed.get(gid)
            if base is None or challenger is None or result is None:
                continue
            identity = (base["home"],base["away"],parse_time(base["kickoff_utc"]))
            if (challenger["home"],challenger["away"],parse_time(challenger["kickoff_utc"])) != identity or (
                result["home"],result["away"],parse_time(result["kickoff_utc"])) != identity:
                raise ValueError("Forecast/final fixture identity mismatch")
            actual_margin = _number(result["home_score"])-_number(result["away_score"])
            actual_total = _number(result["home_score"])+_number(result["away_score"])
            be = abs(base["predicted_margin"]-actual_margin)
            ce = abs(challenger["predicted_margin"]-actual_margin)
            bt = abs(base["predicted_total"]-actual_total)
            ct = abs(challenger["predicted_total"]-actual_total)
            paired.append({
                "game_id": gid, "baseline_sha256":base["record_sha256"],
                "challenger_sha256":challenger["record_sha256"],
                "actual_margin":actual_margin,"actual_total":actual_total,
                "baseline_margin_abs_error":be,"candidate_margin_abs_error":ce,
                "baseline_total_abs_error":bt,"candidate_total_abs_error":ct,
                "baseline_home_bias":base["predicted_margin"]-actual_margin,
                "candidate_home_bias":challenger["predicted_margin"]-actual_margin,
            })
        n=len(paired)
        def avg(k):
            return round(sum(r[k] for r in paired)/n,5) if n else None
        compared[version] = {
            "status": "ENOUGH_PAIRED_GAMES_FOR_REVIEW" if n >= minimum_pairs else "INSUFFICIENT_PAIRED_PROSPECTIVE_GAMES",
            "paired_games": n,
            "total_completed_reference_games": sum(reference in by_game[gid] for gid in completed if gid in by_game),
            "baseline_margin_mae":avg("baseline_margin_abs_error"),
            "candidate_margin_mae":avg("candidate_margin_abs_error"),
            "baseline_total_mae":avg("baseline_total_abs_error"),
            "candidate_total_mae":avg("candidate_total_abs_error"),
            "baseline_signed_home_bias":avg("baseline_home_bias"),
            "candidate_signed_home_bias":avg("candidate_home_bias"),
            "paired_margin_mae_delta":round(avg("candidate_margin_abs_error")-avg("baseline_margin_abs_error"),5) if n else None,
            "paired_total_mae_delta":round(avg("candidate_total_abs_error")-avg("baseline_total_abs_error"),5) if n else None,
            "games": sorted(paired, key=lambda r:r["game_id"]),
            "promotion_eligible": False,
            "not_promoted_reason": "REQUIRES_SOURCE_AUDIT_CALIBRATION_MARKET_BASELINES_AND_INDEPENDENT_HUMAN_REVIEW",
        }
    return {
        "status": STATUS,"reference":reference,"evaluated_at_utc":now.isoformat(),
        "versions":compared, "market_ats_totals_grades":None,
        "model_promoted": False, "safe_for_betting": False,"betting_status":"PASS_UNVALIDATED",
    }


def run(forecasts_path, finals_path, output_path, asof, reference="V03"):
    forecasts = json.loads(Path(forecasts_path).read_text())
    finals = json.loads(Path(finals_path).read_text())
    report = evaluate(forecasts, finals, asof, reference)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    return report


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--forecasts",required=True);p.add_argument("--finals",required=True)
    p.add_argument("--output",required=True);p.add_argument("--asof",required=True)
    p.add_argument("--reference",default="V03")
    a=p.parse_args()
    run(a.forecasts,a.finals,a.output,a.asof,a.reference)

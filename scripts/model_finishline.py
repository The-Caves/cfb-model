"""Consolidated, fail-closed research finish-line report.

Never mistake green engineering CI for predictive validation. All counts and
metrics derive from frozen, checksum-authenticated evidence; no prices, grades,
or model promotions are fabricated.
"""
import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path

from scripts import context_archive as store
from scripts.personnel_coverage_audit import audit as coverage_audit
from scripts.personnel_forecast_grade import (
    INDEX as GRADE_INDEX, STATUS as GRADING_STATUS,
    empty_grade_index, verify_prior_grade,
)
from scripts.personnel_validation_readiness import STATUS as READINESS_STATUS

STATUS = "CFB_2026_FINISH_LINE_RESEARCH_ONLY"


def _nonnegative(value, field):
    if type(value) is not int or value < 0:
        raise ValueError("Invalid nonnegative count: " + field)
    return value


def wilson_interval(correct, n):
    if n == 0:
        return None
    z = 1.959963984540054
    p = correct / n
    denom = 1 + z*z/n
    center = (p + z*z/(2*n))/denom
    radius = z*math.sqrt((p*(1-p) + z*z/(4*n))/n)/denom
    return [round(max(0, center-radius), 5), round(min(1, center+radius), 5)]


def grade_diagnostics(grades):
    """Descriptive metrics on *actual independently archived* postgame grades."""
    seen = set()
    su_count = 0
    su_correct = 0
    margin_error = 0.0
    total_error = 0.0
    brier_total = 0.0
    for g in grades:
        gid = str(g["game_id"])
        if gid in seen:
            raise ValueError("Duplicate frozen graded matchup")
        seen.add(gid)
        if (g.get("status") != "OBSERVED_FORECAST_GRADED_RESEARCH_ONLY"
            or g.get("safe_for_betting") is not False
            or g.get("model_validated") is not False
            or g.get("betting_status") != "PASS_UNVALIDATED"
            or g.get("ats_grade") is not None
            or g.get("over_under_grade") is not None):
            raise ValueError("Nonresearch or invented market grade")
        pm, pt, actual, total, prob = (g[k] for k in (
            "predicted_margin", "predicted_total", "actual_margin",
            "actual_total", "uncalibrated_win_probability"))
        if any(type(x) not in (float,int) or not math.isfinite(x) for x in (pm,pt,actual,total,prob)):
            raise ValueError("Malformed prospectively frozen grade")
        if not 0 <= prob <= 1:
            raise ValueError("Invalid frozen uncalibrated probability")
        if (type(g.get("actual_home_score")) is not int
            or type(g.get("actual_away_score")) is not int
            or min(g["actual_home_score"],g["actual_away_score"]) < 0
            or actual != g["actual_home_score"]-g["actual_away_score"]
            or total != g["actual_home_score"]+g["actual_away_score"]):
            raise ValueError("Invalid observed final arithmetic")
        me=abs(pm-actual)
        te=abs(pt-total)
        if abs(g["margin_abs_error"]-round(me,5))>1e-5 or abs(g["total_abs_error"]-round(te,5))>1e-5:
            raise ValueError("Tampered model error calculation")
        margin_error+=me
        total_error+=te
        expected_su=(int((pm>0)==(actual>0)) if pm != 0 and actual != 0 else None)
        if g["su_correct"] != expected_su:
            raise ValueError("Contradictory win grade")
        if expected_su is not None:
            expected_brier=round((prob-int(actual>0))**2,6)
            if (type(g.get("uncalibrated_brier_diagnostic")) not in (int,float)
                or abs(g["uncalibrated_brier_diagnostic"]-expected_brier)>1e-6):
                raise ValueError("Contradictory Brier grade")
            su_count+=1
            su_correct+=expected_su
            brier_total+=expected_brier
        elif g.get("uncalibrated_brier_diagnostic") is not None:
            raise ValueError("Tie/undecided fixture cannot have Brier grade")
    n=len(grades)
    return {
        "independently_archived_grades":n,
        "su_graded_games":su_count,
        "su_correct":su_correct,
        "su_accuracy":round(su_correct/su_count,5) if su_count else None,
        "su_accuracy_wilson_95pct":wilson_interval(su_correct,su_count),
        "margin_mae":round(margin_error/n,4) if n else None,
        "total_mae":round(total_error/n,4) if n else None,
        "uncalibrated_brier":round(brier_total/su_count,5) if su_count else None,
        "constant_50pct_brier_baseline":0.25 if su_count else None,
        "paired_real_market_comparison":None,
        "statistical_significance_established":False,
        "model_validated":False,
    }


def read_archived_grades():
    raw=store.get_blob_file(GRADE_INDEX)
    index=json.loads(raw) if raw is not None else empty_grade_index()
    records={}
    for entry in index.get("games",{}).values():
        path=entry["path"]
        # Path membership and checksum are checked by verify_prior_grade.
        if path in records:
            raise ValueError("Duplicated graded archive path")
        packed=store.get_blob_file(path)
        if packed is None:
            raise ValueError("Missing historical frozen graded record")
        records[path]=store.unpack(packed)
    verify_prior_grade(index,records)
    return [records[entry["path"]] for _,entry in sorted(index["games"].items())]


def build(readiness,grading,grades,context=None):
    if (readiness.get("status") != READINESS_STATUS
        or readiness.get("betting_status") != "PASS_UNVALIDATED"
        or readiness.get("safe_for_betting") is not False
        or readiness.get("model_promoted") is not False
        or readiness.get("model_ready_for_promotion") is not False):
        raise ValueError("Untrusted preregistered readiness audit")
    if (grading.get("status") != GRADING_STATUS
        or grading.get("betting_status") != "PASS_UNVALIDATED"
        or grading.get("safe_for_betting") is not False
        or grading.get("model_promoted") is not False):
        raise ValueError("Untrusted prospective grade audit")
    paired=_nonnegative(readiness["valid_paired_game_ids"],"paired")
    eligible=_nonnegative(readiness["policy_eligible_game_ids"],"eligible")
    indexed=_nonnegative(grading["indexed_final_games"],"indexed")
    frozen=_nonnegative(grading["total_frozen_graded_games"],"graded")
    if paired > eligible or frozen != len(grades) or frozen > indexed:
        raise ValueError("Research archive counts disagree")
    metrics=grade_diagnostics(grades)
    reports=None
    if context is not None:
        coverage=coverage_audit(context)
        reports=coverage["summary"]
        if coverage["betting_status"]!="PASS_UNVALIDATED":
            raise ValueError("Nonresearch personnel evidence")
    checks=readiness["checks"]
    if not isinstance(checks,dict) or any(type(v) is not bool for v in checks.values()):
        raise ValueError("Invalid preregistered checks")
    outstanding=[
        {"id":"GRADE_FROZEN_GAMES","complete":frozen >= 60,
         "observed":frozen,"target":60,
         "why":"Observed postgame outcomes for original 24–72h frozen forecasts"},
        {"id":"HISTORICALLY_ASOF_PBP","complete":checks.get("independent_historical_pbp_publication_verified") is True,
         "why":"Independent evidence when retrospective advanced data became available"},
        {"id":"AUTHENTIC_MARKET_LINES","complete":checks.get("authentic_predecision_market_spreads_totals_verified") is True,
         "why":"Consent-based licensed market observations, separate from public repository"},
        {"id":"REPEATED_CHRONOLOGICAL_EVALUATION","complete":(
            checks.get("at_least_3_nonoverlapping_evaluated_folds") is True
            and checks.get("at_least_60_matched_heldout_games") is True),
         "why":"Leakage-safe comparable held-out folds"},
        {"id":"QB_EVIDENCE_COVERAGE","complete":checks.get("at_least_25pct_qb_slots_reviewed") is True,
         "why":"Game-specific reviewed official QB confirmations"},
        {"id":"INJURY_REPORT_COVERAGE","complete":checks.get("at_least_60pct_two_team_reports_verified") is True,
         "why":"Both teams covered by timely verified official reports"},
        {"id":"OUT_OF_SAMPLE_SIGNIFICANCE","complete":checks.get("out_of_sample_statistical_significance_verified") is True,
         "why":"Actual held-out calibration and predictive baseline comparisons"},
    ]
    # Even full research coverage does not grant betting validation on its own.
    return {
        "status":STATUS,"season":2026,"betting_status":"PASS_UNVALIDATED",
        "safe_for_betting":False,"model_promoted":False,"model_validated":False,
        "observed":{"policy_eligible_pregame_games":eligible,
                    "audited_paired_final_games":paired,
                    "indexed_final_games":indexed,
                    "frozen_prospective_graded_games":frozen,
                    "personnel_context_coverage":reports},
        "prospective_research_metrics":metrics,
        "completion_requirements":outstanding,
        "unresolved_requirements":[x["id"] for x in outstanding if not x["complete"]],
        "source_constraints":{"actual_fanduel_odds_available":False,
                              "asof_advanced_publication_authenticated":False,
                              "external_archive_immutability_authenticated":False},
        "research_only":True,
    }


def run(readiness_path,grading_path,output,context_path=None,archive_reader=read_archived_grades):
    readiness=json.loads(Path(readiness_path).read_text())
    grading=json.loads(Path(grading_path).read_text())
    context=json.loads(Path(context_path).read_text()) if context_path else None
    result=build(readiness,grading,archive_reader(),context)
    dest=Path(output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf-8") as fp:
        json.dump(result,fp,sort_keys=True,indent=2,allow_nan=False)
        fp.write("\n")
    compact={"status":STATUS,"graded":result["observed"]["frozen_prospective_graded_games"],
             "paired":result["observed"]["audited_paired_final_games"],
             "blocked":result["unresolved_requirements"],"betting_status":"PASS_UNVALIDATED"}
    print(json.dumps(compact))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
            f.write("## CFB 2026 model finish-line audit\n\n")
            f.write("Research-only; no sportsbook prices or validated betting model.\n\n")
            f.write("| Measure | Actual |\n|---|---:|\n")
            f.write(f"| Frozen prospectively graded games | {compact['graded']} |\n")
            f.write(f"| Paired as-observed finals | {compact['paired']} |\n")
            f.write(f"| Unresolved requirements | {len(compact['blocked'])} |\n")
            f.write("\n**Open gates:** "+", ".join(compact["blocked"])+"\n")
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--readiness",required=True)
    parser.add_argument("--grading",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--context")
    args=parser.parse_args()
    run(args.readiness,args.grading,args.output,args.context)

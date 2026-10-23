"""Milestone 5: fail-closed acceptance audit of verified research settlement.

Independently recompute grades and performance from archived match evidence.
No synthetic predictions, historical lines, or claimed profitability.
"""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
from scripts.free_market_final_grade import settle
from scripts.free_market_performance import report
from scripts.game_context import parse_time

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)

def audit(matches,grades,performance,su_records):
    if (matches.get("betting_status")!="PASS_UNVALIDATED" or
        grades.get("betting_status")!="PASS_UNVALIDATED" or
        performance.get("betting_status")!="PASS_UNVALIDATED" or
        performance.get("model_validated") is not False):
        raise ValueError("Research-only safety markers missing")
    if matches["asof_utc"]!=grades["asof_utc"] or grades["asof_utc"]!=performance["asof_utc"]:
        raise ValueError("As-of timestamps differ")
    counts=Counter()
    for r in matches["rows"]:
        status=r["status"];counts[status]+=1
        market=parse_time(r["market_observed_utc"])
        forecast=parse_time(r["forecast_observed_utc"])
        kickoff=parse_time(r["kickoff_utc"])
        if not market<=forecast<kickoff:
            raise ValueError("Non-prospective market chronology")
        if status=="MATCHED_VERIFIED_FINAL":
            observed=parse_time(r["final_observed_at_utc"])
            if observed<kickoff or observed>parse_time(matches["asof_utc"]):
                raise ValueError("Final observation chronology invalid")
            if not isinstance(r.get("final_record_sha256"),str) or len(r["final_record_sha256"])!=64:
                raise ValueError("Invalid final archive SHA")
            if not r.get("final_archive_path"):
                raise ValueError("Missing archived final path")
        elif status not in ("AWAITING_VERIFIED_FINAL","IDENTITY_MISMATCH",
                            "KICKOFF_CHANGED_NO_AUTOMATIC_MATCH","FINAL_NOT_YET_OBSERVED"):
            raise ValueError("Unknown matching state")
    if counts!=Counter({k:v for k,v in matches["summary"].items() if k!="total"}):
        raise ValueError("Matching counts disagree")
    if matches["summary"]["total"]!=len(matches["rows"]):
        raise ValueError("Matching row count disagrees")
    expected_grades=settle(matches)
    if canonical(expected_grades)!=canonical(grades):
        raise ValueError("Grading differs from independently recalculated results")
    expected_performance=report(matches,expected_grades,su_records)
    if canonical(expected_performance)!=canonical(performance):
        raise ValueError("Cumulative performance differs from independently recalculated results")
    for market in ("ats","total"):
        s=performance["summary"][market]
        if s["decisions"]!=s["wins"]+s["losses"]:
            raise ValueError("Decision count invalid")
        if (performance["summary"]["raw_provider_forecasts"][market] !=
            performance["summary"]["unique_games"][market]+
            performance["summary"]["duplicates_excluded"][market]):
            raise ValueError("Duplicate accounting invalid")
    graded=counts["MATCHED_VERIFIED_FINAL"]
    return {"status":"MILESTONE5_ACCEPTANCE_RESEARCH_ONLY",
        "checks":{"frozen_chronology":"PASS","verified_final_evidence":"PASS",
                  "independent_grade_recalculation":"PASS",
                  "independent_performance_recalculation":"PASS",
                  "unique_game_accounting":"PASS"},
        "evidence":{"provider_game_forecasts":len(matches["rows"]),
            "verified_final_matches":graded,
            "awaiting_verified_final":counts["AWAITING_VERIFIED_FINAL"],
            "identity_mismatch":counts["IDENTITY_MISMATCH"],
            "kickoff_mismatch":counts["KICKOFF_CHANGED_NO_AUTOMATIC_MATCH"],
            "final_not_yet_observed":counts["FINAL_NOT_YET_OBSERVED"],
            "ats_unique_games":performance["summary"]["unique_games"]["ats"],
            "totals_unique_games":performance["summary"]["unique_games"]["total"],
            "su_decisions":performance["summary"]["su"]["decisions"]},
        "performance_sha256":hashlib.sha256(canonical(performance).encode()).hexdigest(),
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
        "model_validated":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for field in ("matches","grades","performance","output"):
        p.add_argument("--"+field,required=True)
    a=p.parse_args()
    from scripts.free_market_performance import su_archive
    result=audit(json.loads(Path(a.matches).read_text()),
                 json.loads(Path(a.grades).read_text()),
                 json.loads(Path(a.performance).read_text()),su_archive())
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result))

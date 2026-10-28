"""Score only genuinely frozen, same-game shadow forecasts and observed finals.

The reference Step3G grade index already chooses the latest independently
archived 24-72h V03 forecast for each verified completed fixture. Shadow scores
must match its EXACT game, original V03 SHA, row hash and selected run, never a
different forecast cut. Every variant is scored on the exact same matched games
as its V03 reference. No market ATS/O-U or retrospective synthetic predictions.
"""
import argparse
import datetime as dt
import json
import math
import os
from collections import defaultdict
from pathlib import Path

from scripts import context_archive as store
from scripts.personnel_features import sha256
from scripts.personnel_forecast import checksum
from scripts.personnel_forecast_grade import (
    INDEX as BASE_GRADE_INDEX, empty_grade_index, verify_prior_grade)
from scripts.personnel_results_archive import ROOT, _commit_material
from scripts.model_shadow_forecast import (
    INDEX as SHADOW_INDEX, STATUS as SHADOW_STATUS, MODELS, VERSIONS, verify_shadow)
from scripts.game_context import parse_time as at

STATUS="SHADOW_PROSPECTIVE_PAIRED_GRADING_RESEARCH_ONLY"
INDEX=ROOT+"/shadow_grade_index.json"

def evaluate(shadows, grades, asof_utc):
    now=at(asof_utc)
    by_run={}
    for shadow in shadows:
        verify_shadow(shadow)
        key=str(shadow["run_id"])
        if key in by_run:raise ValueError("Duplicate immutable shadow run")
        if at(shadow["shadow_observed_utc"])>now:raise ValueError("Shadow from future")
        by_run[key]=shadow
    if len({str(g["game_id"]) for g in grades})!=len(grades):
        raise ValueError("Duplicate real reference grade")
    per_game=[]
    reasons=defaultdict(int)
    for grade in sorted(grades,key=lambda r:(r["kickoff_utc"],str(r["game_id"]))):
        if (grade.get("status")!="OBSERVED_FORECAST_GRADED_RESEARCH_ONLY" or
            grade.get("betting_status")!="PASS_UNVALIDATED" or
            grade.get("model_validated") is not False or
            grade.get("safe_for_betting") is not False or
            grade.get("ats_grade") is not None or grade.get("over_under_grade") is not None):
            raise ValueError("Not a valid independently archived reference grade")
        run=str(grade["forecast_run_id"])
        frozen=by_run.get(run)
        if frozen is None:
            reasons["no_shadows_for_selected_baseline_run"]+=1
            continue
        if frozen["baseline_forecast_sha256"]!=grade["forecast_bundle_sha256"]:
            raise ValueError("Wrong baseline archive used for candidate comparison")
        matching=[r for r in frozen["games"] if str(r["game_id"])==str(grade["game_id"])]
        if not matching:
            reasons["target_game_not_in_shadow_capture"]+=1
            continue
        if len(matching)!=1:raise ValueError("Duplicate game within shadow")
        row=matching[0]
        if (row["baseline_row_sha256"]!=grade["frozen_forecast_row_sha256"]
            or row["home"]!=grade["home"] or row["away"]!=grade["away"]
            or at(row["kickoff_utc"])!=at(grade["kickoff_utc"])):
            raise ValueError("Shadow original forecast identity mismatch")
        instant=at(frozen["shadow_observed_utc"])
        kickoff=at(row["kickoff_utc"])
        if not instant<kickoff<at(grade["final_outcome_known_at_utc"])<=now:
            raise ValueError("Shadow/label chronology invalid")
        lead=(kickoff-instant).total_seconds()/3600
        if row["policy_24_to_72h_eligible"]!=(24<=lead<=72):
            raise ValueError("Tampered shadow eligibility rule")
        if not 24<=lead<=72:
            reasons["not_predeclared_24_to_72_hour_window"]+=1
            continue
        original=row["models"]["active_v03"]
        if (original["status"]!="SHADOW_FROZEN_RESEARCH" or
            original["predicted_home_margin"]!=grade["predicted_margin"] or
            original["predicted_total"]!=grade["predicted_total"]):
            raise ValueError("Reference margin/total differs from immutable V03 grade")
        truth=grade["actual_margin"]
        if type(truth) not in (int,float) or not math.isfinite(truth):
            raise ValueError("Non-finite final")
        available={}
        for name in MODELS:
            variant=row["models"][name]
            if variant["status"]!="SHADOW_FROZEN_RESEARCH":
                continue
            m=variant["predicted_home_margin"]
            available[name]={"model_version":VERSIONS[name],
                "predicted_margin":m,
                "margin_abs_error":round(abs(m-truth),5),
                "signed_error":round(m-truth,5),
                "su_correct":int((m>0)==(truth>0)) if m!=0 and truth!=0 else None}
        per_game.append({"game_id":str(grade["game_id"]),"home":grade["home"],
            "away":grade["away"],"kickoff_utc":grade["kickoff_utc"],
            "shadow_run_id":run,
            "shadow_observed_utc":frozen["shadow_observed_utc"],
            "selected_v03_grade_sha256":sha256(grade),
            "reference_grade_policy":grade["observation_policy"],
            "actual_margin":truth,"models":available})
    metrics={}
    for name in MODELS:
        matched=[r for r in per_game if name in r["models"]]
        if not matched:
            metrics[name]={"status":"INSUFFICIENT_FROZEN_PROSPECTIVE_GAMES","games":0}
            continue
        errors=[r["models"][name]["margin_abs_error"] for r in matched]
        baselines=[r["models"]["active_v03"]["margin_abs_error"] for r in matched]
        signed=[r["models"][name]["signed_error"] for r in matched]
        correct=[r["models"][name]["su_correct"] for r in matched
                 if r["models"][name]["su_correct"] is not None]
        metrics[name]={
            "status":"EARLY_PROSPECTIVE_RESEARCH_NOT_PROMOTABLE",
            "model_version":VERSIONS[name],
            "games":len(matched),
            "margin_mae":round(sum(errors)/len(errors),5),
            "paired_v03_margin_mae":round(sum(baselines)/len(baselines),5),
            "paired_delta_margin_mae_vs_v03":round(
                (sum(errors)-sum(baselines))/len(errors),5),
            "signed_home_margin_error":round(sum(signed)/len(signed),5),
            "winner_accuracy":round(sum(correct)/len(correct),5) if correct else None,
            "non_tie_game_count":len(correct)}
    complete=sum(all(k in r["models"] for k in MODELS) for r in per_game)
    return {"status":STATUS,"season":2026,
        "evaluated_at_utc":now.isoformat(),
        "reference_policy":"SAME_SELECTED_IMMUTABLE_24_TO_72_HOUR_STEP3G_GRADE",
        "model_versions":VERSIONS,
        "report_summary":{"selected_real_grades_considered":len(grades),
                          "shadow_linked_eligible_games":len(per_game),
                          "four_way_matched_games":complete,
                          "unmatched_reasons":dict(reasons)},
        "metrics":metrics,"per_game":per_game,
        "market_ats_ou_grades_available":False,
        "historical_pbp_publication_verified":False,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

def read_evidence():
    raw=store.get_blob_file(SHADOW_INDEX)
    index=json.loads(raw) if raw else {
        "status":SHADOW_STATUS,"season":2026,"runs":[],"betting_status":"PASS_UNVALIDATED"}
    if (index.get("status")!=SHADOW_STATUS or index.get("season")!=2026
        or index.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Wrong shadow run index")
    shadows=[]
    for entry in index["runs"]:
        path=entry["path"]
        run=str(entry["run_id"])
        if (not run.isdecimal() or not path.startswith(ROOT+"/shadow_forecasts/2026/")
            or ".." in Path(path).parts or not path.endswith("/run-"+run+".json.gz")):
            raise ValueError("Unsafe shadow archive path")
        raw=store.get_blob_file(path)
        if raw is None:raise ValueError("Missing archived shadow bytes")
        record=store.unpack(raw)
        verify_shadow(record)
        if (str(record["run_id"])!=run or checksum(record)!=entry["sha256"] or
            len(record["games"])!=entry["games"] or
            record["baseline_forecast_sha256"]!=entry["baseline_forecast_sha256"]):
            raise ValueError("Tampered shadow index")
        shadows.append(record)
    raw=store.get_blob_file(BASE_GRADE_INDEX)
    base=json.loads(raw) if raw else empty_grade_index()
    grade_records={}
    for gid,entry in base["games"].items():
        path=entry["path"]
        if (not path.startswith(ROOT+"/forecast_grades/2026/") or
            ".." in Path(path).parts or not path.endswith("/"+str(gid)+".json.gz")):
            raise ValueError("Unsafe graded source path")
        blob=store.get_blob_file(path)
        if blob is None:raise ValueError("Missing original verified grade")
        grade_records[path]=store.unpack(blob)
    verify_prior_grade(base,grade_records)
    return shadows,list(grade_records.values())

def run(output):
    shadows,grades=read_evidence()
    record=evaluate(shadows,grades,dt.datetime.now(dt.timezone.utc).isoformat())
    # Store one immutable report per run; all prior reports remain accessible.
    runid=str(os.environ.get("GITHUB_RUN_ID",""))
    if not runid.isdecimal():raise ValueError("Expected authenticated GitHub run")
    path=ROOT+"/shadow_grade_reports/"+at(record["evaluated_at_utc"]).strftime("%Y/%m/%d")+"/run-"+runid+".json.gz"
    old=store.get_blob_file(INDEX)
    idx=json.loads(old) if old else {"status":STATUS,"season":2026,"runs":[]}
    if idx.get("status")!=STATUS or idx.get("season")!=2026:
        raise ValueError("Invalid shadow grade index")
    if any(str(x["run_id"])==runid for x in idx["runs"]):
        raise ValueError("Shadow grade run already archived")
    idx["runs"].append({"run_id":runid,"path":path,"sha256":sha256(record),
                        "graded_games":record["report_summary"]["shadow_linked_eligible_games"]})
    _commit_material({path:store.pack(record),INDEX:store.encode(idx)},runid)
    dest=Path(output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf-8") as stream:
        json.dump(record,stream,indent=2,allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status":STATUS,"summary":record["report_summary"],
        "metrics":record["metrics"],"model_promoted":False}))
    return record

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    run(p.parse_args().output)

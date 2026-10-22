"""Step 3G.1: score real frozen prospective research forecasts after observed finals.

Never retroactively invent pregame predictions, scoreboard release times, money
lines or sportsbook odds. Forecasts remain immutable; grading lives separately.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
from collections import Counter
from pathlib import Path

from scripts import context_archive as store
from scripts.game_context import parse_time
from scripts.personnel_forecast import (
    INDEX as FORECAST_INDEX, STATUS as FORECAST_STATUS, verify as verify_forecast,
    checksum as forecast_hash)
from scripts.personnel_results_archive import (
    ROOT, INDEX as PREGAME_INDEX, OUTCOMES, _valid_index, _commit_material)
from scripts.personnel_features import sha256
from scripts.personnel_archive_dataset import _check_label, _check_pregame_bundle, safe_path

STATUS = "STEP3G_OBSERVED_PROSPECTIVE_GRADING_RESEARCH_ONLY"
INDEX = ROOT + "/forecast_grades_index.json"
FORECAST_PATH = re.compile(
    r"^research_2026/forecasts/(?:2026/\d{2}|2027/01)/\d{2}/run-\d+\.json\.gz$")
GRADE_PATH = re.compile(
    r"^research_2026/forecast_grades/(?:2026/\d{2}|2027/01)/\d{2}/\d+\.json\.gz$")
POLICY = "LATEST_ACTUALLY_OBSERVED_FORECAST_24_TO_72_HOURS_BEFORE_KICKOFF"


def at(iso):
    return parse_time(iso)


def empty_grade_index():
    return {"status": STATUS, "season": 2026, "games": {},
            "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"}


def _index(index):
    if (not isinstance(index,dict) or index.get("status")!=STATUS or
        index.get("season")!=2026 or
        index.get("safe_for_betting") is not False or
        index.get("betting_status")!="PASS_UNVALIDATED" or
        not isinstance(index.get("games"),dict)):
        raise ValueError("Invalid existing prospective grade index")


def _forecast_index(index):
    if (not isinstance(index,dict) or index.get("status")!=FORECAST_STATUS or
        index.get("season")!=2026 or index.get("safe_for_betting") is not False or
        index.get("betting_status")!="PASS_UNVALIDATED" or
        not isinstance(index.get("runs"),list)):
        raise ValueError("Untrusted forecast index")
    seen=set()
    allpaths=set()
    for entry in index["runs"]:
        if not isinstance(entry,dict):
            raise ValueError("Malformed forecast index entry")
        path=entry["path"]
        if not isinstance(path,str) or not FORECAST_PATH.fullmatch(path):
            raise ValueError("Invalid forecast path")
        runid=str(entry["run_id"])
        if not runid.isdecimal() or runid in seen or path in allpaths:
            raise ValueError("Duplicate or invalid forecast archive run")
        seen.add(runid);allpaths.add(path)
        when=at(entry["forecast_observed_utc"])
        if path!=ROOT+"/forecasts/"+when.strftime("%Y/%m/%d")+"/run-"+runid+".json.gz":
            raise ValueError("Forecast index path conflicts with observed timestamp")


def _all_forecasts(forecast_index, forecasts, cutoff):
    """Validate every referenced file; preserve every non-mutated research row."""
    _forecast_index(forecast_index)
    allpaths={item["path"] for item in forecast_index["runs"]}
    if set(forecasts)!=allpaths:
        raise ValueError("Missing/unindexed frozen forecast files")
    result={}
    for entry in forecast_index["runs"]:
        bundle=forecasts[entry["path"]]
        verify_forecast(bundle)
        if (forecast_hash(bundle)!=entry["forecast_sha256"] or
            str(bundle["run_id"])!=str(entry["run_id"]) or
            at(bundle["forecast_observed_utc"])!=at(entry["forecast_observed_utc"]) or
            len(bundle["games"])!=entry["pregame_games"] or
            sum(row["policy_24_to_72h_eligible"] for row in bundle["games"])!=
            entry["eligible_24_to_72h_games"] or entry.get("actual_market_quotes")!=0):
            raise ValueError("Altered forecast index/source digest")
        observed=at(bundle["forecast_observed_utc"])
        for row in bundle["games"]:
            gid=str(row["game_id"])
            key=(str(bundle["run_id"]),gid)
            if key in result:
                raise ValueError("Repeated game within one immutable run")
            if observed>cutoff:
                continue
            result[key]=(bundle,row,entry)
    return result


def _matching_pregame(bundle,row,pregame_index):
    gid=str(row["game_id"])
    runid=str(bundle["run_id"])
    expected_path=(ROOT+"/pregame/"+at(bundle["source_profile_capture_utc"]).strftime("%Y/%m/%d")
                   +"/run-"+runid+".json.gz")
    matches=[r for r in pregame_index["games"].get(gid,[]) if r["path"]==expected_path]
    if len(matches)!=1:
        raise ValueError("Forecast has no matching previously archived pregame observation")
    meta=matches[0]
    if (meta["home"]!=row["home"] or meta["away"]!=row["away"] or
        at(meta["kickoff_utc"])!=at(row["kickoff_utc"]) or
        at(meta["captured_at_utc"])!=at(bundle["source_profile_capture_utc"]) or
        meta["profile_sha256"]!=row["personnel_profile_sha256"] or
        meta["personnel_record_sha256"]!=row["feature_sha256"]):
        raise ValueError("Frozen forecast disagrees with independent pregame archive")
    return meta


def choose_for_final(gid,final,source_records,pregame_index):
    """Latest forecast *within* 24-72h before kickoff, never latest in hindsight."""
    candidates=[]
    kickoff=at(final["kickoff_utc"])
    for (_,ref), (bundle,row,entry) in source_records.items():
        if ref!=str(gid):
            continue
        _matching_pregame(bundle,row,pregame_index)
        if ((row["home"],row["away"],at(row["kickoff_utc"])) !=
            (final["home"],final["away"],kickoff)):
            continue  # reschedules or changed official opponents cannot be used
        observed=at(row["forecast_observed_utc"])
        hours=(kickoff-observed).total_seconds()/3600
        if 24<=hours<=72 and observed<kickoff and row["policy_24_to_72h_eligible"]:
            candidates.append((observed,bundle,row,entry))
    if not candidates:return None
    candidates.sort(key=lambda r:r[0])
    if len(candidates)>=2 and candidates[-2][0]==candidates[-1][0]:
        raise ValueError("Ambiguous simultaneous prospective forecasts")
    _,bundle,row,entry=candidates[-1]
    return bundle,row,entry


def grade(index,outcome_index,pregame_index,forecast_index,forecasts,outcome_records,
          asof_utc):
    """Pure grading plan. No commit, outcome modification, or network access."""
    now=at(asof_utc)
    _index(index)
    _valid_index(outcome_index,"outcome")
    _valid_index(pregame_index,"pregame")
    sources=_all_forecasts(forecast_index,forecasts,now)
    fresh=json.loads(json.dumps(index))
    created=[]
    reasons=Counter()
    for gid,summary in sorted(outcome_index["games"].items()):
        p=summary["archive_path"]
        safe_path(p,False)
        if p not in outcome_records:
            raise ValueError("Missing final-score original evidence")
        final=outcome_records[p]
        # Verified against separate immutable evidence; no score-only shortcuts.
        eligible_label=_check_label(p,final,summary,summary["selected_pregame"],now)
        if gid!=str(final["game_id"]):
            raise ValueError("Final source game ID disagrees with outcome index")
        for k in ("game_id","home","away","home_score","away_score"):
            if str(summary[k])!=str(final[k]):
                raise ValueError("Tampered final index metadata")
        if at(summary["kickoff_utc"])!=at(final["kickoff_utc"]):
            raise ValueError("Tampered final kickoff metadata")
        if not eligible_label or at(final["observed_at_utc"])>now:
            reasons["label_not_observed_yet"]+=1
            continue
        pick=choose_for_final(gid,final,sources,pregame_index)
        if pick is None:
            reasons["no_eligible_frozen_forecast"]+=1
            continue
        bundle,row,ref=pick
        proj=row["projection"]
        if proj["prediction_status"]!="UNVALIDATED_RESEARCH_PROJECTION":
            reasons["forecast_was_pass"]+=1
            continue
        pred_margin=proj["predicted_home_margin"]
        pred_total=proj["predicted_total_points"]
        actual_margin=final["actual_margin"]
        actual_total=final["actual_total"]
        if any(type(x) not in (int,float) or not math.isfinite(x) for x in
               (pred_margin,pred_total,actual_margin,actual_total)):
            raise ValueError("Unscorable nonfinite forecast/final")
        win=proj["research_home_win_probability"]
        if type(win) not in (int,float) or not 0<=win<=1:
            raise ValueError("Invalid uncalibrated research win probability")
        home_won=actual_margin>0
        su_grade=(int((pred_margin>0)==home_won)
                  if pred_margin!=0 and actual_margin!=0 else None)
        brier=((win-int(home_won))**2 if actual_margin!=0 else None)
        lead=(at(final["kickoff_utc"])-at(row["forecast_observed_utc"])).total_seconds()/3600
        frozen_hash=row["row_sha256"]
        grade_record={
            "status":"OBSERVED_FORECAST_GRADED_RESEARCH_ONLY",
            "season":2026,"game_id":str(gid),
            "home":final["home"],"away":final["away"],
            "kickoff_utc":final["kickoff_utc"],
            "observation_policy":POLICY,
            "forecast_run_id":str(bundle["run_id"]),
            "forecast_archive_path":ref["path"],
            "forecast_bundle_sha256":ref["forecast_sha256"],
            "frozen_forecast_row_sha256":frozen_hash,
            "forecast_observed_utc":row["forecast_observed_utc"],
            "forecast_lead_hours":round(lead,4),
            "forecast_model":bundle["model_training"]["model"],
            "final_archive_path":p,
            "final_source_record_sha256":summary["record_sha256"],
            "final_observed_at_utc":final["observed_at_utc"],
            "final_outcome_known_at_utc":final["outcome_known_at_utc"],
            "predicted_margin":pred_margin,
            "predicted_total":pred_total,
            "uncalibrated_win_probability":win,
            "actual_home_score":final["home_score"],
            "actual_away_score":final["away_score"],
            "actual_margin":actual_margin,
            "actual_total":actual_total,
            "su_correct":su_grade,
            "margin_abs_error":round(abs(pred_margin-actual_margin),5),
            "total_abs_error":round(abs(pred_total-actual_total),5),
            "uncalibrated_brier_diagnostic":round(brier,6) if brier is not None else None,
            "ats_grade":None,"over_under_grade":None,
            "market_status":"NOT_OBSERVED_PRIVATE_OPT_IN_ONLY",
            "safe_for_betting":False,"model_validated":False,
            "betting_status":"PASS_UNVALIDATED"}
        grade_path=(ROOT+"/forecast_grades/"+at(final["kickoff_utc"]).strftime("%Y/%m/%d")
                    +"/"+str(gid)+".json.gz")
        prior=fresh["games"].get(str(gid))
        if prior:
            if prior["grade_sha256"]!=sha256(grade_record) or prior["path"]!=grade_path:
                # Never silently revise which frozen forecast/label won after publication.
                reasons["frozen_grade_conflict_requires_review"]+=1
            else:
                reasons["already_graded"]+=1
            continue
        fresh["games"][str(gid)]={
            "path":grade_path,"grade_sha256":sha256(grade_record),
            "forecast_run_id":str(bundle["run_id"]),
            "forecast_row_sha256":frozen_hash,
            "final_record_sha256":summary["record_sha256"],
            "betting_status":"PASS_UNVALIDATED"}
        created.append((grade_path,grade_record))
    if set(outcome_records)!={r["archive_path"] for r in outcome_index["games"].values()}:
        raise ValueError("Extra unindexed final-score evidence")
    if set(index["games"])-set(outcome_index["games"]):
        raise ValueError("Existing graded game lost its original final label")
    for gid,entry in index["games"].items():
        path=entry["path"]
        if (not isinstance(path,str) or not GRADE_PATH.fullmatch(path) or
            path.split("/")[-1]!=str(gid)+".json.gz"):
            raise ValueError("Corrupt archived grade filename")
    return fresh,created,{
        "status":STATUS,
        "evaluation_asof_utc":now.isoformat(),
        "forecast_runs_available":len(forecast_index["runs"]),
        "indexed_final_games":len(outcome_index["games"]),
        "total_frozen_graded_games":len(fresh["games"]),
        "newly_graded_games":len(created),
        "outstanding":dict(reasons),
        "grade_policy":POLICY,
        "ats_ou_results_available":False,
        "model_validated":False,"model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}


def verify_prior_grade(index, stored):
    """Authenticate retained grade contents against immutable archive metadata."""
    _index(index)
    if set(stored)!={entry["path"] for entry in index["games"].values()}:
        raise ValueError("Prior grading archive missing or contains extra records")
    for gid,entry in index["games"].items():
        path=entry["path"]
        if not GRADE_PATH.fullmatch(path) or not path.endswith("/"+str(gid)+".json.gz"):
            raise ValueError("Invalid archived grading path")
        result=stored[path]
        if (result.get("status")!="OBSERVED_FORECAST_GRADED_RESEARCH_ONLY" or
            result.get("safe_for_betting") is not False or
            result.get("model_validated") is not False or
            result.get("betting_status")!="PASS_UNVALIDATED" or
            str(result.get("game_id"))!=str(gid) or
            sha256(result)!=entry["grade_sha256"] or
            result.get("frozen_forecast_row_sha256")!=entry["forecast_row_sha256"] or
            result.get("final_source_record_sha256")!=entry["final_record_sha256"] or
            str(result.get("forecast_run_id"))!=str(entry["forecast_run_id"]) or
            result.get("ats_grade") is not None or
            result.get("over_under_grade") is not None):
            raise ValueError("Prior prospective grade integrity mismatch")
        if not at(result["forecast_observed_utc"])<at(result["kickoff_utc"])<at(
            result["final_outcome_known_at_utc"]):
            raise ValueError("Impossible historical grading chronology")
    return True


def read():
    src=store.get_blob_file(FORECAST_INDEX)
    if src is None:
        raise ValueError("Step 3G forecast archive is not initialized")
    forecast_index=json.loads(src)
    _forecast_index(forecast_index)
    f={}
    for entry in forecast_index["runs"]:
        blob=store.get_blob_file(entry["path"])
        if blob is None:
            raise ValueError("Missing source forecast bytes")
        f[entry["path"]]=store.unpack(blob)
    pre=store.get_blob_file(PREGAME_INDEX)
    out=store.get_blob_file(OUTCOMES)
    if pre is None or out is None:
        raise ValueError("Expected Step 3D archive indexes")
    pre=json.loads(pre);out=json.loads(out)
    _valid_index(pre,"pregame")
    _valid_index(out,"outcome")
    # Before grading on the live branch, reauthenticate each original frozen
    # pregame bundle against its independent SHA/provenance checks.
    all_pregame_paths={meta["path"]
                       for rows in pre["games"].values() for meta in rows}
    for path in sorted(all_pregame_paths):
        safe_path(path,True)
        blob=store.get_blob_file(path)
        if blob is None:
            raise ValueError("Missing independent original pregame bundle")
        _check_pregame_bundle(path,store.unpack(blob))
    finals={}
    for gid,row in out["games"].items():
        path=row["archive_path"]
        safe_path(path,False)
        blob=store.get_blob_file(path)
        if blob is None:
            raise ValueError("Missing archived result bytes")
        finals[path]=store.unpack(blob)
    grades=store.get_blob_file(INDEX)
    index=json.loads(grades) if grades else empty_grade_index()
    _index(index)
    prior={}
    for gid,entry in index["games"].items():
        path=entry["path"]
        if not isinstance(path,str) or not GRADE_PATH.fullmatch(path):
            raise ValueError("Unsafe previously archived grading path")
        blob=store.get_blob_file(path)
        if blob is None:
            raise ValueError("Missing previously graded immutable bytes")
        prior[path]=store.unpack(blob)
    verify_prior_grade(index,prior)
    return index,out,pre,forecast_index,f,finals,prior


def run(output):
    index,out,pre,forecast_index,f,finals,prior=read()
    index,created,report=grade(index,out,pre,forecast_index,f,finals,
            dt.datetime.now(dt.timezone.utc).isoformat())
    # Prior files were verified against their individual SHA-256 signatures on
    # read; newly generated grades are separately immutable on the branch.
    # Only append new immutable grade records; index itself is mutable.
    if created:
        material={INDEX:store.encode(index)}
        for path,item in created:
            material[path]=store.pack(item)
        report["git_commit_sha"]=_commit_material(material,str(os.environ.get("GITHUB_RUN_ID","")))
    else:
        report["no_new_grade_write"]=True
    dest=Path(output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf-8") as fp:
        json.dump(report,fp,indent=2,allow_nan=False)
        fp.write("\n")
    print(json.dumps(report))
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    args=p.parse_args()
    run(args.output)

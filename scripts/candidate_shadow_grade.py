"""Prospective grading of immutable QB and venue/travel candidate shadows.

Matches selected original V03 scores by run, exact game and row SHA.
Only 24-72h pregame captures count. Never retrofits later QB information.
"""
import argparse,datetime as dt,json,math,os
from pathlib import Path
from scripts import context_archive as store
from scripts.candidate_shadow_archive import validate as verify_candidate,VERSIONS
from scripts.model_shadow_grade import read_evidence as read_baselines
from scripts.personnel_results_archive import ROOT,_commit_material
from scripts.personnel_features import sha256
from scripts.game_context import parse_time

STATUS="QB_VENUE_TRAVEL_PROSPECTIVE_PAIRED_GRADE_RESEARCH_ONLY"
def evaluate(candidates,grades,asof):
    now=parse_time(asof)
    catalog={}
    for kind,records in candidates.items():
        for rec in records:
            run,observed=verify_candidate(rec,kind)
            if observed>now:raise ValueError("Future-side candidate grading")
            key=(run,kind)
            if key in catalog:raise ValueError("Duplicate frozen candidate run")
            catalog[key]=rec
    paired=[];reason={}
    def reject(why):reason[why]=reason.get(why,0)+1
    for grade in grades:
        if (grade.get("status")!="OBSERVED_FORECAST_GRADED_RESEARCH_ONLY" or
            grade.get("betting_status")!="PASS_UNVALIDATED"
            or grade.get("model_validated") is not False
            or grade.get("safe_for_betting") is not False):
            raise ValueError("Untrusted actual game grade")
        run=str(grade["forecast_run_id"])
        items={}
        for kind in VERSIONS:
            data=catalog.get((run,kind))
            if data is None:
                reject("NO_"+kind.upper()+"_SNAPSHOT_FOR_SELECTED_BASELINE")
                continue
            if data["baseline_forecast_sha256"]!=grade["forecast_bundle_sha256"]:
                raise ValueError("Wrong original V03 forecast bundle")
            matching=[r for r in data["games"]
                      if str(r["game_id"])==str(grade["game_id"])]
            if not matching:
                reject("SELECTED_GAME_MISSING_"+kind.upper());continue
            if len(matching)!=1:raise ValueError("Duplicate game within candidate")
            g=matching[0]
            if (g["baseline_row_sha256"]!=grade["frozen_forecast_row_sha256"]
                or (g["home"],g["away"],parse_time(g["kickoff_utc"]))!=(
                    grade["home"],grade["away"],parse_time(grade["kickoff_utc"]))):
                raise ValueError("Candidate game source identity mismatch")
            kickoff=parse_time(g["kickoff_utc"])
            issued=parse_time(data["observed_at_utc"])
            observed_outcome=parse_time(grade["final_outcome_known_at_utc"])
            if not issued<kickoff<observed_outcome<=now:
                raise ValueError("Candidate/outcome chronology invalid")
            hours=(kickoff-issued).total_seconds()/3600
            if not 24<=hours<=72:
                reject("OUTSIDE_24_TO_72H_"+kind.upper());continue
            if kind=="qb":
                c=g["candidate"]
                value=c.get("adjusted_home_margin") if c["status"]=="QB_PLAYER_CONDITIONAL_SHADOW" else None
                if value is not None:
                    items["qb_conditional"]={"prediction":float(value),
                        "covered_sides":c["adjusted_side_count"]}
                # Independently prospectively grade the exposure mixture
                # against exactly the same frozen baseline and actual final.
                if c.get("usage_weighted_status")=="QB_EMPIRICAL_EXPOSURE_SHADOW":
                    w=c.get("usage_weighted_home_margin")
                    exposure=c.get("evaluated_player_sample_exposure_by_side",{})
                    if (type(w) not in (int,float) or
                        any(type(exposure.get(side)) not in (int,float)
                            or not 0<=exposure[side]<=1 for side in ("home","away"))):
                        raise ValueError("Invalid prospective QB exposure candidate")
                    items["qb_empirical_exposure"]={"prediction":float(w),
                        "sample_coverage_home":exposure["home"],
                        "sample_coverage_away":exposure["away"]}
                if c.get("opponent_peer_status")=="QB_OPPONENT_PEER_EPA_SHADOW":
                    value=c.get("opponent_peer_home_margin")
                    sides=c.get("opponent_peer_qualified_sides")
                    if (type(value) not in (int,float) or not math.isfinite(value)
                        or type(sides) is not int or not 1<=sides<=2):
                        raise ValueError("Invalid archived opponent peer QB candidate")
                    items["qb_defense_peer"]={"prediction":float(value),
                        "covered_sides":sides}
                if c.get("opponent_peer_exposure_status")=="QB_OPPONENT_PEER_EXPOSURE_SHADOW":
                    value=c.get("opponent_peer_exposure_home_margin")
                    covered=c.get("opponent_peer_exposure_sample_by_side")
                    if (type(value) not in (int,float) or not math.isfinite(value)
                        or not isinstance(covered,dict) or
                        any(type(covered.get(side)) not in (int,float)
                            or not 0<=covered[side]<=1 for side in ("home","away"))
                        or not any(covered[side]>0 for side in ("home","away"))):
                        raise ValueError("Invalid archived opponent QB exposure")
                    items["qb_defense_peer_exposure"]={"prediction":float(value),
                        "sample_coverage_home":covered["home"],
                        "sample_coverage_away":covered["away"]}
            else:
                for name,field in (("venue_only","venue_only_margin"),
                                   ("venue_plus_travel","venue_plus_travel_margin")):
                    value=g.get(field)
                    if value is not None:
                        items[name]={"prediction":float(value)}
        if not items:continue
        actual=float(grade["actual_margin"]);baseline=float(grade["predicted_margin"])
        rows={}
        for kind,entry in items.items():
            value=entry["prediction"]
            if not math.isfinite(value) or abs(value)>55:
                raise ValueError("Invalid research margin")
            rows[kind]={**entry,"abs_error":round(abs(value-actual),5),
                "signed_home_error":round(value-actual,5),
                "winner_correct":int((value>0)==(actual>0)) if actual and value else None}
        paired.append({"game_id":str(grade["game_id"]),"run_id":run,
            "home":grade["home"],"away":grade["away"],
            "actual_home_margin":actual,"baseline_v03_margin":baseline,
            "baseline_v03_abs_error":round(abs(baseline-actual),5),
            "model_results":rows})
    metrics={}
    for name in ("qb_conditional","qb_empirical_exposure","qb_defense_peer",
                 "qb_defense_peer_exposure","venue_only","venue_plus_travel"):
        rows=[r for r in paired if name in r["model_results"]]
        if not rows:
            metrics[name]={"status":"INSUFFICIENT_PROSPECTIVE_GRADED_GAMES","games":0}
            continue
        n=len(rows)
        metrics[name]={"status":"EARLY_PROSPECTIVE_RESEARCH_NOT_PROMOTABLE","games":n,
            "margin_mae":round(sum(r["model_results"][name]["abs_error"] for r in rows)/n,5),
            "same_game_baseline_v03_mae":round(sum(r["baseline_v03_abs_error"] for r in rows)/n,5),
            "signed_home_margin_error":round(sum(r["model_results"][name]["signed_home_error"]
                                                for r in rows)/n,5),
            "win_accuracy":round(sum(r["model_results"][name]["winner_correct"] for r in rows
                                   if r["model_results"][name]["winner_correct"] is not None)/
                          max(1,sum(r["model_results"][name]["winner_correct"] is not None for r in rows)),5)}
    return {"status":STATUS,"evaluated_at_utc":now.isoformat(),"season":2026,
        "reference_policy":"EXACT_SELECTED_ARCHIVED_V03_24_TO_72H_PREKICKOFF",
        "per_game":paired,"summary":{"graded_games":len(paired),"reasons_not_graded":reason},
        "metrics":metrics,"model_promoted":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

def read_candidates():
    result={}
    for kind,status in VERSIONS.items():
        path=ROOT+"/candidate_shadow_"+kind+"/index.json"
        raw=store.get_blob_file(path)
        idx=json.loads(raw) if raw else {"status":status,"season":2026,"runs":[]}
        if idx.get("status")!=status or idx.get("season")!=2026:
            raise ValueError("Untrusted historical candidate index")
        data=[]
        for entry in idx["runs"]:
            run=str(entry["run_id"]);loc=entry["path"]
            if (not run.isdigit() or ".." in Path(loc).parts or
                not loc.startswith(ROOT+"/candidate_shadow_"+kind+"/2026/") or
                not loc.endswith("/run-"+run+".json.gz")):
                raise ValueError("Invalid candidate immutable archive path")
            payload=store.get_blob_file(loc)
            if payload is None:raise ValueError("Missing candidate archive")
            rec=store.unpack(payload)
            verify_candidate(rec,kind)
            if entry["sha256"]!=sha256(rec) or len(rec["games"])!=entry["games"]:
                raise ValueError("Candidate archive SHA mismatch")
            data.append(rec)
        result[kind]=data
    return result

def run(output):
    saved=read_candidates()
    _,grades=read_baselines()
    result=evaluate(saved,grades,dt.datetime.now(dt.timezone.utc).isoformat())
    runid=os.environ.get("GITHUB_RUN_ID","")
    if not runid.isdigit():raise ValueError("No GitHub run for archived grade")
    destination=ROOT+"/candidate_shadow_grades/2026/"+runid+".json.gz"
    indexpath=ROOT+"/candidate_shadow_grades/index.json"
    prev=store.get_blob_file(indexpath)
    idx=json.loads(prev) if prev else {"status":STATUS,"season":2026,"runs":[]}
    if any(x["run_id"]==runid for x in idx["runs"]):
        raise ValueError("Prospective score report cannot be overwritten")
    idx["runs"].append({"run_id":runid,"path":destination,"sha256":sha256(result),
                        "games":result["summary"]["graded_games"]})
    _commit_material({destination:store.pack(result),indexpath:store.encode(idx)},runid)
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("x") as f:json.dump(result,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({"status":STATUS,**result["summary"],
                      "metrics":result["metrics"],"model_promoted":False}))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    run(p.parse_args().output)

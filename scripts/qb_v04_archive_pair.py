"""Audit predecisional V04 website snapshots against frozen QB research grades.

V04 is NOT reconstructed from a subsequently updated team profile. Only a
source-hashed website score actually archived BEFORE the chosen QB shadow
capture, within six hours and in the identical pre-kickoff 24–72h cohort,
may be used as the V04 control. Missing pairs stay missing; model promotion
remains prohibited and earlier V03 forecasts remain untouched.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import context_archive as store
from scripts.candidate_shadow_archive import validate as verify_candidate
from scripts.candidate_shadow_grade import STATUS as GRADE_STATUS
from scripts.game_context import parse_time
from scripts.site_decision_archive import INDEX as SITE_INDEX, STATUS as SITE_STATUS
from scripts.v04_direct_scores import MODEL as V04_MODEL,STATUS as V04_STATUS
from scripts.qb_v04_same_intake import STATUS as SAME_INTAKE_STATUS

STATUS="QB_SHADOW_EARLIER_WEBSITE_V04_PAIRED_AUDIT_RESEARCH_ONLY"
MAX_CAPTURE_LAG_HOURS=6


def read_site_snapshots(qb_shadows, read_blob=None):
    """Read only nearby actual archived captures, SHA-check every used blob."""
    read_blob=read_blob or store.get_blob_file
    issued=[]
    for rec in qb_shadows:
        _,clock=verify_candidate(rec,"qb")
        issued.append(clock)
    if not issued:
        return []
    raw=read_blob(SITE_INDEX)
    if raw is None:return []
    index=json.loads(raw)
    if (index.get("status")!=SITE_STATUS or index.get("schema_version")!=1 or
        not isinstance(index.get("runs"),list)):
        raise ValueError("Corrupt source-hashed V04 snapshot index")
    seen=set()
    snapshots=[]
    for entry in index["runs"]:
        run=str(entry.get("run_id",""))
        cap=parse_time(entry["capture_utc"])
        if not run.isdecimal() or run in seen:
            raise ValueError("Duplicate/invalid V04 website archive run")
        seen.add(run)
        if not any(dt.timedelta(0)<=t-cap<=dt.timedelta(hours=MAX_CAPTURE_LAG_HOURS)
                   for t in issued):
            continue
        loc=entry.get("path","")
        if (not loc.startswith("research_2026/site_board_snapshots/2026/") or
            ".." in Path(loc).parts or
            not loc.endswith("/run-"+run+".json.gz") or
            not isinstance(entry.get("sha256"),str) or len(entry["sha256"])!=64):
            raise ValueError("Unsafe V04 website archive path")
        payload=read_blob(loc)
        if payload is None:
            raise ValueError("Missing selected V04 site archive")
        snapshot=store.unpack(payload)
        digest=hashlib.sha256(store.encode(snapshot)).hexdigest()
        if (digest!=entry["sha256"] or snapshot.get("status")!=SITE_STATUS or
            snapshot.get("schema_version")!=1 or
            str(snapshot.get("dashboard_run_id"))!=run or
            parse_time(snapshot.get("capture_utc"))!=cap or
            not isinstance(snapshot.get("rows"),list)):
            raise ValueError("Tampered/invalid V04 site snapshot source hash")
        if (parse_time(snapshot["model_forecast_observed_utc"])>cap or
            not isinstance(snapshot.get("model_forecast_sha256"),str) or
            len(snapshot["model_forecast_sha256"])!=64):
            raise ValueError("V04 archive originally observed after capture")
        ids=[str(x["game_id"]) for x in snapshot["rows"]]
        if len(set(ids))!=len(ids):
            raise ValueError("Duplicated V04 snapshot game")
        snapshots.append({"snapshot":snapshot,
                          "source_snapshot_sha256":digest,
                          "source_snapshot_run_id":run})
    return snapshots


def enrich(grade,qb_shadows,source_snapshots):
    """Append a separately time-verified same-game control to each QB grade."""
    if (grade.get("status")!=GRADE_STATUS or grade.get("model_promoted") is not False
        or grade.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Unexpected candidate score grade for V04 comparison")
    byrun={}
    for rec in qb_shadows:
        run,clock=verify_candidate(rec,"qb")
        if run in byrun:raise ValueError("Duplicate immutable QB shadow run")
        ids={str(row["game_id"]):row for row in rec["games"]}
        if len(ids)!=len(rec["games"]):raise ValueError("Duplicate QB game")
        byrun[run]=(rec,clock,ids)
    site=[]
    hashes=set()
    for entry in source_snapshots:
        snapshot=entry["snapshot"]
        h=hashlib.sha256(store.encode(snapshot)).hexdigest()
        run=str(entry.get("source_snapshot_run_id",""))
        if (h!=entry.get("source_snapshot_sha256") or
            snapshot.get("status")!=SITE_STATUS or
            snapshot.get("schema_version")!=1 or
            str(snapshot.get("dashboard_run_id"))!=run or
            snapshot.get("betting_status")!="PASS_UNVALIDATED" or
            run in hashes):
            raise ValueError("V04 snapshot source hash/identity missing")
        hashes.add(run)
        capture=parse_time(snapshot["capture_utc"])
        model_stamp=parse_time(snapshot["model_forecast_observed_utc"])
        if model_stamp>capture or not isinstance(snapshot.get("rows"),list):
            raise ValueError("V04 snapshot after model capture")
        ids={str(row["game_id"]):row for row in snapshot["rows"]}
        if len(ids)!=len(snapshot["rows"]):
            raise ValueError("Duplicate V04 game in site archive")
        site.append((capture,run,h,ids))
    result=copy.deepcopy(grade)
    total=0;matched=0;candidate_error=0.;v04_error=0.
    paired_dates=set()
    same_intake_dates=set()
    same_intake_eligible=0
    same_intake_paired=0
    same_intake_v04_err=0.
    same_intake_qb_err=0.
    same_intake_v03_err=0.
    no_pair={}
    for row in result.get("per_game",[]):
        if "qb_conditional" not in row["model_results"]:
            continue
        total+=1
        run=str(row["run_id"])
        gid=str(row["game_id"])
        if run not in byrun or gid not in byrun[run][2]:
            raise ValueError("V04 audit lacked original matched QB shadow")
        shadow,decision,shadow_rows=byrun[run]
        original=shadow_rows[gid]
        kick=parse_time(original["kickoff_utc"])
        if (row["home"],row["away"])!=(original["home"],original["away"]):
            raise ValueError("V04 candidate game identity mismatch")
        if not 24 <= (kick-decision).total_seconds()/3600 <= 72:
            raise ValueError("QB sample outside original research horizon")
        qb_value=original["candidate"].get("adjusted_home_margin")
        if (original["candidate"].get("status")!="QB_PLAYER_CONDITIONAL_SHADOW"
            or type(qb_value) not in (int,float) or not math.isfinite(qb_value)
            or abs(float(qb_value)-float(row["model_results"]["qb_conditional"]["prediction"]))>1e-5):
            raise ValueError("QB research prediction not frozen on cited run")
        choices=[]
        contemporaneous=original.get("same_intake_v04")
        row["v04_same_intake_instrumented"]=contemporaneous is not None
        if contemporaneous is not None:
            same_intake_eligible+=1
            z=contemporaneous
            source=parse_time(z["source_observed_at_utc"])
            scores=parse_time(z["source_score_retrieved_at_utc"])
            fixture=parse_time(z["source_fixture_observed_at_utc"])
            digest=z.get("source_bundle_sha256")
            if (z.get("source_class")!=SAME_INTAKE_STATUS or
                z.get("model")!=V04_MODEL or
                z.get("market_used_for_fit") is not False or
                z.get("no_v03_scores_used") is not True or
                z.get("before_qb_shadow_issued") is not True or
                z.get("not_a_published_website_snapshot") is not True or
                z.get("model_promoted") is not False or
                digest!=shadow.get("same_intake_v04_source_sha256") or
                not isinstance(digest,str) or len(digest)!=64 or
                any(not isinstance(z.get(k),str) or len(z[k])!=64 for k in
                    ("source_scoreboard_sha256","source_manifest_sha256",
                     "source_training_rows_sha256","source_context_sha256")) or
                not scores<=fixture<=source<=decision or
                source>=kick or z.get("status") not in
                    (V04_STATUS,"V04_TEAM_NOT_IN_PRIOR_HISTORY")):
                raise ValueError("Untrusted earlier same-intake V04 score receipt")
            m=z.get("home_margin")
            if m is not None:
                if (z.get("status")!=V04_STATUS or type(m) not in (int,float)
                    or not math.isfinite(m) or abs(m)>55):
                    raise ValueError("Invalid same-intake V04 score")
                choices.append((source,None,digest,float(m),{
                    "frozen_forecast_sha256":shadow["baseline_forecast_sha256"],
                    "source_kind":"SAME_INTAKE_BEFORE_QB_SHADOW",
                    "market_odds_not_used":True}))
        else:
          for capture,site_run,digest,records in site:
              since=(decision-capture).total_seconds()/3600
              if not 0<=since<=MAX_CAPTURE_LAG_HOURS:continue
              lead=(kick-capture).total_seconds()/3600
              if not 24<=lead<=72:continue
              control=records.get(gid)
              if control is None:continue
              if (control.get("home"),control.get("away"),
                  parse_time(control.get("kickoff_utc"))) !=(
                  row["home"],row["away"],kick):
                  raise ValueError("V04 archived team or kickoff differs from QB grade")
              if control.get("v04_direct_home_margin") is None:continue
              if (control.get("v04_direct_score_model")!=V04_MODEL or
                  control.get("v04_direct_source_no_v03_total_reuse") is not True or
                  control.get("v04_research_not_promoted") is not True or
                  control.get("home_bias_quarantined") is not True or
                  parse_time(control["frozen_forecast_observed_utc"])>capture or
                  not isinstance(control.get("frozen_forecast_sha256"),str) or
                  len(control["frozen_forecast_sha256"])!=64):
                  raise ValueError("Untrusted independently archived V04 score receipt")
              margin=control["v04_direct_home_margin"]
              if type(margin) not in (int,float) or not math.isfinite(margin) or abs(margin)>55:
                  raise ValueError("Invalid frozen V04 score margin")
              choices.append((capture,site_run,digest,float(margin),control))
        if not choices:
            reason="NO_SAME_GAME_V04_BEFORE_QB_ISSUE_WITHIN_6H"
            no_pair[reason]=no_pair.get(reason,0)+1
            row["v04_paired_reference"]=None
            row["v04_missing_reason"]=reason
            continue
        capture,site_run,digest,margin,control=max(choices,key=lambda x:(x[0],x[1]))
        if capture>decision or capture>=kick:
            raise ValueError("Postdecision V04 baseline leakage")
        outcome=float(row["actual_home_margin"])
        if not math.isfinite(outcome):
            raise ValueError("Untrusted actual home margin")
        pair={"v04_frozen_home_margin":margin,
              "v04_source_kind":control.get("source_kind","EARLIER_WEBSITE_SNAPSHOT"),
              "v04_source_receipt_sha256":digest,
              "kickoff_utc":original["kickoff_utc"],
              "v04_abs_error":round(abs(margin-outcome),5),
              "qb_conditional_abs_error":row["model_results"]["qb_conditional"]["abs_error"],
              "capture_utc":capture.isoformat(),
              "qb_shadow_observed_utc":decision.isoformat(),
              "site_snapshot_run_id":site_run,
              "site_snapshot_sha256":digest if site_run is not None else None,
              "model_forecast_sha256":control["frozen_forecast_sha256"],
              "observation_lag_minutes":round((decision-capture).total_seconds()/60,3),
              "source_hashed_before_qb_decision":True,
              "market_odds_not_used":True,
              "no_hindsight_recalculation":True,
              "not_claimed_as_simultaneously_published_website_score":True}
        row["v04_paired_reference"]=pair
        matched+=1
        paired_dates.add(kick.astimezone(ZoneInfo("America/New_York")).date().isoformat())
        v04_error+=pair["v04_abs_error"]
        candidate_error+=pair["qb_conditional_abs_error"]
        if pair["v04_source_kind"]=="SAME_INTAKE_BEFORE_QB_SHADOW":
            same_intake_paired+=1
            same_intake_dates.add(kick.astimezone(ZoneInfo("America/New_York")).date().isoformat())
            same_intake_v04_err+=pair["v04_abs_error"]
            same_intake_qb_err+=pair["qb_conditional_abs_error"]
            same_intake_v03_err+=row["baseline_v03_abs_error"]
    metric=result["metrics"].get("qb_conditional")
    if not isinstance(metric,dict) or metric.get("games",0)!=total:
        raise ValueError("Mismatched QB-conditional grade denominator")
    # Explicitly separate partially paired subsets from a complete cohort:
    # the milestone validation gate requires all QB games to be V04-paired.
    if total:
        metric["same_game_baseline_v04_games"]=matched
        metric["same_game_baseline_v04_mae"]=(
            round(v04_error/matched,5) if matched==total else None)
        metric["same_game_v04_pregame_source_hashed"]=bool(matched==total)
        metric["v04_paired_subset_qb_mae"]=(
            round(candidate_error/matched,5) if matched else None)
        metric["v04_paired_subset_control_mae"]=(
            round(v04_error/matched,5) if matched else None)
        metric["v04_control_policy"]="SEPARATE_PRIOR_SITE_OR_SAME_INTAKE_FROZEN_V04"
    metric["post_instrumentation_eligible_qb_games"]=same_intake_eligible
    metric["post_instrumentation_paired_qb_games"]=same_intake_paired
    metric["post_instrumentation_pair_fraction"]=(
        round(same_intake_paired/same_intake_eligible,5) if same_intake_eligible else None)
    metric["post_instrumentation_qb_mae"]=(
        round(same_intake_qb_err/same_intake_paired,5) if same_intake_paired else None)
    metric["post_instrumentation_v04_mae"]=(
        round(same_intake_v04_err/same_intake_paired,5) if same_intake_paired else None)
    metric["post_instrumentation_no_qb_v03_mae"]=(
        round(same_intake_v03_err/same_intake_paired,5) if same_intake_paired else None)
    metric["post_instrumentation_distinct_game_dates"]=len(same_intake_dates)
    result["v04_comparison_audit"]={
        "status":STATUS,"qb_candidate_games":total,
        "same_game_v04_pair_count":matched,
        "unpaired_game_count":total-matched,
        "reasons_unpaired":no_pair,
        "snapshot_age_limit_hours":MAX_CAPTURE_LAG_HOURS,
        "post_instrumentation_eligible_games":same_intake_eligible,
        "post_instrumentation_paired_games":same_intake_paired,
        "post_instrumentation_pair_fraction":(
            round(same_intake_paired/same_intake_eligible,5)
            if same_intake_eligible else None),
        "post_instrumentation_distinct_game_dates":len(same_intake_dates),
        "preinstrumentation_games_reported":total-same_intake_eligible,
        "same_intake_frozen_score_pairs":sum(
            r.get("v04_paired_reference",{}).get("v04_source_kind")==
            "SAME_INTAKE_BEFORE_QB_SHADOW" for r in result["per_game"]
            if r.get("v04_paired_reference") is not None),
        "distinct_paired_football_dates":len(paired_dates),
        "fully_matched_cohort":bool(total and matched==total),
        "predecision_source_hashed_no_hindsight":True,
        "no_market_odds_fit":True,
        "no_model_promoted":True,
        "betting_status":"PASS_UNVALIDATED"}
    return result

def run(grades_path,output_path):
    from scripts.candidate_shadow_grade import read_candidates
    p=Path(grades_path)
    grade=json.loads(p.read_text(encoding="utf-8"))
    qb=read_candidates()["qb"]
    snapshots=read_site_snapshots(qb)
    record=enrich(grade,qb,snapshots)
    target=Path(output_path)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x",encoding="utf-8") as dst:
        json.dump(record,dst,indent=2,sort_keys=True,allow_nan=False)
        dst.write("\n")
    print(json.dumps(record["v04_comparison_audit"],sort_keys=True))
    return record


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--grades",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    run(args.grades,args.output)

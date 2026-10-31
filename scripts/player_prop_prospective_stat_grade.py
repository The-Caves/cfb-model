"""Independently grade saved pre-kickoff 2026 PlayerForm stat predictions.

This grader never reconstructs old model predictions from later box scores.
Choose the EARLIEST valid archived forecast for each game/athlete/metric,
then independently observe the completed game's ESPN athlete category.
Missing athlete or category means UNKNOWN, not zero/DNP and not a loss.
Retrospective source's original publication time is NOT independently
authenticated; current collection time, hashes and model grade stay distinct.
No sportsbooks, ROI, calibrated over/under probabilities or auto promotion.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import re
from collections import Counter,defaultdict
from pathlib import Path

from scripts import context_archive as store
from scripts.game_context import parse_time
from scripts.nextgen_source_readiness import SOURCE,fetch_asset
from scripts.player_prop_history import NEEDED,from_box_rows,STATUS as PLAYER_HISTORY
from scripts.player_prop_prior_seasons import SCHEDULE_COLS,make_schedule
from scripts.site_player_projection_archive import (
    INDEX,ROOT,STATUS as ARCHIVED, METRICS, MAX_AGE_SECONDS)

STATUS="PROSPECTIVE_FROZEN_PLAYER_STAT_MAE_GRADE_RESEARCH_ONLY"
LATEST="state/player_stat_grade_latest.json"
INDEX_FILE=INDEX
RUN_PATTERN=r"research_2026/player_projection_snapshots/(?:2026/(?:08|09|10|11|12)|2027/01)/\d{2}/run-\d+\.json\.gz"
CATEGORIES={"passing_yards":"passing","rushing_yards":"rushing",
            "receiving_yards":"receiving"}
MAX_RUNS=5000

def _num(x):
    return type(x) in (int,float) and math.isfinite(x)

def _names_match(a,b):
    x=re.sub("[^a-z0-9]","",str(a or "").lower())
    y=re.sub("[^a-z0-9]","",str(b or "").lower())
    return bool(x and y and (x==y or x in y or y in x))

def _snapshot(root,entry,now):
    run=str(entry["run_id"])
    if not run.isdigit():raise ValueError("Non-numeric archived run ID")
    stamp=parse_time(entry["capture_utc"])
    if stamp>now:raise ValueError("Future archived run in history")
    expected=ROOT+"/"+stamp.strftime("%Y/%m/%d")+"/run-"+run+".json.gz"
    path=entry["path"]
    if (path!=expected or re.fullmatch(RUN_PATTERN,path) is None):
        raise ValueError("Unsafe player-stat archive path")
    data_path=root/path
    if not data_path.is_file():raise ValueError("Missing immutable player-stat evidence")
    raw=data_path.read_bytes()
    if len(raw)>20_000_000:raise ValueError("Oversized archived player-stat evidence")
    obj=json.loads(gzip.decompress(raw))
    digest=hashlib.sha256(store.encode(obj)).hexdigest()
    if digest!=entry["sha256"]:raise ValueError("Archived player forecast checksum changed")
    if (obj.get("status")!=ARCHIVED or obj.get("schema_version")!=1
        or obj.get("season")!=2026 or obj.get("betting_status")!="PASS_UNVALIDATED"
        or obj.get("safe_for_betting") is not False
        or obj.get("model_promoted") is not False
        or obj.get("dashboard_run_id")!=run
        or parse_time(obj["captured_at_utc"])!=stamp
        or obj.get("player_model_version")!="PlayerForm R1"
        or obj.get("summary",{}).get("player_stat_projections")!=len(obj.get("rows",[]))):
        raise ValueError("Invalid immutable player-stat forecast record")
    return obj,stamp

def select_first(root,evaluated_at_utc):
    root=Path(root)
    now=parse_time(evaluated_at_utc)
    index_file=root/INDEX_FILE
    if not index_file.is_file():
        return {},{"archive_status":"NO_ARCHIVE_INDEX_YET","archived_runs":0,
                   "archived_forecasts_across_runs":0}
    index=json.loads(index_file.read_text(encoding="utf-8"))
    if (index.get("status")!=ARCHIVED or index.get("schema_version")!=1
        or not isinstance(index.get("runs"),list) or len(index["runs"])>MAX_RUNS):
        raise ValueError("Invalid or unbounded player archive index")
    picked={};runs=set();raw_count=0
    for entry in index["runs"]:
        run=str(entry["run_id"])
        if run in runs:raise ValueError("Duplicate player archive run")
        runs.add(run)
        obj,stamp=_snapshot(root,entry,now)
        duplicate=set()
        for row in obj["rows"]:
            key=(str(row.get("game_id")),str(row.get("player_id")),row.get("metric"))
            if key in duplicate:raise ValueError("Duplicated player in same snapshot")
            duplicate.add(key)
            kick=parse_time(row["kickoff_utc"])
            issued=parse_time(row["source_observed_at_utc"])
            if (not key[0].isdigit() or not key[1].isdigit()
                or key[2] not in METRICS or
                not issued<=stamp<kick or (stamp-issued).total_seconds()>MAX_AGE_SECONDS
                or row.get("model_version")!="PlayerForm R1"
                or not _num(row.get("projection_conditional_yards"))
                or not -100<=row["projection_conditional_yards"]<=1200
                or row.get("team_side") not in ("home","away")
                or row.get("team")!=row[row["team_side"]+"_team"]
                or not isinstance(row.get("player"),str) or not row["player"].strip()
                or row.get("original_V03_sha256")!=obj["original_score_forecast_sha256"]
                or row.get("real_bookmaker_line") is not None
                or row.get("real_bookmaker_over_probability") is not None
                or row.get("player_participation_verified") is not False
                or row.get("eligible_for_future_independent_player_stat_grading") is not True):
                raise ValueError("Untrusted or post-kickoff frozen player research row")
            raw_count+=1
            priority=(stamp,int(run))
            if key not in picked or priority<picked[key][0]:
                picked[key]=(priority,row,run)
    return picked,{"archive_status":"VALID_PREKICKOFF_PLAYER_STAT_ARCHIVES",
        "archived_runs":len(runs),"archived_forecasts_across_runs":raw_count}

def grade(root,official_fixtures,player_ledger,evaluated_at_utc):
    now=parse_time(evaluated_at_utc)
    if (player_ledger.get("status")!=PLAYER_HISTORY
        or player_ledger.get("season")!=2026
        or player_ledger.get("betting_status")!="PASS_UNVALIDATED"
        or player_ledger.get("retrospective_first_publication_authenticated") is not False
        or parse_time(player_ledger["observed_at_utc"])>now):
        raise ValueError("Untrusted current observed player game finals")
    if not isinstance(official_fixtures,list):
        raise ValueError("Source-completed fixture rows required")
    completed,excluded=make_schedule(official_fixtures,2026,evaluated_at_utc)
    forecasts,summary=select_first(root,evaluated_at_utc)
    actual={};seen=set()
    for r in player_ledger["rows"]:
        key=(str(r["game_id"]),str(r["player_id"]),str(r["team_id"]))
        if key in seen:raise ValueError("Duplicate ESPN athlete/team game final")
        seen.add(key)
        if r.get("source_status")!="RETROSPECTIVE_REVISED_PLAYER_BOX_ONLY":
            raise ValueError("Untrusted observed player category final")
        actual[key]=r
    counts=Counter();by_metric=defaultdict(list)
    grades=[]
    for (gid,pid,metric),(_,pred,run) in sorted(forecasts.items()):
        if gid not in completed:
            counts["GAME_NOT_VERIFIED_FINAL"]+=1
            continue
        fixture=completed[gid]
        if (abs((parse_time(pred["kickoff_utc"])-parse_time(fixture["kickoff_utc"])).total_seconds())>3600
            or not _names_match(pred["home_team"],fixture["home"])
            or not _names_match(pred["away_team"],fixture["away"])):
            counts["GAME_ID_TIME_OR_TEAM_MISMATCH_QUARANTINED"]+=1
            continue
        team_id=str(fixture[pred["team_side"]+"_id"])
        final=actual.get((gid,pid,team_id))
        if final is None:
            counts["COMPLETED_GAME_PLAYER_UNOBSERVED_DNP_UNKNOWN"]+=1
            continue
        if (parse_time(final["kickoff_utc"])!=parse_time(fixture["kickoff_utc"])
            or parse_time(final["observed_at_utc"])<=parse_time(pred["kickoff_utc"])):
            raise ValueError("Player game recorded before scheduled kickoff")
        if CATEGORIES[metric] not in final.get("categories",[]):
            counts["PLAYER_STAT_CATEGORY_UNOBSERVED_NOT_ZERO"]+=1
            continue
        value=final["values"].get(metric)
        if type(value) is not int:
            counts["RECORDED_PLAYER_STAT_MISSING_VALUE"]+=1
            continue
        baseline=pred.get("recent_four_baseline_yards")
        if baseline is not None and (not _num(baseline) or not -100<=baseline<=1200):
            raise ValueError("Invalid frozen challenger baseline")
        projection=pred["projection_conditional_yards"]
        r={
            "game_id":gid,"player_id":pid,"player":pred["player"],
            "team_id":team_id,"metric":metric,
            "kickoff_utc":pred["kickoff_utc"],
            "forecast_run_id":run,"forecast_capture_utc":pred["source_observed_at_utc"],
            "model_version":pred["model_version"],
            "actual_recorded_player_yards":value,
            "conditional_playerform_yards":projection,
            "absolute_error":round(abs(value-projection),6),
            "signed_error":round(projection-value,6),
            "recent_four_baseline_yards":baseline,
            "recent_four_absolute_error":round(abs(baseline-value),6) if baseline is not None else None,
            "source_observed_at_utc":final["observed_at_utc"],
            "player_category_recorded_not_full_active_roster_confirmation":True,
        }
        grades.append(r);by_metric[metric].append(r)
        counts["GRADED_RECORDED_PLAYER_STAT"]+=1
    metrics={}
    for metric in sorted(METRICS):
        rows=by_metric[metric];n=len(rows)
        paired=[r for r in rows if r["recent_four_baseline_yards"] is not None]
        m=len(paired)
        mae=sum(r["absolute_error"] for r in rows)/n if n else None
        bm=sum(r["recent_four_absolute_error"] for r in paired)/m if m else None
        mm=sum(r["absolute_error"] for r in paired)/m if m else None
        metrics[metric]={
            "graded_recorded_player_games":n,
            "playerform_conditional_mae":round(mae,5) if n else None,
            "playerform_mean_signed_error":round(sum(r["signed_error"] for r in rows)/n,5) if n else None,
            "paired_with_frozen_recent_four_baseline":m,
            "paired_model_mae":round(mm,5) if m else None,
            "paired_recent_four_baseline_mae":round(bm,5) if m else None,
            "paired_mae_improvement":round(bm-mm,5) if m else None,
            "automatic_promotion_approved":False,
        }
    total=len(forecasts)
    return {
        "status":STATUS,"season":2026,
        "graded_at_utc":now.isoformat(),
        "source_observed_at_utc":player_ledger["observed_at_utc"],
        "source_player_box_sha256":player_ledger.get("source_sha256"),
        "archive_verification":summary,
        "eligible_unique_pre_kickoff_player_forecasts":total,
        "graded_recorded_player_stat_samples":len(grades),
        "player_category_coverage_rate":round(len(grades)/total,5) if total else None,
        "missing_or_unsettled":dict(counts),
        "excluded_completed_source_fixtures":excluded,
        "metrics":metrics,"grade_records":grades,
        "first_valid_pregame_snapshot_only":True,
        "missing_player_or_category_is_not_zero_or_assumed_dnp":True,
        "historical_source_first_publication_authenticated":False,
        "prospective_athlete_game_outcome_as_observed_only":True,
        "no_bookmaker_prop_lines_or_return_calculated":True,
        "player_participation_not_preconfirmed":True,
        "no_automatic_model_promotion":True,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED",
    }

def publish_latest(result):
    """Persist current as-observed grading, never modify frozen forecast rows."""
    if (result.get("status")!=STATUS
        or result.get("betting_status")!="PASS_UNVALIDATED"
        or result.get("model_promoted") is not False
        or result.get("safe_for_betting") is not False):
        raise ValueError("Invalid live player-stat grade publication")
    # A small latest summary is deliberately mutable. Predictions themselves
    # remain immutable in their separate per-run SHA-bound archive.
    public={k:v for k,v in result.items() if k not in
            ("grade_records","excluded_completed_source_fixtures")}
    public["grade_records_persisted_in_latest"]=False
    prior=store.get_blob_file(LATEST)
    if prior is not None:
        old=json.loads(prior)
        if (old.get("status")!=STATUS or
            parse_time(old["graded_at_utc"])>parse_time(result["graded_at_utc"])):
            raise ValueError("Refusing stale or unrecognized latest grade overwrite")
    blob=store.encode(public)
    if prior==blob:
        return {"status":"GRADE_ALREADY_PUBLISHED","path":LATEST}
    from scripts.personnel_results_archive import _commit_material
    sha=_commit_material({LATEST:blob},"player-prop-grading")
    return {"status":"PLAYER_STAT_GRADE_PUBLISHED","path":LATEST,
            "commit_sha":sha,
            "graded_recorded_player_stat_samples":result["graded_recorded_player_stat_samples"]}

def run(archive_root,output,publish=False):
    import pyarrow.parquet as pq
    schedule_uri=SOURCE+"/cfb_schedules/cfb_schedules_2026.parquet"
    box_uri=SOURCE+"/espn_cfb_player_box/player_box_2026.parquet"
    fixtures_blob=fetch_asset(schedule_uri,max_bytes=150_000_000)
    box_blob=fetch_asset(box_uri,max_bytes=150_000_000)
    schedule_pq=pq.ParquetFile(io.BytesIO(fixtures_blob))
    box_pq=pq.ParquetFile(io.BytesIO(box_blob))
    if not SCHEDULE_COLS.issubset(schedule_pq.schema_arrow.names):
        raise ValueError("Fresh completed-game schedule schema mismatch")
    if not NEEDED.issubset(box_pq.schema_arrow.names):
        raise ValueError("Fresh player-box source schema mismatch")
    fixtures=schedule_pq.read(columns=sorted(SCHEDULE_COLS)).to_pylist()
    boxes=box_pq.read(columns=sorted(NEEDED)).to_pylist()
    observed=dt.datetime.now(dt.timezone.utc)
    games,_=make_schedule(fixtures,2026,observed.isoformat())
    ledger=from_box_rows(boxes,games,observed.isoformat())
    ledger["source_sha256"]=hashlib.sha256(box_blob).hexdigest()
    result=grade(archive_root,fixtures,ledger,observed.isoformat())
    result["schedule_source_sha256"]=hashlib.sha256(fixtures_blob).hexdigest()
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    if publish:
        result["publication"]=publish_latest(result)
    print(json.dumps({"status":STATUS,"archive":result["archive_verification"],
       "prospectively_frozen_player_stats":result["eligible_unique_pre_kickoff_player_forecasts"],
       "graded_samples":result["graded_recorded_player_stat_samples"],
       "metrics":result["metrics"],"safe_for_betting":False},sort_keys=True))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",required=True);p.add_argument("--output",required=True)
    p.add_argument("--publish",action="store_true")
    a=p.parse_args();run(a.archive_root,a.output,publish=a.publish)

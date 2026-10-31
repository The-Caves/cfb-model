"""Append-only observed pre-kickoff PlayerForm R1 STAT research forecasts.

Archived displayed player-stat projection != authentic bookmaker player prop
line; the historical 2026 box feed original publication time is unverified.
Save the exact prospectively displayed player/game/metric/conditional numeric
projection before kickoff for later independent outcome grading. Git commit
time is a reproducible receipt, not third-party timestamp attestation.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path

from scripts import context_archive as store
from scripts.game_context import parse_time
from scripts.personnel_results_archive import _commit_material
from scripts.site_player_props import STATUS as PLAYER_STATUS

ROOT="research_2026/player_projection_snapshots"
INDEX=ROOT+"/index.json"
STATUS="ARCHIVED_PREKICKOFF_CONDITIONAL_PLAYER_STAT_DISPLAY_RESEARCH_ONLY"
METRICS={"passing_yards","rushing_yards","receiving_yards"}
MAX_AGE_SECONDS=3600

def _finite(x):
    return type(x) in (float,int) and math.isfinite(x)

def freeze(board,now,run_id):
    if (board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED"
        or not isinstance(board.get("games"),list)
        or not str(run_id).isdigit()
        or not isinstance(board.get("forecast_sha256"),str)
        or len(board["forecast_sha256"])!=64
        or board.get("player_prop_display",{}).get("model_scores_updated") is not False
        or board.get("player_prop_display",{}).get("real_bookmaker_quotes_present") is not False):
        raise ValueError("Invalid source-linked archived score/player board")
    capture=parse_time(now)
    model=board["player_prop_display"].get("model")
    if model!="PlayerForm R1":
        raise ValueError("Unsupported experimental player-stat model version")
    rows=[];seen=set();excluded=0
    for game in board["games"]:
        gid=str(game["game_id"])
        kick=parse_time(game["kickoff_utc"])
        if kick<=capture:
            excluded+=1
            continue
        pp=game.get("player_props") or {}
        if pp.get("status") not in (PLAYER_STATUS,"PLAYER_OUTLOOK_UNAVAILABLE"):
            raise ValueError("Missing source-gated PlayerForm game record")
        if pp.get("real_bookmaker_prop_lines")!=0:
            raise ValueError("Actual bookmaker player lines cannot enter this archive")
        if pp["status"]!="PLAYER_OUTLOOK_UNAVAILABLE":
            observed=parse_time(pp["source_observed_at_utc"])
            if observed>capture or observed>=kick or (capture-observed).total_seconds()>MAX_AGE_SECONDS:
                raise ValueError("Stale or future-dated player research source")
        for row in pp.get("entries",[]):
            ident=(gid,str(row.get("player_id")),str(row.get("metric")))
            if ident in seen:raise ValueError("Duplicate player-stat research forecast")
            seen.add(ident)
            if not (str(row.get("player_id","")).isdigit()
                and row.get("metric") in METRICS
                and row.get("team_side") in ("home","away")
                and row.get("team")==game[row["team_side"]+"_team"]
                and isinstance(row.get("player"),str) and row["player"].strip()
                and _finite(row.get("projection"))
                and 0<=row["projection"]<=1200
                and row.get("unit")=="yards"
                and row.get("real_bookmaker_line") is None
                and row.get("over_probability") is None
                and row.get("workload_share_used_to_change_yard_projection") is False
                and row.get("player_participation_status")=="RECENT_GAME_PARTICIPANT_NOT_CONFIRMED"):
                raise ValueError("Untrusted or improperly attributed player-prop research display")
            issued=parse_time(row["source_observed_at_utc"])
            if issued>capture or issued>=kick or (capture-issued).total_seconds()>MAX_AGE_SECONDS:
                raise ValueError("Player projection issued after kickoff or outside source-age policy")
            recent=row.get("recent_four_baseline_yards")
            if recent is not None and (not _finite(recent) or not -100<=recent<=1200):
                raise ValueError("Invalid independent same-time recent-four baseline")
            role=row.get("workload_role_evidence")
            if role is not None:
                share=role.get("recorded_opportunity_share")
                if (not _finite(share) or not 0<=share<=1 or
                    role.get("participation_not_confirmed") is not True or
                    role.get("share_is_not_snap_or_target_percentage") is not True):
                    raise ValueError("Misleading workload / roster evidence")
            rows.append({
                "game_id":gid,"kickoff_utc":game["kickoff_utc"],
                "home_team":game["home_team"],"away_team":game["away_team"],
                "player_id":str(row["player_id"]),"player":row["player"],
                "team_side":row["team_side"],"team":row["team"],
                "metric":row["metric"],"model_version":model,
                "projection_conditional_yards":row["projection"],
                "recent_four_baseline_yards":recent,
                "workload_role_evidence":role,
                "official_reported_status":row.get("official_reported_status","UNKNOWN_NOT_REPORTED"),
                "player_participation_verified":False,
                "real_bookmaker_line":None,
                "real_bookmaker_over_probability":None,
                "source_observed_at_utc":row["source_observed_at_utc"],
                "original_V03_model":board["model"],
                "original_V03_sha256":board["forecast_sha256"],
                "original_V03_forecast_observed_at_utc":board["forecast_observed_utc"],
                "source_first_publication_time_verified":False,
                "eligible_for_future_independent_player_stat_grading":True,
                "not_a_betting_prop_or_validated_edge":True,
            })
    rows.sort(key=lambda r:(r["kickoff_utc"],r["game_id"],r["team_side"],r["player_id"],r["metric"]))
    return {
        "status":STATUS,"schema_version":1,"season":2026,
        "captured_at_utc":capture.isoformat(),
        "dashboard_run_id":str(run_id),
        "score_model_version":board["model"],
        "player_model_version":model,
        "original_score_forecast_sha256":board["forecast_sha256"],
        "board_display_sha256":hashlib.sha256(store.encode(board)).hexdigest(),
        "research_model_and_bookmaker_lines_synchronized":False,
        "publisher_first_publication_authenticated":False,
        "not_an_executed_bet":True,
        "summary":{"future_games":sum(parse_time(g["kickoff_utc"])>capture for g in board["games"]),
                   "player_stat_projections":len(rows),
                   "excluded_kicked_off_games":excluded,
                   "games_with_player_stat_projections":len({r["game_id"] for r in rows})},
        "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
        "model_promoted":False,"rows":rows,
    }

def archive(snapshot):
    if snapshot.get("status")!=STATUS or snapshot.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Wrong player-stat research snapshot")
    run_id=str(snapshot["dashboard_run_id"])
    path=ROOT+"/"+parse_time(snapshot["captured_at_utc"]).strftime("%Y/%m/%d")+"/run-"+run_id+".json.gz"
    packed=store.pack(snapshot)
    old=store.get_blob_file(path)
    if old is not None:
        if old!=packed:
            raise ValueError("Cannot rewrite already-frozen player predictions")
        return {"status":"ALREADY_ARCHIVED","path":path,"summary":snapshot["summary"]}
    prev=store.get_blob_file(INDEX)
    index=json.loads(prev) if prev else {"status":STATUS,"schema_version":1,"runs":[]}
    if (index.get("status")!=STATUS or index.get("schema_version")!=1
        or not isinstance(index.get("runs"),list)
        or any(x["run_id"]==run_id for x in index["runs"])):
        raise ValueError("Duplicate or corrupt player projection index")
    index["runs"].append({"run_id":run_id,"path":path,
        "sha256":hashlib.sha256(store.encode(snapshot)).hexdigest(),
        "capture_utc":snapshot["captured_at_utc"],**snapshot["summary"]})
    sha=_commit_material({path:packed,INDEX:store.encode(index)},run_id)
    return {"status":"ARCHIVED","commit_sha":sha,"path":path,
            "summary":snapshot["summary"]}

def run(input_file,now=None,run_id=None,persist=True):
    current=now or dt.datetime.now(dt.timezone.utc)
    identity=run_id or os.environ.get("GITHUB_RUN_ID","")
    board=json.loads(Path(input_file).read_text(encoding="utf-8"))
    snapshot=freeze(board,current,identity)
    if not snapshot["rows"]:
        return {"status":"NO_ELIGIBLE_SOURCE_RECORDED_PLAYER_PROJECTIONS",
                "summary":snapshot["summary"],"model_promoted":False}
    if not persist:return snapshot
    return archive(snapshot)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--dashboard",required=True)
    a=p.parse_args()
    print(json.dumps(run(a.dashboard),sort_keys=True))

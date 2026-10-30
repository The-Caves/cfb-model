"""Join authentic 2026 observed player box totals to source-observed ESPN drives.

Use only completed, matched, internally reconciling game/team observations.
No proof of historical first publication time is implied. The captured
snapshots are usable prospectively only after their real observation.
Do not assume the observed roster includes DNPs, unlisted players or starters.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import math
from collections import defaultdict,Counter
from pathlib import Path

from scripts.game_context import parse_time
from scripts.player_prop_history import STATUS as HISTORY_STATUS, _id
from scripts.player_prop_team_budget_audit import audit as audit_box
from scripts.nextgen_source_readiness import ASSETS, fetch_asset, SOURCE

STATUS="OBSERVED_ESPN_TEAM_BOX_DRIVE_BUDGETS_RESEARCH_ONLY"
SOURCE_KIND="CURRENTLY_OBSERVED_REVISED_PROVIDER_RELEASE"
DRIVE_URI=SOURCE+"/"+ASSETS["drives_2026"][0]

def _driveid(v):
    if v is None or isinstance(v,bool):return None
    token=str(v).strip()
    return token if token and token.lower() not in {"nan","none","null","unknown"} and len(token)<128 else None

def assemble(history,drives,drives_observed_utc,sha256):
    when=parse_time(drives_observed_utc)
    if (history.get("status")!=HISTORY_STATUS or
        history.get("retrospective_first_publication_authenticated") is not False or
        history.get("betting_status")!="PASS_UNVALIDATED" or
        parse_time(history["observed_at_utc"])>when or
        not isinstance(sha256,str) or len(sha256)!=64):
        raise ValueError("Untrusted current observational player box release")
    box=audit_box(history)
    metadata={}
    for r in history["rows"]:
        key=(str(r["game_id"]),str(r["team_id"]))
        fixture=(str(r["date"]),str(r["kickoff_utc"]))
        if key in metadata and metadata[key]!=fixture:
            raise ValueError("Contradictory ESPN player-game fixture")
        metadata[key]=fixture
    records=defaultdict(set);repeated=set();rejected=Counter()
    for row in drives:
        if not isinstance(row,dict) or row.get("season") not in (2026,"2026"):
            rejected["OTHER_SEASON_OR_INVALID_ROW"]+=1;continue
        gid,team,drive=_id(row.get("game_id")),_id(row.get("team_id")),_driveid(row.get("drive_id"))
        if not gid or not team or not drive:
            rejected["INVALID_GAME_TEAM_DRIVE_ID"]+=1;continue
        key=(gid,team)
        if key not in metadata:
            rejected["NO_MATCHED_PLAYER_BOX_TEAM_GAME"]+=1;continue
        if parse_time(metadata[key][1])>=when:
            rejected["NOT_AN_OBSERVED_COMPLETED_GAME"]+=1;continue
        if drive in records[key]:repeated.add(key)
        records[key].add(drive)
    budgets=[]
    for row in box["per_team_game"]:
        key=(row["game_id"],row["team_id"])
        if key in repeated:
            rejected["DUPLICATED_DRIVE_ID_IN_TEAM_GAME"]+=1;continue
        count=len(records[key])
        if not 1<=count<=24:
            rejected["MISSING_OR_IMPLAUSIBLE_DRIVE_COUNT"]+=1;continue
        if row["observed_completion_reception_exact_match"] is not True:
            rejected["COMPLETIONS_RECEPTIONS_NOT_RECONCILED"]+=1;continue
        if row["observed_passing_receiving_yard_exact_match"] is not True:
            rejected["PASS_RECEIVE_YARDS_NOT_RECONCILED"]+=1;continue
        required=("reported_passing_attempts","reported_passing_completions",
                  "reported_passing_yards","reported_rushing_attempts",
                  "reported_rushing_yards")
        if any(row[k] is None for k in required):
            rejected["MISSING_TEAM_PLAY_CATEGORY"]+=1;continue
        if (row["reported_passing_attempts"]<row["reported_passing_completions"]
            or (row["reported_passing_completions"]==0 and row["reported_passing_yards"]!=0)):
            rejected["INCONSISTENT_TEAM_PASS_YARD_BUDGET"]+=1;continue
        date,kick=metadata[key]
        budgets.append({
            "game_id":row["game_id"],"team_id":row["team_id"],
            "date":date,"kickoff_utc":kick,
            "outcome_confirmed_by_capture_utc":when.isoformat(),
            "observed_at_utc":when.isoformat(),
            "source_url":DRIVE_URI,
            "source_sha256":sha256,
            "player_box_source_sha256":history.get("source_sha256"),
            "pass_attempts":row["reported_passing_attempts"],
            "pass_completions":row["reported_passing_completions"],
            "pass_yards":row["reported_passing_yards"],
            "rush_attempts":row["reported_rushing_attempts"],
            "rush_yards":row["reported_rushing_yards"],
            "possessions":count,
            "player_stat_categories_reconciled":True,
            "recorded_complete_active_roster":False,
            "historical_first_publication_authenticated":False,
        })
    budgets.sort(key=lambda x:(x["date"],x["game_id"],x["team_id"]))
    return {"status":STATUS,"season":2026,"observed_at_utc":when.isoformat(),
        "source_uri":DRIVE_URI,"source_sha256":sha256,
        "source_kind":SOURCE_KIND,
        "team_game_budgets":budgets,
        "summary":{"reconciled_box_team_slots":len(box["per_team_game"]),
                   "eligible_matched_game_team_budgets":len(budgets),
                   "rejected_by_reason":dict(rejected),
                   "drive_team_slots":len(records),
                   "duplicated_drive_team_slots":len(repeated)},
        "historical_first_publication_authenticated":False,
        "true_pregame_source_snapshot_only_from_this_capture_forward":True,
        "all_active_player_participation_verified":False,
        "future_slate_player_roles_available":False,
        "ready_for_live_prop_forecasts":False,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

def run(player_file,output_file):
    import pyarrow.parquet as pq
    history=json.loads(Path(player_file).read_text(encoding="utf-8"))
    blob=fetch_asset(DRIVE_URI)
    required={"season","game_id","team_id","drive_id"}
    pqf=pq.ParquetFile(io.BytesIO(blob))
    if not required.issubset(pqf.schema_arrow.names):
        raise ValueError("Actual 2026 drive feed missing recorded identity fields")
    rows=pqf.read(columns=sorted(required)).to_pylist()
    when=dt.datetime.now(dt.timezone.utc).isoformat()
    result=assemble(history,rows,when,hashlib.sha256(blob).hexdigest())
    target=Path(output_file);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(result["summary"]))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True);p.add_argument("--output",required=True)
    args=p.parse_args();run(args.history,args.output)

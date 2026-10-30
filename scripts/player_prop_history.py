"""Verified-schema, player-game ESPN box-score research ledger.

ESPN athlete IDs are required. Every row represents a *recorded category*;
missing game/category is UNKNOWN, never a player zero or proof of health.
This snapshot is only evidence after retrieval. Older retroactive box-score
releases are NOT authenticated pregame snapshots.
"""
import argparse
import csv
import datetime as dt
import io
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from scripts.game_context import parse_time
from scripts.nextgen_source_readiness import SOURCE, fetch_asset

STATUS="PLAYER_GAME_BOX_PROP_HISTORY_RESEARCH_ONLY"
ASSET="espn_cfb_player_box/player_box_2026.parquet"
STAT_FIELDS={
    "passing":{"passing_yards":"passing_yards","passing_touchdowns":"passing_touchdowns",
               "interceptions":"interceptions"},
    "rushing":{"rushing_attempts":"rushing_attempts","rushing_yards":"rushing_yards",
               "rushing_touchdowns":"rushing_touchdowns"},
    "receiving":{"receptions":"receptions","receiving_yards":"receiving_yards",
                 "receiving_touchdowns":"receiving_touchdowns"}
}
STATS=tuple(sorted({f for cols in STAT_FIELDS.values() for f in cols}
                   | {"passing_attempts","passing_completions"}))
COUNT_STATS={"passing_attempts","passing_completions","passing_touchdowns","interceptions",
             "rushing_attempts","rushing_touchdowns","receptions","receiving_touchdowns"}
YARD_STATS=set(STATS)-COUNT_STATS
NEEDED={"game_id","season","team_id","category","athlete_id","athlete_name",
         "completions_passing_attempts",*STATS}-{"passing_attempts","passing_completions"}

def _id(value):
    if isinstance(value,bool):return None
    try:
        v=float(value)
        return str(int(v)) if math.isfinite(v) and v.is_integer() and v>0 else None
    except (ValueError,TypeError,OverflowError):return None

def _num(value,field):
    if value is None or value=="":return None
    raw=str(value).strip().replace(",","")
    if not re.fullmatch(r"-?\d+",raw):
        return None
    val=int(raw)
    if field in COUNT_STATS and val<0:
        return None
    if field in YARD_STATS and not -100<=val<=1200:
        return None
    if field in COUNT_STATS and val>150:
        return None
    return val

def _pairs(value):
    if not isinstance(value,str) or not re.fullmatch(r"\d+/\d+",value.strip()):
        return None,None
    a,b=(int(x) for x in value.strip().split("/"))
    return (a,b) if 0<=a<=b<=150 else (None,None)

def load_schedule(csv_path):
    games=list(csv.DictReader(Path(csv_path).open(encoding="utf-8-sig",newline="")))
    result={}
    for row in games:
        gid=_id(row.get("game_id"))
        if not gid or gid in result:raise ValueError("Missing or repeated ESPN game")
        kick=parse_time(row["kickoff_utc"])
        date=dt.date.fromisoformat(row["date"])
        if kick.year!=2026 or date.year!=2026 or not row["home"] or not row["away"]:
            raise ValueError("Invalid fixture source")
        result[gid]={"game_id":gid,"date":date.isoformat(),
                     "kickoff_utc":kick.isoformat(),
                     "home":row["home"],"away":row["away"]}
    return result

def from_box_rows(box_rows, schedule, observed_at_utc):
    observed=parse_time(observed_at_utc)
    ledger={}; quarantined=defaultdict(int);seen=set()
    for row in box_rows:
        try:
            if int(row.get("season") or 0)!=2026:
                quarantined["WRONG_SEASON"]+=1;continue
            gid=_id(row.get("game_id"))
            team=_id(row.get("team_id"))
            player=_id(row.get("athlete_id"))
            category=row.get("category")
            if gid not in schedule:
                quarantined["NO_SCORE_MATCHED_ESPN_FIXTURE"]+=1;continue
            if category not in STAT_FIELDS:
                quarantined["UNSUPPORTED_STAT_CATEGORY"]+=1;continue
            if not team or not player or not row.get("athlete_name"):
                quarantined["UNVERIFIED_PLAYER_OR_TEAM_ID"]+=1;continue
            if parse_time(schedule[gid]["kickoff_utc"])>=observed:
                quarantined["NOT_A_COMPLETED_HISTORICAL_GAME"]+=1;continue
            identity=(gid,team,player,category)
            if identity in seen:
                raise ValueError("Duplicate player/category/game; quarantine source")
            seen.add(identity)
            key=(gid,team,player)
            if key not in ledger:
                ledger[key]={"game_id":gid,"team_id":team,"player_id":player,
                  "player_name":str(row["athlete_name"]).strip(),
                  "date":schedule[gid]["date"],"kickoff_utc":schedule[gid]["kickoff_utc"],
                  "observed_at_utc":observed.isoformat(),
                  "source_uri":SOURCE+"/"+ASSET,
                  "source_status":"RETROSPECTIVE_REVISED_PLAYER_BOX_ONLY",
                  "values":{k:None for k in STATS},"categories":[]}
            obj=ledger[key]
            if obj["player_name"]!=str(row["athlete_name"]).strip():
                raise ValueError("Conflicting ESPN player identity")
            obj["categories"].append(category)
            for name,column in STAT_FIELDS[category].items():
                obj["values"][name]=_num(row.get(column),name)
            if category=="passing":
                c,a=_pairs(row.get("completions_passing_attempts"))
                obj["values"]["passing_attempts"]=a
                obj["values"]["passing_completions"]=c
        except (ValueError,TypeError,OverflowError) as ex:
            if "Duplicate" in str(ex) or "Conflicting" in str(ex):raise
            quarantined["SOURCE_DECODE_FAILURE"]+=1
    result=sorted(ledger.values(),key=lambda x:(x["date"],x["game_id"],x["player_id"]))
    return {"status":STATUS,"season":2026,"observed_at_utc":observed.isoformat(),
            "source_uri":SOURCE+"/"+ASSET,"recorded_player_games":len(result),
            "rejected_by_reason":dict(quarantined),
            "rows":result,"unlisted_player_game_means_zero":False,
            "retrospective_first_publication_authenticated":False,
            "no_injury_or_starter_inference":True,
            "model_promoted":False,"safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED"}

def download_rows():
    import pyarrow.parquet as pq
    blob=fetch_asset(SOURCE+"/"+ASSET,max_bytes=150_000_000)
    import hashlib
    parquet=pq.ParquetFile(io.BytesIO(blob))
    missing=NEEDED-set(parquet.schema_arrow.names)
    if missing:raise ValueError("Missing player box source schema: "+str(sorted(missing))+"; ACTUAL_COLUMNS="+str(sorted(parquet.schema_arrow.names)))
    # Limit loaded columns and allow sparse, nullable categories.
    table=parquet.read(columns=sorted(NEEDED))
    return table.to_pylist(),hashlib.sha256(blob).hexdigest()

def run(games,output,now=None):
    when=now or dt.datetime.now(dt.timezone.utc).isoformat()
    schedule=load_schedule(games)
    rows,sha=download_rows()
    result=from_box_rows(rows,schedule,when)
    result["source_sha256"]=sha
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":STATUS,"player_games":result["recorded_player_games"],
         "rejected":result["rejected_by_reason"],"model_promoted":False}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.games,a.output)

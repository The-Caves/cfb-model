"""Bounded, observed-time-only checks of public CFB player/drive data assets.

Usage shares measure opportunities, NOT snaps or player participation.
Roster presence is not a starting-QB confirmation. Drive result labels do not
prove offensive points because defensive returns/XP can be misattributed.
All source errors are explicit coverage gaps. NEVER retrofit downloaded
revised 2026 tables into September pregame predictions.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import urllib.request
from pathlib import Path

SOURCE="https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
ASSETS={
    "roster_2025":("espn_cfb_rosters/cfb_rosters_2025.parquet",
                   {"season","team_id","athlete_id"}),
    "roster_2026":("espn_cfb_rosters/cfb_rosters_2026.parquet",
                   {"season","team_id","athlete_id"}),
    "offense_usage_2026":("espn_cfb_usage_players/usage_players_2026.parquet",
                          {"season","pos_team_id","player_id","position_group",
                           "target_share","touch_share","games"}),
    "defense_usage_2026":("espn_cfb_usage_tackles/usage_tackles_2026.parquet",
                          {"season","def_pos_team_id","player_id","tackle_share","games"}),
    "drives_2026":("espn_cfb_drives/drives_2026.parquet",
                   {"season","game_id","team_id","drive_id","result"}),
}
STATUS="NEXTGEN_EXTERNAL_SOURCE_READINESS_RESEARCH_ONLY"

def fetch_asset(url,max_bytes=75_000_000,timeout=35):
    if not url.startswith(SOURCE+"/"):raise ValueError("Untrusted source host")
    request=urllib.request.Request(url,headers={
        "User-Agent":"CFB-nextgen-source-audit/2026","Accept":"application/octet-stream"})
    with urllib.request.urlopen(request,timeout=timeout) as response:
        chunks=[];length=0
        while True:
            chunk=response.read(min(65536,max_bytes+1-length))
            if not chunk:break
            length+=len(chunk)
            if length>max_bytes:raise ValueError("SOURCE_OVER_SIZE_LIMIT")
            chunks.append(chunk)
    return b"".join(chunks)

def audit_payload(name,blob,observed_at):
    import pyarrow.parquet as pq
    if name not in ASSETS: raise ValueError("Unregistered external dataset")
    if not isinstance(blob,bytes) or not blob:
        raise ValueError("Empty or undecodable source")
    parquet=pq.ParquetFile(io.BytesIO(blob))
    columns=set(parquet.schema_arrow.names)
    expected=ASSETS[name][1]
    missing=sorted(expected-columns)
    count=parquet.metadata.num_rows
    if count<0:raise ValueError("Invalid parquet row count")
    return {
        "status":"OBSERVED_SCHEMA_READY" if not missing and count>0 else
                 "SOURCE_MISSING_COLUMNS_OR_ROWS",
        "source_uri":SOURCE+"/"+ASSETS[name][0],
        "observed_at_utc":observed_at,
        "sha256":hashlib.sha256(blob).hexdigest(),
        "source_bytes":len(blob),
        "rows":count,
        "schema_columns_available":len(columns),
        "missing_required_columns":missing,
        "season_released":2025 if name=="roster_2025" else 2026,
        "original_publication_time_authenticated":False,
        "official_player_status_evidence":False,
        "usage_is_actual_snap_share":False,
        "drive_scoring_attribution_verified":False,
    }

def audit(observed_at=None,fetcher=fetch_asset):
    issue=observed_at or dt.datetime.now(dt.timezone.utc).isoformat()
    results={}
    for name,(path,_) in ASSETS.items():
        uri=SOURCE+"/"+path
        try:
            blob=fetcher(uri)
            results[name]=audit_payload(name,blob,issue)
        except Exception as exc:
            results[name]={"status":"SOURCE_UNAVAILABLE_OR_UNAUDITED",
                           "source_uri":uri,"observed_at_utc":issue,
                           "reason":type(exc).__name__+":"+str(exc)[:180],
                           "original_publication_time_authenticated":False}
    available=sum(v["status"]=="OBSERVED_SCHEMA_READY" for v in results.values())
    return {"status":STATUS,"season":2026,"observed_at_utc":issue,
            "datasets_checked":len(ASSETS),"datasets_schema_ready":available,
            "datasets_missing_or_incomplete":len(ASSETS)-available,
            "sources":results,
            "source_use_policy":{
                "snapshot_data_usable_only_after_real_observation":True,
                "season_usage_share_is_NOT_snap_share":True,
                "roster_entry_is_NOT_confirmed_starter":True,
                "drive_result_code_is_NOT_verified_offense_score":True,
                "availability_unlisted_is_unknown":True,
                "betting_validation_available":False,
            },
            "game_predictions_generated":0,"safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED","model_promoted":False}

def run(output):
    result=audit()
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":STATUS,"datasets_checked":result["datasets_checked"],
                      "datasets_schema_ready":result["datasets_schema_ready"],
                      "source_statuses":{k:v["status"] for k,v in result["sources"].items()},
                      "model_promoted":False}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    run(p.parse_args().output)

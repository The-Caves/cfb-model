"""Immutable archive for point-in-time market/forecast comparisons.

The board is research-only and can be graded later without recomputing picks.
"""
import argparse,datetime as dt,hashlib,json,os,re
from pathlib import Path
from scripts import context_archive as store
from scripts.personnel_results_archive import _commit_material
from scripts.game_context import parse_time

ROOT="research_2026/free_market_comparisons"
INDEX=ROOT+"/index.json"

def validate(board):
    if board.get("status")!="PROSPECTIVE_MARKET_RESEARCH" or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Untrusted comparison")
    seen=set()
    for row in board.get("rows",[]):
        key=(str(row["game_id"]),row["provider"])
        if key in seen:raise ValueError("Duplicate provider-game comparison")
        seen.add(key)
        if row.get("status")!="FROZEN_RESEARCH_COMPARISON_NOT_BETTING_VALIDATED":
            raise ValueError("Untrusted comparison status")
        market=parse_time(row["market_observed_utc"])
        forecast=parse_time(row["forecast_observed_utc"])
        kickoff=parse_time(row["kickoff_utc"])
        if not market<=forecast<kickoff:raise ValueError("Market/forecast chronology invalid")
        if row["ats_selection"]!="PASS" and row.get("market_home_spread") is None:
            raise ValueError("ATS without line")
        if row["total_selection"]!="PASS" and row.get("market_total") is None:
            raise ValueError("Total without line")
    return True

def persist(board,run_id):
    validate(board)
    if not str(run_id).isdigit():raise ValueError("Numeric GitHub run required")
    if store.branch_head() is None:raise ValueError("Missing archive branch")
    path=ROOT+"/run-"+str(run_id)+".json.gz"
    packed=store.pack(board)
    old=store.get_blob_file(path)
    if old is not None:
        if old!=packed:raise ValueError("Immutable comparison collision")
        return {"status":"ALREADY_ARCHIVED","path":path}
    raw=store.get_blob_file(INDEX)
    index=json.loads(raw) if raw else {"status":"RESEARCH_ONLY","runs":[]}
    if index.get("status")!="RESEARCH_ONLY" or not isinstance(index.get("runs"),list):
        raise ValueError("Invalid comparison index")
    if any(x["run_id"]==str(run_id) for x in index["runs"]):
        raise ValueError("Conflicting archived comparison run")
    index["runs"].append({"run_id":str(run_id),"path":path,
        "sha256":hashlib.sha256(store.encode(board)).hexdigest(),
        "matched_provider_games":board["summary"]["matched_provider_games"],
        "ats_comparable":board["summary"]["ats_comparable"],
        "totals_comparable":board["summary"]["totals_comparable"]})
    _commit_material({path:packed,INDEX:store.encode(index)},str(run_id))
    return {"status":"ARCHIVED","path":path,"summary":board["summary"]}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--comparison",required=True)
    a=p.parse_args()
    board=json.loads(Path(a.comparison).read_text())
    print(json.dumps(persist(board,os.environ.get("GITHUB_RUN_ID",""))))

"""Milestone 2: match frozen market boards to independently archived observed finals.

No score grading, no retroactive picks, and no inferred kickoff corrections.
"""
import argparse,datetime as dt,hashlib,json,os
from collections import Counter
from pathlib import Path
from scripts import context_archive as store
from scripts.free_market_comparison_archive import INDEX as MARKET_INDEX,validate as verify_board
from scripts.personnel_results_archive import OUTCOMES,_valid_index
from scripts.personnel_archive_dataset import _check_label,safe_path
from scripts.game_context import parse_time

def match(boards, outcome_index, finals, asof):
    _valid_index(outcome_index,"outcome")
    cutoff=parse_time(asof)
    if set(finals)!={x["archive_path"] for x in outcome_index["games"].values()}:
        raise ValueError("Final archive set differs from verified index")
    for gid,meta in outcome_index["games"].items():
        path=meta["archive_path"];safe_path(path,False)
        final=finals[path]
        if str(final["game_id"])!=str(gid):raise ValueError("Final game ID mismatch")
        for k in ("home","away","home_score","away_score"):
            if str(final[k])!=str(meta[k]):raise ValueError("Final index identity/score mismatch")
        if parse_time(final["kickoff_utc"])!=parse_time(meta["kickoff_utc"]):
            raise ValueError("Final kickoff/index mismatch")
        _check_label(path,final,meta,meta["selected_pregame"],cutoff)
    rows=[];counts=Counter()
    for run_id,board in sorted(boards.items()):
        verify_board(board)
        for r in board["rows"]:
            gid=str(r["game_id"])
            result={"forecast_run_id":str(run_id),"game_id":gid,
                "provider":r["provider"],"home":r["home"],"away":r["away"],
                "kickoff_utc":r["kickoff_utc"],
                "market_observed_utc":r["market_observed_utc"],
                "forecast_observed_utc":r["forecast_observed_utc"],
                "ats_selection":r["ats_selection"],"total_selection":r["total_selection"],
                "market_home_spread":r["market_home_spread"],"market_total":r["market_total"]}
            meta=outcome_index["games"].get(gid)
            if meta is None:
                status="AWAITING_VERIFIED_FINAL"
            else:
                f=finals[meta["archive_path"]]
                if (f["home"],f["away"])!=(r["home"],r["away"]):
                    status="IDENTITY_MISMATCH"
                elif parse_time(f["kickoff_utc"])!=parse_time(r["kickoff_utc"]):
                    status="KICKOFF_CHANGED_NO_AUTOMATIC_MATCH"
                elif parse_time(f["observed_at_utc"])>cutoff or parse_time(f["outcome_known_at_utc"])>cutoff:
                    status="FINAL_NOT_YET_OBSERVED"
                else:
                    status="MATCHED_VERIFIED_FINAL"
                    result.update({"final_archive_path":meta["archive_path"],
                        "final_record_sha256":meta["record_sha256"],
                        "final_observed_at_utc":f["observed_at_utc"],
                        "home_score":f["home_score"],"away_score":f["away_score"]})
            result["status"]=status;counts[status]+=1;rows.append(result)
    return {"status":"VERIFIED_MARKET_FINAL_MATCH_RESEARCH_ONLY",
        "asof_utc":cutoff.isoformat(),"rows":rows,"summary":{"total":len(rows),**dict(counts)},
        "betting_status":"PASS_UNVALIDATED","safe_for_betting":False}

def read_and_match():
    raw=store.get_blob_file(MARKET_INDEX)
    if raw is None:raise ValueError("Missing archived market comparisons")
    index=json.loads(raw)
    if index.get("status")!="RESEARCH_ONLY" or not isinstance(index.get("runs"),list):
        raise ValueError("Invalid comparison index")
    boards={}
    for entry in index["runs"]:
        rid=str(entry["run_id"]);path=entry["path"]
        if not rid.isdigit() or path!="research_2026/free_market_comparisons/run-"+rid+".json.gz" or rid in boards:
            raise ValueError("Invalid comparison index entry")
        blob=store.get_blob_file(path)
        if blob is None:raise ValueError("Missing archived comparison")
        board=store.unpack(blob)
        if hashlib.sha256(store.encode(board)).hexdigest()!=entry["sha256"]:
            raise ValueError("Archived market comparison SHA mismatch")
        verify_board(board)
        if board["summary"]!={k:entry[k] for k in (
            "matched_provider_games","ats_comparable","totals_comparable")}:
            raise ValueError("Archived comparison counts mismatch")
        boards[rid]=board
    raw=store.get_blob_file(OUTCOMES)
    if raw is None:raise ValueError("Missing observed final index")
    outcomes=json.loads(raw);_valid_index(outcomes,"outcome")
    finals={}
    for item in outcomes["games"].values():
        path=item["archive_path"];safe_path(path,False)
        blob=store.get_blob_file(path)
        if blob is None:raise ValueError("Missing observed final")
        finals[path]=store.unpack(blob)
    return match(boards,outcomes,finals,dt.datetime.now(dt.timezone.utc).isoformat())

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    args=p.parse_args();result=read_and_match()
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result["summary"]))

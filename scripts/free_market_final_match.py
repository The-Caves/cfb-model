"""Milestone 2: match frozen market boards to independently archived observed finals.

No score grading, no retroactive picks, and no inferred kickoff corrections.
"""
import argparse,datetime as dt,hashlib,json,os
from collections import Counter
from pathlib import Path
from scripts import context_archive as store
from scripts.free_market_comparison_archive import INDEX as MARKET_INDEX,validate as verify_board
from scripts.market_finals_archive import INDEX as FINAL_INDEX,verify as verify_final_index
from scripts.game_context import parse_time

def match(boards, outcome_index, finals, asof):
    verify_final_index(outcome_index)
    cutoff=parse_time(asof)
    if set(finals)!={x["path"] for x in outcome_index["games"].values()}:
        raise ValueError("Final archive set differs from independent index")
    for gid,meta in outcome_index["games"].items():
        final=finals[meta["path"]]
        if (final.get("status")!="OBSERVED_INDEPENDENT_MARKET_FINAL" or
            final.get("season")!=2026 or final.get("safe_for_betting") is not False or
            final.get("betting_status")!="PASS_UNVALIDATED" or
            str(final.get("game_id"))!=str(gid)):
            raise ValueError("Invalid independently observed final")
        if hashlib.sha256(store.encode(final)).hexdigest()!=meta["sha256"]:
            raise ValueError("Independent final checksum mismatch")
        for k in ("home","away","home_score","away_score"):
            if final[k]!=meta[k]:raise ValueError("Final index identity/score mismatch")
        if parse_time(final["kickoff_utc"])!=parse_time(meta["kickoff_utc"]):
            raise ValueError("Final kickoff/index mismatch")
        kickoff=parse_time(final["kickoff_utc"])
        known=parse_time(final["outcome_known_at_utc"])
        observed=parse_time(final["observed_at_utc"])
        if not kickoff<known<=observed or observed>cutoff:
            raise ValueError("Invalid final chronology")
        if (len(final.get("scoreboard_sha256",""))!=64 or
            final.get("source_url")!="https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"):
            raise ValueError("Unverifiable final provenance")
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
                f=finals[meta["path"]]
                if (f["home"],f["away"])!=(r["home"],r["away"]):
                    status="IDENTITY_MISMATCH"
                elif parse_time(f["kickoff_utc"])!=parse_time(r["kickoff_utc"]):
                    status="KICKOFF_CHANGED_NO_AUTOMATIC_MATCH"
                elif parse_time(f["observed_at_utc"])>cutoff or parse_time(f["outcome_known_at_utc"])>cutoff:
                    status="FINAL_NOT_YET_OBSERVED"
                else:
                    status="MATCHED_VERIFIED_FINAL"
                    result.update({"final_archive_path":meta["archive_path"],
                        "final_record_sha256":meta["sha256"],
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
    raw=store.get_blob_file(FINAL_INDEX)
    if raw is None:raise ValueError("Missing independent observed final index")
    outcomes=json.loads(raw);verify_final_index(outcomes)
    finals={}
    for item in outcomes["games"].values():
        path=item["path"]
        blob=store.get_blob_file(path)
        if blob is None:raise ValueError("Missing independent observed final")
        finals[path]=store.unpack(blob)
    return match(boards,outcomes,finals,dt.datetime.now(dt.timezone.utc).isoformat())

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    args=p.parse_args();result=read_and_match()
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result["summary"]))

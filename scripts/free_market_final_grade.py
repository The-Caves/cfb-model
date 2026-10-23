"""Milestone 3: settle ONLY previously verified, point-in-time market matches.

Research grades are not wagers or evidence of realized betting returns.
"""
import argparse,json,math
from collections import Counter
from pathlib import Path
from scripts.market_settlement import exact_score

def outcome(value):
    if not math.isfinite(value):raise ValueError("Nonfinite settlement")
    return "WIN" if value>0 else "LOSS" if value<0 else "PUSH"

def settle(board):
    if (board.get("status")!="VERIFIED_MARKET_FINAL_MATCH_RESEARCH_ONLY" or
        board.get("safe_for_betting") is not False or
        board.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Untrusted verified matching report")
    results=[];counts=Counter();seen=set()
    for r in board["rows"]:
        key=(str(r["forecast_run_id"]),str(r["game_id"]),r["provider"])
        if key in seen:raise ValueError("Duplicate run/game/provider grade")
        seen.add(key)
        status=r["status"]
        row={"forecast_run_id":key[0],"game_id":key[1],"provider":key[2],
             "match_status":status,"ats":None,"total":None,
             "betting_status":"PASS_UNVALIDATED"}
        if status=="MATCHED_VERIFIED_FINAL":
            for k in ("final_archive_path","final_record_sha256","final_observed_at_utc"):
                if not r.get(k):raise ValueError("Missing verified final provenance")
                row[k]=r[k]
            h=exact_score(r["home_score"]);a=exact_score(r["away_score"])
            row["home_score"]=h;row["away_score"]=a
            spread=r.get("market_home_spread");total=r.get("market_total")
            ats=r["ats_selection"];ou=r["total_selection"]
            if ats not in ("HOME","AWAY","PASS") or ou not in ("OVER","UNDER","PASS"):
                raise ValueError("Invalid frozen selection")
            if ats!="PASS":
                if type(spread) not in (int,float) or not math.isfinite(spread):
                    raise ValueError("ATS selection missing finite spread")
                value=h-a+spread
                row["ats"]=outcome(value if ats=="HOME" else -value)
            if ou!="PASS":
                if type(total) not in (int,float) or not math.isfinite(total) or not 0<total<150:
                    raise ValueError("Total selection missing valid total")
                value=h+a-total
                row["total"]=outcome(value if ou=="OVER" else -value)
            row["status"]="SETTLED_VERIFIED_RESEARCH_ONLY"
        elif status in ("AWAITING_VERIFIED_FINAL","IDENTITY_MISMATCH",
                        "KICKOFF_CHANGED_NO_AUTOMATIC_MATCH","FINAL_NOT_YET_OBSERVED"):
            row["status"]="NOT_GRADED"
        else:raise ValueError("Unknown match status")
        for market in ("ats","total"):
            counts[market+"_"+(row[market] or "NOT_GRADED")]+=1
        counts[row["status"]]+=1
        results.append(row)
    return {"status":"VERIFIED_PROSPECTIVE_MARKET_GRADES_RESEARCH_ONLY",
            "asof_utc":board["asof_utc"],"rows":results,
            "summary":{"total_provider_game_forecasts":len(results),**dict(counts)},
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
            "profitability_calculated":False}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--matches",required=True)
    p.add_argument("--output",required=True);args=p.parse_args()
    board=json.loads(Path(args.matches).read_text())
    result=settle(board);out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result["summary"]))

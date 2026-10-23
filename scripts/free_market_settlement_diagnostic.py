"""Classify pending frozen research comparisons without inventing final scores."""
import argparse,csv,datetime as dt,json
from collections import Counter
from pathlib import Path
from scripts.game_context import parse_time

def diagnose(matches, completed, asof):
    cutoff=parse_time(asof)
    observed={str(g["game_id"]):g for g in completed}
    groups={}
    for row in matches["rows"]:
        gid=str(row["game_id"])
        key=(gid,row["home"],row["away"],row["kickoff_utc"])
        groups.setdefault(key,[]).append(row)
    counts=Counter();records=[]
    for (gid,home,away,kickoff),rows in sorted(groups.items()):
        start=parse_time(kickoff)
        if all(r["status"]=="MATCHED_VERIFIED_FINAL" for r in rows):
            status="MATCHED_VERIFIED_FINAL"
        elif any(r["status"] in ("IDENTITY_MISMATCH","KICKOFF_CHANGED_NO_AUTOMATIC_MATCH") for r in rows):
            status="ARCHIVED_FINAL_MISMATCH"
        elif gid in observed:
            actual=observed[gid]
            status=("COMPLETED_NOT_ARCHIVED" if
                    (actual["home"],actual["away"],parse_time(actual["kickoff_utc"]))==
                    (home,away,start) else "COMPLETED_LEDGER_IDENTITY_MISMATCH")
        elif start>cutoff:
            status="NOT_KICKED_OFF"
        else:
            status="KICKED_OFF_NO_COMPLETED_LEDGER_RESULT"
        counts[status]+=1
        records.append({"game_id":gid,"home":home,"away":away,"kickoff_utc":kickoff,
                        "status":status,"comparison_rows":len(rows)})
    return {"status":"RESEARCH_ONLY_SETTLEMENT_DIAGNOSTIC",
            "asof_utc":cutoff.isoformat(),"unique_games":len(records),
            "comparison_rows":sum(len(v) for v in groups.values()),
            "counts":dict(counts),"games":records,"safe_for_betting":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--matches",required=True)
    p.add_argument("--games",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    matches=json.loads(Path(a.matches).read_text())
    if matches.get("status")!="VERIFIED_MARKET_FINAL_MATCH_RESEARCH_ONLY":
        raise ValueError("Unverified market match input")
    with open(a.games,newline="") as f: completed=list(csv.DictReader(f))
    result=diagnose(matches,completed,dt.datetime.now(dt.timezone.utc).isoformat())
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="games"}))
    if result["counts"].get("COMPLETED_NOT_ARCHIVED",0):
        raise ValueError("Completed market games were not archived: inspect diagnostic artifact")

if __name__=="__main__":main()

"""Research-only pregame market comparison and postgame grading.

No synthetic lines, no retrospectively created forecasts, no betting claims.
"""
import argparse,csv,json,math
from pathlib import Path
from scripts.game_context import parse_time
from scripts.market_settlement import exact_score

def compare(forecast, snapshots):
    record=forecast.get("record",forecast)
    games={str(g["game_id"]):g for g in record["games"]}
    observations={}
    for snapshot in snapshots:
        for q in snapshot.get("quotes",[]):
            gid=str(q["game_id"])
            g=games.get(gid)
            if g is None or (q["home"],q["away"])!=(g["home"],g["away"]):
                continue
            observed=parse_time(q["retrieved_at_utc"])
            if observed>=parse_time(g["kickoff_utc"]) or observed<parse_time(g["forecast_observed_utc"]):
                continue
            if q.get("source")!="ESPN_SCOREBOARD" or not q.get("provider"):
                continue
            key=(gid,q["provider"])
            if key not in observations or observed>parse_time(observations[key]["retrieved_at_utc"]):
                observations[key]=q
    rows=[]
    for (gid,provider),q in sorted(observations.items()):
        g=games[gid];p=g["projection"]
        margin=p["predicted_home_margin"];total=p["predicted_total_points"]
        spread=q.get("market_home_spread")
        market_total=q.get("total_points")
        valid_spread=(q.get("spread_semantics")=="EXPLICIT_FAVORITE_FLAGS" and
                      type(spread) in (int,float) and math.isfinite(spread))
        valid_total=type(market_total) in (int,float) and math.isfinite(market_total) and 0<market_total<150
        rows.append({
            "game_id":gid,"home":g["home"],"away":g["away"],"kickoff_utc":g["kickoff_utc"],
            "forecast_observed_utc":g["forecast_observed_utc"],
            "market_observed_utc":q["retrieved_at_utc"],"provider":provider,
            "model_home_margin":margin,"model_total":total,
            "market_home_spread":spread if valid_spread else None,
            "market_total":market_total if valid_total else None,
            "ats_selection":("HOME" if margin+spread>0 else "AWAY" if margin+spread<0 else "PASS")
                if margin is not None and valid_spread else "PASS",
            "total_selection":("OVER" if total>market_total else "UNDER" if total<market_total else "PASS")
                if total is not None and valid_total else "PASS",
            "status":"FROZEN_RESEARCH_COMPARISON_NOT_BETTING_VALIDATED"})
    return {"status":"PROSPECTIVE_MARKET_RESEARCH","rows":rows,"betting_status":"PASS_UNVALIDATED",
            "summary":{"matched_provider_games":len(rows),
                       "ats_comparable":sum(r["ats_selection"]!="PASS" for r in rows),
                       "totals_comparable":sum(r["total_selection"]!="PASS" for r in rows)}}

def grade(board,finals,finals_retrieved_at_utc):
    observed=parse_time(finals_retrieved_at_utc)
    indexed={str(f["game_id"]):f for f in finals}
    rows=[]
    for r in board["rows"]:
        f=indexed.get(str(r["game_id"]))
        if f is None:continue
        if observed<=parse_time(r["kickoff_utc"]):continue
        if (f["home"],f["away"])!=(r["home"],r["away"]):continue
        if abs((parse_time(f["kickoff_utc"])-parse_time(r["kickoff_utc"])).total_seconds())>900:continue
        h=exact_score(f["home_score"]);a=exact_score(f["away_score"])
        def outcome(value):
            return "WIN" if value>0 else "LOSS" if value<0 else "PUSH"
        ats=None;tot=None
        if r["ats_selection"]!="PASS":
            v=h-a+r["market_home_spread"]
            ats=outcome(v if r["ats_selection"]=="HOME" else -v)
        if r["total_selection"]!="PASS":
            v=h+a-r["market_total"]
            tot=outcome(v if r["total_selection"]=="OVER" else -v)
        rows.append({"game_id":r["game_id"],"provider":r["provider"],"ats":ats,"total":tot,
                     "status":"OBSERVED_FINAL_RESEARCH_GRADE"})
    return {"status":"PROSPECTIVE_MARKET_RESEARCH_GRADE","rows":rows,
            "betting_status":"PASS_UNVALIDATED"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--forecast",required=True)
    p.add_argument("--market-dir",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--finals")
    p.add_argument("--finals-observed")
    a=p.parse_args()
    forecast=json.loads(Path(a.forecast).read_text())
    snapshots=[json.loads(f.read_text()) for f in sorted(Path(a.market_dir).glob("*.json"))]
    board=compare(forecast,snapshots)
    if a.finals or a.finals_observed:
        if not a.finals or not a.finals_observed:raise ValueError("Both finals inputs required")
        with Path(a.finals).open(newline="") as stream:finals=list(csv.DictReader(stream))
        board["grading"]=grade(board,finals,a.finals_observed)
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(board,indent=2,allow_nan=False)+"\n")
    print(json.dumps(board["summary"]))

if __name__=="__main__":main()

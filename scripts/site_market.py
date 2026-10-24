"""Join observed free ESPN pregame markets to independently frozen model research.

Market quotes can be newer than a frozen score forecast. They are explicitly
labeled *observed at build time*, never rewritten into the original forecast
snapshot or used for historic claims. No odds are synthesized or paid for.
"""
import argparse
import datetime as dt
import json
import math
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.free_market_capture import BASE, normalize
from scripts.game_context import parse_time

EASTERN=ZoneInfo("America/New_York")
MAX_DATES=15
SOURCE="ESPN_SCOREBOARD_FREE"
STATUS="FREE_ESPN_MARKET_RESEARCH_NOT_BETTING_VALIDATED"

def valid_number(n):
    return type(n) in (int,float) and math.isfinite(n)

def quote_selection(dashboard, snapshots, now):
    if dashboard.get("schema_version")!=2 or dashboard.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Invalid dashboard model clearance")
    indexed={}
    for snapshot in snapshots:
        if snapshot.get("source")!=SOURCE or snapshot.get("paid_api_calls")!=0:
            raise ValueError("Untrusted or paid quote feed")
        observed=parse_time(snapshot["observed_at_utc"])
        if observed>now:
            raise ValueError("Market observation is from the future")
        for q in snapshot.get("quotes",[]):
            if q.get("source")!="ESPN_SCOREBOARD" or not q.get("provider"):
                continue
            if parse_time(q["retrieved_at_utc"])!=observed:
                continue
            indexed.setdefault(str(q["game_id"]),[]).append(q)
    captured=0;spreads=0;totals=0
    for game in dashboard["games"]:
        # The model itself remains frozen. This is a conditional *current quote*
        # comparison, not a historically authenticated as-of-model price.
        game.update({"market_home_spread":None,"market_total":None,
            "market_provider":None,"market_observed_utc":None,
            "market_status":"NO_OBSERVED_VALID_PREGAME_QUOTE",
            "model_ats_side":None,"model_ou_side":None,
            "ats_edge_points":None,"ou_edge_points":None})
        kickoff=parse_time(game["kickoff_utc"])
        candidates=[]
        for q in indexed.get(str(game["game_id"]),[]):
            when=parse_time(q["retrieved_at_utc"])
            if (when>=kickoff or when>now or q.get("home")!=game["home_team"]
                or q.get("away")!=game["away_team"]
                or abs((parse_time(q["kickoff_utc"])-kickoff).total_seconds())>900):
                continue
            spread=q.get("market_home_spread")
            total=q.get("total_points")
            spread_ok=(q.get("spread_semantics")=="EXPLICIT_FAVORITE_FLAGS"
                       and valid_number(spread) and abs(spread)<80)
            total_ok=valid_number(total) and 0<total<150
            if not spread_ok and not total_ok:
                continue
            candidates.append((q,spread if spread_ok else None,
                               total if total_ok else None))
        if not candidates:
            continue
        # Newest available quote, deterministic provider tie-break. Do not
        # synthesize spread from one provider and total from another.
        candidates.sort(key=lambda t:(parse_time(t[0]["retrieved_at_utc"]),
                                         str(t[0]["provider"])))
        q,spread,total=candidates[-1]
        game.update({"market_home_spread":spread,"market_total":total,
            "market_provider":str(q["provider"]),
            "market_observed_utc":q["retrieved_at_utc"],
            "market_status":STATUS})
        captured+=1
        margin=game["model_home_margin"]
        predicted_total=game["model_total"]
        if valid_number(spread) and valid_number(margin):
            diff=margin+spread # model home margin vs home handicap
            game["ats_edge_points"]=round(abs(diff),4)
            game["model_ats_side"]="HOME" if diff>0 else "AWAY" if diff<0 else "PASS"
            spreads+=1
        if valid_number(total) and valid_number(predicted_total):
            diff=predicted_total-total
            game["ou_edge_points"]=round(abs(diff),4)
            game["model_ou_side"]="OVER" if diff>0 else "UNDER" if diff<0 else "PASS"
            totals+=1
    dashboard["market_display"]={
        "status":STATUS,"source":"ESPN scoreboard public observed odds",
        "historical_publication_authenticated":False,
        "same_time_as_model_forecast":False,
        "matched_games":captured,"usable_spreads":spreads,"usable_totals":totals,
        "comparison_warning":"Directional research comparisons to current observed lines, not validated ATS/O-U bets. Published-time provenance is not independently attested."}
    return dashboard

def fetch_day(day, now, opener=urllib.request.urlopen):
    url=BASE+"?dates="+day.strftime("%Y%m%d")+"&limit=500&groups=80"
    request=urllib.request.Request(url,headers={
        "User-Agent":"cfb-model-research/0.2","Accept":"application/json"})
    with opener(request,timeout=12) as response:
        payload=json.load(response)
    return normalize(payload,now.isoformat())

def enrich(path,now=None,fetcher=fetch_day):
    now=now or dt.datetime.now(dt.timezone.utc)
    file=Path(path)
    dashboard=json.loads(file.read_text())
    days=sorted(set(parse_time(g["kickoff_utc"]).astimezone(EASTERN).date()
                    for g in dashboard["games"]))[:MAX_DATES]
    snapshots=[];errors=[]
    for day in days:
        try:
            snapshots.append(fetcher(day,now))
        except Exception as exc:
            errors.append({"day":day.isoformat(),"reason":type(exc).__name__})
    result=quote_selection(dashboard,snapshots,now)
    result["market_display"]["dates_requested"]=len(days)
    result["market_display"]["successful_dates"]=len(snapshots)
    result["market_display"]["failed_dates"]=errors
    # Never overwrite a validated model export if this output is malformed.
    file.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result["market_display"]))
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--dashboard",required=True)
    args=parser.parse_args()
    enrich(args.dashboard)

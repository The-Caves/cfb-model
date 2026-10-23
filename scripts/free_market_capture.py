"""Free, best-effort ESPN scoreboard market observations (no paid API).

Only capture explicitly published pregame lines. Never infer bookmaker, opening
line, closing line, or publication time. Source is ESPN's scoreboard API.
"""
import argparse
import datetime as dt
import json
import urllib.request
from pathlib import Path
from scripts.game_context import parse_time

BASE="https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"

def normalize(payload, retrieved_at_utc):
    observed=parse_time(retrieved_at_utc)
    if not isinstance(payload,dict) or not isinstance(payload.get("events"),list):
        raise ValueError("Missing ESPN scoreboard events")
    rows=[];quarantined=[]
    for event in payload["events"]:
        if not isinstance(event,dict):continue
        gid=str(event.get("id",""))
        try:
            kickoff=parse_time(event["date"])
            competition=event["competitions"][0]
            sides=competition["competitors"]
            home=next(x["team"]["displayName"] for x in sides if x["homeAway"]=="home")
            away=next(x["team"]["displayName"] for x in sides if x["homeAway"]=="away")
            if not gid or not home or not away or observed>=kickoff:
                continue
            offers=competition.get("odds") or []
            if not isinstance(offers,list):raise ValueError("Malformed odds field")
            for offer in offers:
                if not isinstance(offer,dict):continue
                # ESPN's 'details' (e.g. TEAM -3.5) is descriptive only;
                # require numeric spread and total fields for trusted capture.
                spread=offer.get("spread")
                total=offer.get("overUnder")
                if type(spread) not in (int,float) and type(total) not in (int,float):
                    continue
                provider=offer.get("provider") or {}
                provider_name=provider.get("name") if isinstance(provider,dict) else None
                if not provider_name:
                    quarantined.append({"game_id":gid,"reason":"MISSING_PROVIDER"})
                    continue
                # ESPN spread is commonly an unsigned favorite handicap.
                # It is NOT necessarily the signed home-team spread.
                rows.append({
                    "game_id":gid,"home":home,"away":away,
                    "kickoff_utc":kickoff.isoformat(),
                    "retrieved_at_utc":observed.isoformat(),
                    "source":"ESPN_SCOREBOARD",
                    "provider":provider_name,
                    "raw_spread":spread if type(spread) in (int,float) else None,
                    "raw_total":total if type(total) in (int,float) else None,
                    "spread_semantics":"UNVERIFIED_DO_NOT_GRADE_ATS",
                    "market_home_spread":None,
                    "total_points":total if type(total) in (int,float) and 0<total<150 else None,
                    "source_publication_time_verified":False
                })
        except (KeyError,IndexError,StopIteration,TypeError,ValueError) as exc:
            quarantined.append({"game_id":gid,"reason":type(exc).__name__})
    return {"schema_version":1,"observed_at_utc":observed.isoformat(),
            "source":"ESPN_SCOREBOARD_FREE","status":"RESEARCH_MARKET_OBSERVATION_ONLY",
            "quotes":rows,"quarantined":quarantined,"paid_api_calls":0}

def capture(day,output):
    if not isinstance(day,dt.date):raise TypeError("day must be a date")
    url=BASE+"?dates="+day.strftime("%Y%m%d")+"&limit=500&groups=80"
    req=urllib.request.Request(url,headers={"User-Agent":"cfb-model-research/0.2","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as response:
        payload=json.load(response)
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    result=normalize(payload,now)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError("Refusing to overwrite market snapshot")
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return {"quotes":len(result["quotes"]),"quarantined":len(result["quarantined"]),
            "paid_api_calls":0,"output":str(path)}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--date",default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(capture(dt.date.fromisoformat(a.date),a.output)))

"""Fetch timestamped ESPN CFB scoreboard data. Public feed; verify source coverage."""
import argparse,csv,datetime,json,time,urllib.request
from pathlib import Path
URL="https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
def fetch_day(day):
    url=URL+"?dates="+day.strftime("%Y%m%d")+"&limit=500&groups=80"
    req=urllib.request.Request(url,headers={"User-Agent":"cfb-model-research/0.1","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as res:payload=json.load(res)
    if not isinstance(payload.get("events"),list):raise RuntimeError("Missing ESPN events")
    return payload
def parse_event(event):
    competitions=event.get("competitions") or []
    if not competitions:return None
    c=competitions[0];teams=c.get("competitors") or []
    home=next((x for x in teams if x.get("homeAway")=="home"),None)
    away=next((x for x in teams if x.get("homeAway")=="away"),None)
    if not home or not away:return None
    status=event.get("status",{}).get("type",{})
    if not status.get("completed"):return None
    try:hs=int(home["score"]);a=int(away["score"])
    except (KeyError,ValueError,TypeError):return None
    return {"game_id":str(event["id"]),"date":event["date"][:10],
       "away":away.get("team",{}).get("displayName",""),"home":home.get("team",{}).get("displayName",""),
       "away_score":a,"home_score":hs,"neutral":bool(c.get("neutralSite",False))}
def ingest(start,end,output):
    if end>datetime.date.today():end=datetime.date.today()
    if end<start:raise ValueError("end before start")
    output.mkdir(parents=True,exist_ok=True)
    raw=output/"raw";raw.mkdir(exist_ok=True)
    games={};failures=[];day=start;calls=0
    while day<=end:
        try:
            payload=fetch_day(day);calls+=1
            (raw/(day.isoformat()+".json")).write_text(json.dumps({"retrieved_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"payload":payload}))
            for e in payload["events"]:
                r=parse_event(e)
                if r and r["away"] and r["home"]:games[r["game_id"]]=r
        except Exception as exc:failures.append({"date":str(day),"error":str(exc)})
        day+=datetime.timedelta(days=1)
        time.sleep(.05)
    fields=["game_id","date","away","home","away_score","home_score","neutral"]
    with (output/"games_2026.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        w.writerows(sorted(games.values(),key=lambda x:(x["date"],x["game_id"])))
    manifest={"retrieved_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "requested_start":str(start),"requested_end":str(end),"days_fetched":calls,
        "completed_games":len(games),"failures":failures,
        "status":"SUCCESS" if games and not failures else "INCOMPLETE"}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))
    if manifest["status"]!="SUCCESS":raise SystemExit(2)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2026-08-01");p.add_argument("--end",default=datetime.date.today().isoformat())
    p.add_argument("--output",default="data");a=p.parse_args()
    ingest(datetime.date.fromisoformat(a.start),datetime.date.fromisoformat(a.end),Path(a.output))

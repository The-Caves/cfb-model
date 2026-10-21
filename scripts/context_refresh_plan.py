"""Select baseline/dense kickoff-aware context refreshes from live ESPN schedules."""
import argparse,datetime as dt,json,os,urllib.parse,urllib.request
from scripts.game_context import ET,UTC,extract_game,parse_time
BASELINE_HOURS={10,16,23}
def decide(issue,games,force=False,healthy=True):
    if force:return {"run":True,"reason":"manual_or_explicit_test","horizon_days":10}
    hours=[(parse_time(g["kickoff_utc"])-issue).total_seconds()/3600 for g in games
           if not g["completed"] and parse_time(g["kickoff_utc"])>issue]
    nearest=min(hours,default=None)
    if issue.hour in BASELINE_HOURS:return {"run":True,"reason":"baseline_three_times_daily","horizon_days":10,"hours_to_next_kickoff":nearest}
    if nearest is not None and nearest<=12:return {"run":True,"reason":"within_12_hours_hourly","horizon_days":10,"hours_to_next_kickoff":nearest}
    if nearest is not None and nearest<=48 and issue.hour%3==0:
        return {"run":True,"reason":"within_48_hours_every_three_hours","horizon_days":10,"hours_to_next_kickoff":nearest}
    if not healthy:return {"run":True,"reason":"schedule_check_failed_fails_open","horizon_days":10}
    return {"run":False,"reason":"not_due","horizon_days":10,"hours_to_next_kickoff":nearest}

def lookup(issue):
    start=issue.astimezone(ET).date();games={};errors=[]
    for n in range(4):
        day=start+dt.timedelta(days=n)
        if day.year!=2026:continue
        url=("https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?"
             +urllib.parse.urlencode({"dates":day.strftime("%Y%m%d"),"groups":80,"limit":500}))
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"cfb-context-plan/0.1"})
            with urllib.request.urlopen(req,timeout=10) as stream:
                payload=json.load(stream)
            if not isinstance(payload.get("events"),list):raise ValueError("Missing events")
            for raw in payload["events"]:
                item=extract_game(raw)
                if item:games[item["game_id"]]=item
        except Exception as e:errors.append({"day":str(day),"error":str(e)[:180]})
    return list(games.values()),errors

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--force",action="store_true")
    p.add_argument("--now",default=None)
    p.add_argument("--output",default="data/context_refresh_plan.json")
    a=p.parse_args()
    issue=parse_time(a.now) if a.now else dt.datetime.now(UTC)
    games,errors=([],[]) if a.force else lookup(issue)
    decision=decide(issue,games,a.force,not errors)
    decision["planned_at_utc"]=issue.isoformat()
    decision["schedule_probe_errors"]=errors
    from pathlib import Path
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(decision,indent=2)+"\n")
    with open(os.environ.get("GITHUB_OUTPUT","/dev/null"),"a") as f:
        f.write("run="+str(decision["run"]).lower()+"\n")
        f.write("horizon="+str(decision["horizon_days"])+"\n")
    print(json.dumps(decision,indent=2))

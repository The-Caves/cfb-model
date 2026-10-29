"""Sourced 2026 team turnovers: ESPN boxscore only, not undocumented PBP vectors.

The recorded statistic is the offense team's total turnovers. Its opponent's
takeaways are the same observed events from the other team perspective.
Incomplete, missing or contradictory game reports stay UNKNOWN.
Historical publication timestamps are NOT authenticated for old games.
"""
import argparse,csv,datetime as dt,json,re,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

STATUS="ESPN_COMPLETED_BOXSCORE_TURNOVERS_RESEARCH_ONLY"
URL="https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event="
def fetch(gid):
    if not re.fullmatch(r"\d{6,12}",str(gid)):raise ValueError("Invalid ESPN ID")
    req=urllib.request.Request(URL+str(gid),headers={"User-Agent":"cfb-team-strength-research/0.4",
                                                  "Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=12) as resp:return json.load(resp)
def parse(game,data,observed):
    """Do not guess turnovers from a missing statistic or a single team's row."""
    comp=(data.get("header") or {}).get("competitions") or []
    if not comp:raise ValueError("Missing ESPN game identity")
    first=comp[0]
    sides=first.get("competitors") or []
    if len(sides)!=2:raise ValueError("Missing two ESPN opponents")
    names={s.get("homeAway"):s.get("team",{}).get("displayName") for s in sides}
    if names!={"home":game["home"],"away":game["away"]}:
        raise ValueError("ESPN summary team/side identity mismatch")
    if not first.get("status",{}).get("type",{}).get("completed"):
        raise ValueError("Not an authenticated completed game")
    scores={s.get("homeAway"):int(s.get("score")) for s in sides}
    if scores!={"home":int(game["home_score"]),"away":int(game["away_score"])}:
        raise ValueError("Boxscore final does not match accepted scoreboard")
    boxes=(data.get("boxscore") or {}).get("teams") or []
    if len(boxes)!=2:raise ValueError("No two-sided boxscore")
    results={}
    for item in boxes:
        team=(item.get("team") or {}).get("displayName")
        if team not in (game["home"],game["away"]) or team in results:
            raise ValueError("Boxscore team identity ambiguous")
        values=[x.get("displayValue") for x in item.get("statistics",[])
                if x.get("name")=="turnovers"]
        if len(values)!=1 or not re.fullmatch(r"\d{1,2}",str(values[0])):
            raise ValueError("Turnover count missing or malformed")
        count=int(values[0])
        if count>15:raise ValueError("Unreasonable team turnovers")
        results[team]=count
    if len(results)!=2:raise ValueError("Missing opposing turnover records")
    return [{"game_id":str(game["game_id"]),"date":game["date"],
             "team":team,"opponent":game["away"] if team==game["home"] else game["home"],
             "turnovers_committed":count,
             "takeaways_observed":results[game["away"] if team==game["home"] else game["home"]],
             "source_url":URL+str(game["game_id"]),
             "captured_at_utc":observed,
             "historical_pregame_publication_verified":False,
             "betting_status":"PASS_UNVALIDATED"} for team,count in results.items()]

def collect(games,asof,fetcher=fetch,max_workers=8):
    if len({str(g["game_id"]) for g in games})!=len(games):
        raise ValueError("Duplicate scoreboard")
    rows=[];errors=[]
    def one(game):
        try:return parse(game,fetcher(game["game_id"]),asof),None
        except (OSError,ValueError,KeyError,TypeError,TimeoutError) as e:
            return [],{"game_id":str(game["game_id"]),"reason":type(e).__name__}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for entries,error in executor.map(one,games):
            rows.extend(entries)
            if error:errors.append(error)
    return {"status":STATUS,"season":2026,"captured_at_utc":asof,
            "completed_games_checked":len(games),
            "fully_verified_games":len(rows)//2,"unknown_games":len(errors),
            "errors":errors[:100],"rows":rows,
            "historical_publication_times_verified":False,
            "model_promoted":False,"betting_status":"PASS_UNVALIDATED",
            "safe_for_betting":False}

def run(games_file,output):
    with open(games_file,newline="",encoding="utf-8") as f:games=list(csv.DictReader(f))
    result=collect(games,dt.datetime.now(dt.timezone.utc).isoformat())
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("rows","errors")}))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--games",required=True)
    p.add_argument("--output",required=True);a=p.parse_args();run(a.games,a.output)

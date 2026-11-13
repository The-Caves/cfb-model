"""Source-observed ESPN 2026 possession ledger, including score ownership.

Use completed game drive/plays evidence, never synthesize drives from a final.
All historical game-data publication times remain RETROSPECTIVE/UNVERIFIED.
Scoring on turnovers is attributed to DEFENSE, not the possessing offense.
"""
import argparse
import csv
import datetime as dt
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from scripts.turnover_boxscore import fetch as espn_fetch,parse as verify_turnovers

STATUS="ESPN_COMPLETED_SOURCE_MATCHED_POSSESSION_RESEARCH_ONLY"
CATEGORIES=("TD","FG","PUNT","INTERCEPTION","FUMBLE","MISSED_FG","DOWNS",
            "END_PERIOD","SAFETY","OTHER")
def _int(value,lo=0,hi=200):
    if type(value) is int: x=value
    elif isinstance(value,str) and value.isdigit():x=int(value)
    else:return None
    return x if lo<=x<=hi else None

def _category(result):
    text=str(result or "").upper().replace("-"," ").strip()
    if not text:return None
    if "INT" in text and "POINT" not in text:return "INTERCEPTION"
    if "FUMBLE" in text:return "FUMBLE"
    if "MISSED" in text and ("FG" in text or "FIELD" in text):return "MISSED_FG"
    if "TOUCHDOWN" in text or re.search(r"\bTD\b",text):return "TD"
    if text.startswith("FG") or "FIELD GOAL" in text:return "FG"
    if "PUNT" in text:return "PUNT"
    if "DOWNS" in text:return "DOWNS"
    if "SAFETY" in text:return "SAFETY"
    if any(x in text for x in ("END","HALF","PERIOD","QUARTER","CLOCK")):
        return "END_PERIOD"
    if any(x in text for x in ("KICKOFF","BLOCKED","OTHER")):return "OTHER"
    return None

def _field_position(drive,team_id):
    # ESPN drive.start.yardLine uses HOME coordinate and cannot be used as
    # offense yards-to-goal: use first offensive scrimmage play's explicit
    # start.yardsToEndzone and possession team instead.
    for play in drive.get("plays") or []:
        start=play.get("start") or {}
        typ=(play.get("type") or {}).get("text","").lower()
        if "kickoff" in typ or "extra point" in typ or "conversion" in typ:
            continue
        team=(start.get("team") or {}).get("id")
        yards=_int(start.get("yardsToEndzone"),0,100)
        if str(team)==str(team_id) and yards is not None:
            return yards
    return None

def _red_zone(drive,team_id):
    for p in drive.get("plays") or []:
        start=p.get("start") or {}
        if str((start.get("team") or {}).get("id"))!=str(team_id):continue
        y=_int(start.get("yardsToEndzone"),0,100)
        if y is not None and y<=20:return True
    return False

def _end_scores(drive):
    scores=[]
    for p in drive.get("plays") or []:
        h=_int(p.get("homeScore"));a=_int(p.get("awayScore"))
        if h is not None and a is not None:scores.append((h,a))
    return scores[-1] if scores else None

def parse(game,payload,captured_at):
    obs=dt.datetime.fromisoformat(str(captured_at).replace("Z","+00:00"))
    if obs.tzinfo is None:raise ValueError("Source capture must have timezone")
    if obs<=dt.datetime.fromisoformat(game["kickoff_utc"].replace("Z","+00:00")):
        raise ValueError("Game not already completed at observation")
    competition=(payload.get("header") or {}).get("competitions") or []
    if len(competition)!=1:raise ValueError("Missing unique ESPN completed fixture")
    comp=competition[0]
    if (comp.get("status") or {}).get("type",{}).get("completed") is not True:
        raise ValueError("Not finished")
    sides=comp.get("competitors") or []
    home=[s for s in sides if s.get("homeAway")=="home"]
    away=[s for s in sides if s.get("homeAway")=="away"]
    if len(home)!=1 or len(away)!=1:raise ValueError("Ambiguous sides")
    h,a=home[0],away[0]
    if (h.get("team",{}).get("displayName")!=game["home"] or
        a.get("team",{}).get("displayName")!=game["away"] or
        _int(h.get("score"))!=int(game["home_score"]) or
        _int(a.get("score"))!=int(game["away_score"])):
        raise ValueError("Mismatch final ESPN identity or score")
    hid=str(h["team"]["id"]);aid=str(a["team"]["id"])
    if not hid or not aid or hid==aid:raise ValueError("Invalid ESPN team IDs")
    drives=(payload.get("drives") or {}).get("previous")
    if not isinstance(drives,list) or not 10<=len(drives)<=60:
        raise ValueError("Missing complete drive ledger")
    box=verify_turnovers(game,payload,captured_at)
    turnover_by={x["team"]:x["turnovers_committed"] for x in box}
    seen=set();records=[];previous=(0,0)
    for d in drives:
        did=str(d.get("id",""))
        if not did or did in seen:raise ValueError("Duplicate drive")
        seen.add(did)
        tid=str((d.get("team") or {}).get("id",""))
        if tid not in (hid,aid):raise ValueError("Drive possession team not in fixture")
        side="home" if tid==hid else "away"
        name=game[side]
        plays=d.get("plays")
        if not isinstance(plays,list) or not plays:raise ValueError("No drive-level play evidence")
        result=_category(d.get("result"))
        if result is None:raise ValueError("Unrecognized drive-ending event: "+str(d.get("result")))
        state=_end_scores(d)
        if state is None:raise ValueError("Drive scores unavailable")
        dh=state[0]-previous[0];da=state[1]-previous[1]
        if dh<0 or da<0 or (dh and da) or max(dh,da)>9:
            raise ValueError("Scores not reconcilable within a possession")
        previous=state
        ytg=_field_position(d,tid)
        if ytg is None:raise ValueError("Offensive starting field position missing")
        offense_points=(dh if side=="home" else da)
        defense_points=(da if side=="home" else dh)
        # Nonoffensive scoring is explicitly separated from this offense's
        # points/drive, not assigned to offense or inferred from isScore.
        if defense_points and result not in ("INTERCEPTION","FUMBLE","OTHER"):
            raise ValueError("Unverified defensive/special teams scoring event")
        if offense_points and result not in ("TD","FG","SAFETY","OTHER"):
            raise ValueError("Unverified possession scoring type")
        turnover=result in ("INTERCEPTION","FUMBLE")
        if turnover and offense_points:raise ValueError("Turnover drive credited with offense points")
        records.append({
            "drive_id":did,"team":name,"side":side,"start_yards_to_goal":ytg,
            "field_zone":"red_zone" if ytg<=20 else "opponent_half" if ytg<=50 else
                          "midfield" if ytg<=60 else "own_half" if ytg<=90 else "own_deep",
            "result":result,"turnover":turnover,
            "offense_points":offense_points,"defense_points":defense_points,
            "red_zone_visited":_red_zone(d,tid),
            "offensive_plays":_int(d.get("offensivePlays"),0,100),
            "yards":d.get("yards") if type(d.get("yards")) is int else None,
            "source_result":str(d.get("result")),
        })
    if previous!=(int(game["home_score"]),int(game["away_score"])):
        raise ValueError("Cumulative drive scoreboard does not match observed final")
    counts={name:sum(r["team"]==name for r in records) for name in (game["home"],game["away"])}
    if any(not 5<=n<=30 for n in counts.values()):
        raise ValueError("Suspiciously incomplete team possession count")
    calc={name:sum(r["turnover"] for r in records if r["team"]==name) for name in counts}
    if calc!=turnover_by:
        raise ValueError("Drive-ending turnovers do not match verified ESPN boxscore: "+str(calc)+" vs "+str(turnover_by))
    for side,side_score in (("home",game["home_score"]),("away",game["away_score"])):
        represented=sum(r["offense_points"] for r in records if r["side"]==side)
        represented+=sum(r["defense_points"] for r in records if r["side"]!=side)
        if represented!=int(side_score):
            raise ValueError("Offensive/defensive scoring ownership does not reconcile")
    return {
      "game_id":str(game["game_id"]),"home":game["home"],"away":game["away"],
      "kickoff_utc":game["kickoff_utc"],"date":game["date"],
      "home_score":int(game["home_score"]),"away_score":int(game["away_score"]),
      "source_url":"https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event="+str(game["game_id"]),
      "source_captured_at_utc":captured_at,
      "historical_pregame_source_availability_verified":False,
      "scoreboard_and_boxscore_reconciled":True,
      "scoring_ownership_verified":True,
      "drives_complete_checked":True,
      "turnovers_verified":turnover_by,"drives":records,
    }

def collect(games,cap=400,workers=8,fetcher=espn_fetch):
    if len({str(g["game_id"]) for g in games})!=len(games):raise ValueError("Duplicate source game IDs")
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    games=sorted(games,key=lambda x:(x["kickoff_utc"],x["game_id"]))[:cap]
    def one(g):
        try:return parse(g,fetcher(g["game_id"]),now),None
        except (OSError,ValueError,KeyError,TypeError,TimeoutError) as err:
            return None,{"game_id":g["game_id"],"reason":type(err).__name__,"detail":str(err)[:170]}
    accepted=[];rejected=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for row,error in pool.map(one,games):
            if row:accepted.append(row)
            else:rejected.append(error)
    return {"status":STATUS,"season":2026,"captured_at_utc":now,
            "historical_pregame_publication_times_verified":False,
            "safe_for_betting":False,"model_promoted":False,
            "betting_status":"PASS_UNVALIDATED",
            "games_checked":len(games),"games_accepted":len(accepted),
            "games_quarantined":len(rejected),"rejected":rejected,
            "games":accepted}

def run(games_csv,output,cap=400,workers=8):
    games=list(csv.DictReader(open(games_csv,encoding="utf-8-sig",newline="")))
    data=collect(games,cap,workers)
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,indent=2)+"\n")
    print(json.dumps({key:data[key] for key in
          ("status","games_checked","games_accepted","games_quarantined")}))
    from collections import Counter
    print("quarantine reasons",dict(Counter(r["detail"] for r in data["rejected"]).most_common(12)))
    return data

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--games",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--cap",type=int,default=400)
    parser.add_argument("--workers",type=int,default=8)
    args=parser.parse_args()
    run(args.games,args.output,args.cap,args.workers)

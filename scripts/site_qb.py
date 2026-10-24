"""Source-labeled QB context for the public research dashboard.

Game-specific reviewed official starters come from immutable as-observed
context-state QB history, never from season stats. ESPN prior-completed-game
passing box scores supply *last-game performers* as secondary context only;
they do NOT identify or confirm a future starting quarterback. The frozen
model prediction and its QB verification counters are never rewritten.
"""
import argparse,concurrent.futures,datetime as dt,json,re,urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from scripts.game_context import parse_time
from scripts.qb_history import verify_observation

BASE="https://site.api.espn.com/apis/site/v2/sports/football/college-football"
STATUS="CURRENT_QB_CONTEXT_UNVALIDATED"
UNKNOWN={"player":None,"status":"UNKNOWN","source_url":None,"observed_at_utc":None,
         "description":"No verified game-specific QB or named passing-leader evidence"}

def fetch_json(url):
    if urlsplit(url).hostname!="site.api.espn.com" or not url.startswith(BASE):
        raise ValueError("Invalid ESPN source")
    req=urllib.request.Request(url,headers={"User-Agent":"CFB-2026-QB-context/0.1","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=8) as r:
        data=r.read(2_000_000+1)
    if len(data)>2_000_000:raise ValueError("Oversized ESPN response")
    return json.loads(data)

def season_passing_leader(data):
    """Read only explicitly named passing-category player; no QB starter claims."""
    for category in data.get("leaders",[]) if isinstance(data.get("leaders"),list) else []:
        key=" ".join(str(category.get(k) or "") for k in ("name","displayName","shortDisplayName")).lower()
        if "pass" not in key:continue
        items=category.get("leaders") or []
        for item in items:
            athlete=item.get("athlete") or {}
            player=athlete.get("displayName") or athlete.get("fullName")
            pos=athlete.get("position") or {}
            # In ambiguous athlete layouts refuse to guess the position.
            if (isinstance(player,str) and 3<=len(player)<=100 and
                not re.search(r"\d",player) and
                (pos.get("abbreviation") in ("QB",None,""))):
                return player.strip()
    return None

def team_ids_from_scoreboard(payload, wanted, now):
    """Exact ESPN matchup and kickoff check before accepting an ESPN team ID."""
    found={}
    for event in payload.get("events",[]):
        gid=str(event.get("id",""))
        match=wanted.get(gid)
        if not match:continue
        if parse_time(event.get("date"))!=parse_time(match["kickoff_utc"]):continue
        if parse_time(match["kickoff_utc"])<=now:continue
        for comp in event.get("competitions",[])[:1]:
            sides=comp.get("competitors",[])
            if len(sides)!=2:continue
            for side in sides:
                team=side.get("team") or {}
                name=team.get("displayName")
                expected=match["home_team"] if side.get("homeAway")=="home" else (
                    match["away_team"] if side.get("homeAway")=="away" else None)
                tid=str(team.get("id") or "")
                if name==expected and tid.isdigit():
                    found[(gid,expected)]=tid
    return found

def confirmed_rows(history, games, now):
    if history is None:return {}
    verify_observation(history)
    observed=parse_time(history["observed_at_utc"])
    if observed>now:raise ValueError("Future QB evidence")
    idx={}
    for row in history["rows"]:
        gid=str(row["game_id"]);g=games.get(gid)
        if not g or parse_time(g["kickoff_utc"])<=now:continue
        team=row["team"]
        if (parse_time(g["kickoff_utc"])!=parse_time(row["kickoff_utc"]) or
            team not in (g["home_team"],g["away_team"]) or
            row["opponent"] != (g["away_team"] if team==g["home_team"] else g["home_team"])):
            continue
        if row["starter_status"]=="CONFIRMED_REVIEWED_PREKICKOFF":
            ev=row["starter_evidence"]
            if not ev or parse_time(ev["reviewed_at_utc"])>observed:
                raise ValueError("Invalid confirmed starter source")
            idx[(gid,team)]={
                "player":row["starter_player"],"status":"CONFIRMED_OFFICIAL",
                "source_url":ev["source_url"],"observed_at_utc":observed.isoformat(),
                "description":"Reviewed explicit official statement for this game"}
        elif row["starter_status"]=="UNKNOWN" and row.get("evidence_conflicts"):
            idx[(gid,team)]={
                "player":None,"status":"CONFLICT_REVIEW",
                "source_url":None,"observed_at_utc":observed.isoformat(),
                "description":"Conflicting or invalid game-specific QB evidence"}
    return idx

def passer_from_game_summary(summary,team_id,expected_team):
    """The top box-score PASSING athlete is NOT necessarily the team's starter."""
    box=summary.get("boxscore") or {}
    for row in box.get("players",[]) or []:
        team=row.get("team") or {}
        if str(team.get("id"))!=str(team_id) or team.get("displayName")!=expected_team:
            continue
        for group in row.get("statistics",[]) or []:
            if group.get("name")!="passing":continue
            for item in group.get("athletes",[]) or []:
                ath=item.get("athlete") or {}
                player=ath.get("displayName")
                if (isinstance(player,str) and 3<=len(player)<=100
                    and isinstance(item.get("stats"),list) and item["stats"]
                    and all(c.isprintable() for c in player)):
                    return player.strip()
    return None

def recent_completed_game_map(payload,required_team_ids,now):
    """Most recent completed game in an observed score slate, never a future game."""
    matches={}
    for game in payload.get("events",[]) or []:
        gid=str(game.get("id") or "")
        status=(game.get("status") or {}).get("type") or {}
        if status.get("completed") is not True or not gid.isdigit():continue
        try:when=parse_time(game["date"])
        except (KeyError,ValueError,TypeError):continue
        if when>=now:continue
        comps=game.get("competitions") or []
        if not comps:continue
        for side in comps[0].get("competitors") or []:
            tid=str((side.get("team") or {}).get("id") or "")
            if tid not in required_team_ids:continue
            if (side.get("team") or {}).get("displayName")!=required_team_ids[tid]:
                continue
            if tid not in matches or when>parse_time(matches[tid]["date"]):
                matches[tid]={"game_id":gid,"date":when.isoformat()}
    return matches

def overlay(board,history,now,team_id_map=None,recent_passers=None):
    if board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Untrusted forecast board")
    games={str(g["game_id"]):g for g in board["games"]}
    confirmed=confirmed_rows(history,games,now)
    team_id_map=team_id_map or {}
    recent_passers=recent_passers or {}
    counts={"confirmed":0,"recent_game_passer":0,"unknown":0,"conflicts":0}
    for g in board["games"]:
        gid=str(g["game_id"])
        for key,team in (("qb_home",g["home_team"]),("qb_away",g["away_team"])):
            slot=confirmed.get((gid,team))
            if slot is None:
                tid=team_id_map.get((gid,team))
                latest=recent_passers.get(tid) if tid else None
                if latest and isinstance(latest.get("player"),str):
                    slot={"player":latest["player"],"status":"RECENT_GAME_PASSER",
                          "source_url":latest["source_url"],
                          "last_game_utc":latest["last_game_utc"],
                          "observed_at_utc":now.isoformat(),
                          "description":"Last completed game's ESPN passing box-score leader, NOT a game-specific starter prediction"}
                else:slot=dict(UNKNOWN)
            g[key]=slot
            counts[{"CONFIRMED_OFFICIAL":"confirmed","RECENT_GAME_PASSER":"recent_game_passer",
                    "CONFLICT_REVIEW":"conflicts","UNKNOWN":"unknown"}[slot["status"]]]+=1
    board["qb_display"]={"status":STATUS,"captured_at_utc":now.isoformat(),
        "official_history_observed_utc":history.get("observed_at_utc") if history else None,
        "counts":counts,"model_features_updated":False,
        "warning":"A previous game's passing leader is NOT confirmation or prediction of this game's starter. Latest source overlay is separate from the frozen forecast."}
    return board

def collect(board,now,fetch=fetch_json):
    """Try confirmed official archive first; use recent completed-game passer as fallback."""
    wanted={str(g["game_id"]):g for g in board["games"]}
    days=sorted({parse_time(g["kickoff_utc"]).astimezone(
        ZoneInfo("America/New_York")).date() for g in wanted.values()})[:14]
    refs={};failures=[]
    for day in days:
        try:
            url=BASE+"/scoreboard?dates="+day.strftime("%Y%m%d")+"&limit=500&groups=80"
            refs.update(team_ids_from_scoreboard(fetch(url),wanted,now))
        except (ValueError,KeyError,OSError,TypeError) as exc:
            failures.append({"kind":"upcoming_scoreboard","day":day.isoformat(),"error":type(exc).__name__})
    wanted_teams={}
    for (gid,name),tid in refs.items():
        if tid in wanted_teams and wanted_teams[tid]!=name:
            raise ValueError("ESPN team id resolves to different school names")
        wanted_teams[tid]=name
    latest={}
    # Three recent weeks find teams returning after a bye, without attempting
    # to infer a QB1 from a season stat, roster position or future game.
    for n in range(1,23):
        day=now.date()-dt.timedelta(days=n)
        try:
            url=BASE+"/scoreboard?dates="+day.strftime("%Y%m%d")+"&limit=500&groups=80"
            available=recent_completed_game_map(fetch(url),wanted_teams,now)
            for tid,item in available.items():
                if tid not in latest or parse_time(item["date"])>parse_time(latest[tid]["date"]):
                    latest[tid]=item
        except (ValueError,KeyError,OSError,TypeError) as exc:
            failures.append({"kind":"completed_scoreboard","day":day.isoformat(),"error":type(exc).__name__})
    by_game={}
    for tid,g in latest.items():by_game.setdefault(g["game_id"],[]).append(tid)
    recent={}
    def collect_game(gid):
        return fetch(BASE+"/summary?event="+gid)
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures={pool.submit(collect_game,gid):gid for gid in sorted(by_game)}
        for future in concurrent.futures.as_completed(futures):
            gid=futures[future]
            try:
                summary=future.result()
                for tid in by_game[gid]:
                    name=passer_from_game_summary(summary,tid,wanted_teams[tid])
                    if name:
                        recent[tid]={"player":name,
                            "source_url":"https://www.espn.com/college-football/game/_/gameId/"+gid,
                            "last_game_utc":latest[tid]["date"]}
            except (ValueError,KeyError,OSError,TypeError) as exc:
                failures.append({"kind":"completed_game_boxscore","game_id":gid,"error":type(exc).__name__})
    return refs,recent,failures

def run(board_path,history_path,now=None,collector=collect):
    now=now or dt.datetime.now(dt.timezone.utc)
    source=Path(board_path);board=json.loads(source.read_text())
    hpath=Path(history_path)
    history=json.loads(hpath.read_text()) if hpath.exists() else None
    ids,recent,errors=collector(board,now)
    result=overlay(board,history,now,ids,recent)
    result["qb_display"]["school_ids_matched"]=len(ids)
    result["qb_display"]["recent_passers_identified"]=len(recent)
    result["qb_display"]["fetch_failures"]=errors[:150]
    source.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result["qb_display"]))
    return result

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--dashboard",required=True)
    ap.add_argument("--history",required=True)
    args=ap.parse_args()
    run(args.dashboard,args.history)

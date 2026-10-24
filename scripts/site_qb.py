"""Source-labeled QB context for the public research dashboard.

Game-specific reviewed official starters come from immutable as-observed
context-state QB history, never from season stats. 2026 ESPN season passing
leader is only a prior-performance reference, explicitly NOT a projected or
confirmed future starting quarterback. No change to frozen model features.
"""
import argparse,concurrent.futures,datetime as dt,json,re,urllib.request
from pathlib import Path
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

def overlay(board,history,now,team_id_map=None,leaders=None):
    if board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Untrusted forecast board")
    games={str(g["game_id"]):g for g in board["games"]}
    confirmed=confirmed_rows(history,games,now)
    team_id_map=team_id_map or {}
    leaders=leaders or {}
    counts={"confirmed":0,"season_passing_leader":0,"unknown":0,"conflicts":0}
    for g in board["games"]:
        gid=str(g["game_id"])
        for key,team in (("qb_home",g["home_team"]),("qb_away",g["away_team"])):
            slot=confirmed.get((gid,team))
            if slot is None:
                tid=team_id_map.get((gid,team))
                player=leaders.get(tid) if tid else None
                if player:
                    slot={"player":player,"status":"SEASON_PASSING_LEADER",
                          "source_url":BASE+"/teams/"+tid+"/leaders?season=2026",
                          "observed_at_utc":now.isoformat(),
                          "description":"2026 season passing leader, NOT a game-specific starter prediction"}
                else:
                    slot=dict(UNKNOWN)
            g[key]=slot
            counts[{"CONFIRMED_OFFICIAL":"confirmed","SEASON_PASSING_LEADER":"season_passing_leader",
                    "CONFLICT_REVIEW":"conflicts","UNKNOWN":"unknown"}[slot["status"]]]+=1
    board["qb_display"]={"status":STATUS,"captured_at_utc":now.isoformat(),
        "official_history_observed_utc":history.get("observed_at_utc") if history else None,
        "counts":counts,"model_features_updated":False,
        "warning":"Season passing leaders are NOT confirmed or projected starters. Latest source overlay was observed separately from the frozen forecast."}
    return board

def collect(board,now,fetch=fetch_json):
    """Best effort current ESPN context: errors never promote a starter."""
    wanted={str(g["game_id"]):g for g in board["games"]}
    days=sorted({parse_time(g["kickoff_utc"]).date() for g in wanted.values()})[:14]
    refs={};failures=[]
    for day in days:
        try:
            url=BASE+"/scoreboard?dates="+day.strftime("%Y%m%d")+"&limit=500&groups=80"
            refs.update(team_ids_from_scoreboard(fetch(url),wanted,now))
        except (ValueError,KeyError,OSError,TypeError) as exc:
            failures.append({"kind":"scoreboard","date":day.isoformat(),"error":type(exc).__name__})
    # Diagnose available completed-game public QB-leader schema before
    # promoting any last-game performer to a sourced, non-starter label.
    try:
        sample_day=now.date()-dt.timedelta(days=7)
        sample=fetch(BASE+"/scoreboard?dates="+sample_day.strftime("%Y%m%d")+"&limit=500&groups=80")
        ev=next((e for e in sample.get("events",[]) if e.get("competitions")),None)
        comp=ev["competitions"][0] if ev else {}
        team=(comp.get("competitors") or [{}])[0]
        leadership=team.get("leaders")
        desc={"events":len(sample.get("events",[])),"team_keys":sorted(team.keys()),
              "competitor_leaders_type":type(leadership).__name__,
              "first_category":(leadership[:1] if isinstance(leadership,list) else None)}
        print(json.dumps({"prior_week_espn_qb_diagnostic":desc})[:2000])
    except (ValueError,KeyError,OSError,TypeError) as exc:
        print(json.dumps({"prior_week_espn_qb_diagnostic_error":type(exc).__name__}))
    unique=sorted(set(refs.values()))
    results={}
    shapes=[]
    def one(tid):
        data=fetch(BASE+"/teams/"+tid+"/leaders?season=2026")
        sample={"team_id":tid,"keys":sorted(data.keys())[:15],
                "leaders_type":type(data.get("leaders")).__name__,
                "categories_type":type(data.get("categories")).__name__}
        groups=data.get("leaders") or data.get("categories") or []
        if isinstance(groups,list) and groups:
            sample["first_category_keys"]=sorted(groups[0].keys()) if isinstance(groups[0],dict) else []
            if isinstance(groups[0],dict):
                sample["first_category_name"]=groups[0].get("name")
                sample["first_category_display"]=groups[0].get("displayName")
                details=groups[0].get("leaders") or []
                if isinstance(details,list) and details and isinstance(details[0],dict):
                    sample["first_leader_keys"]=sorted(details[0].keys())
                    player=details[0].get("athlete") or {}
                    sample["first_athlete_keys"]=sorted(player.keys()) if isinstance(player,dict) else []
        return season_passing_leader(data),sample
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures={pool.submit(one,tid):tid for tid in unique}
        for f in concurrent.futures.as_completed(futures):
            tid=futures[f]
            try:
                name,sample=f.result()
                if name:results[tid]=name
                if len(shapes)<3 and (not name):shapes.append(sample)
            except (ValueError,KeyError,OSError,TypeError) as exc:
                failures.append({"kind":"team_leaders","team_id":tid,"error":type(exc).__name__})
    if not results and shapes:
        print(json.dumps({"qb_source_format_diagnostic":shapes}))
    return refs,results,failures

def run(board_path,history_path,now=None,collector=collect):
    now=now or dt.datetime.now(dt.timezone.utc)
    source=Path(board_path);board=json.loads(source.read_text())
    hpath=Path(history_path)
    history=json.loads(hpath.read_text()) if hpath.exists() else None
    ids,leaders,errors=collector(board,now)
    result=overlay(board,history,now,ids,leaders)
    result["qb_display"]["school_ids_matched"]=len(ids)
    result["qb_display"]["season_leaders_identified"]=len(leaders)
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

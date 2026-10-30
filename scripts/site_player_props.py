"""Source-matched pregame player STAT outlook for the public CFB game board.

This is a separate experimental PlayerForm R1 model. It does not change V03
scores, ATS, totals or the original archived forecasts. Source: presently
observed 2026 player-game box stats, 2025 athlete-ID priors and actual ESPN
2026 schedules. Players observed in past games are not automatically playing
in the next game; all numbers are CONDITIONAL stat scenarios, not book lines.

Early-game prior weights (40% same recorded team, 25% changed team ID) and
25% capped opponent allowance adjustment were tested SEPARATELY, not jointly.
The combination is unvalidated and no sportsbook player prop edge is claimed.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from scripts.game_context import parse_time
from scripts.nextgen_source_readiness import SOURCE, fetch_asset
from scripts.player_prop_history import NEEDED,from_box_rows
from scripts.player_prop_prior_seasons import SCHEDULE_COLS,make_schedule

STATUS="CFB_SITE_PLAYERFORM_R1_STAT_RESEARCH_ONLY"
MODEL="PlayerForm R1"
PICK=("passing_yards","rushing_yards","receiving_yards")
GROUP={"passing_yards":"QB passing","rushing_yards":"Rushing","receiving_yards":"Receiving"}
DEFENSE={"passing_yards":"passing_yards","rushing_yards":"rushing_yards",
         "receiving_yards":"passing_yards"}
NO_OPENING_START={"OUT","OUT_FIRST_HALF","SUSPENDED","DOUBTFUL"}
MAX_GAMES_PER_SIDE=3

def _id(x):
    try:
        n=float(x)
        return str(int(n)) if math.isfinite(n) and n>0 and n.is_integer() else None
    except (ValueError,TypeError,OverflowError):return None

def _name(s):
    return re.sub(r"[^a-z0-9]","",str(s or "").lower())

def _visible_team(a,b):
    x,y=_name(a),_name(b)
    return bool(x and y and (x==y or x in y or y in x))

def _mean(xs):
    return sum(xs)/len(xs) if xs else None

def _playerform(observed,older,metric,prevteams,team):
    if not observed:return None
    # Chronological oldest-to-newest records, with no target-game row.
    current=[v for _,v in observed][-6:]
    prior=[v for _,v in older][-6:]
    if len(current)<=2 and len(prior)>=2:
        share=.4 if team in prevteams and len(prevteams)==1 else .25
        base=(1-share)*_mean(current)+share*_mean(prior)
        tag="Prior-season blend"
    else:
        share=0.
        base=_mean(current[-4:])
        tag="Recent four"
    recent=current[-4:]
    return {"base":base,"prior_share":share,"base_method":tag,
            "current_games":len(current),"prior_games":len(prior),
            "recent_min":min(recent) if len(recent)>=3 else None,
            "recent_max":max(recent) if len(recent)>=3 else None}

def _freeze_labels(board,now):
    if board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Invalid archived website score board")
    if not isinstance(board.get("games"),list):raise ValueError("Missing game records")
    for g in board["games"]:
        if parse_time(g["kickoff_utc"])<=now:
            raise ValueError("Do not attach pregame projections to kicked-off game")
    return [(g["game_id"],g["model_home_margin"],g["model_total"],
             g["model_home_points"],g["model_away_points"]) for g in board["games"]]

def _blank(reason):
    return {"status":"PLAYER_OUTLOOK_UNAVAILABLE","model":MODEL,
        "reason":reason,"entries":[],"real_bookmaker_prop_lines":0,
        "player_participation_confirmed":False}

def overlay(board,box2026,box2025,schedule2026,schedule2025,observed_at_utc,
            source_hashes=None):
    now=parse_time(observed_at_utc)
    original=_freeze_labels(board,now)
    if not (isinstance(schedule2026,list) and isinstance(schedule2025,list)
            and isinstance(box2026,list) and isinstance(box2025,list)):
        raise ValueError("Missing raw verified ESPN source collections")
    sched26={}
    for r in schedule2026:
        gid=_id(r.get("game_id"))
        if gid is None or r.get("season")!=2026:continue
        if gid in sched26:raise ValueError("Duplicate official 2026 ESPN fixture ID")
        sched26[gid]=r
    past26,_=make_schedule(schedule2026,2026,observed_at_utc)
    past25,_=make_schedule(schedule2025,2025,observed_at_utc)
    rows26=from_box_rows(box2026,past26,observed_at_utc,season=2026)["rows"]
    rows25=from_box_rows(box2025,past25,observed_at_utc,season=2025)["rows"]
    curr=defaultdict(list);prev=defaultdict(list);prevteam=defaultdict(set)
    # These completed-game rows are only known from the source as observed NOW.
    # Do not pretend this is a historical pregame capture of each 2026 game.
    for rows,store in ((rows26,curr),(rows25,prev)):
        for row in rows:
            team=str(row["team_id"]);pid=str(row["player_id"])
            for stat in PICK:
                x=row["values"].get(stat)
                if type(x) is int:
                    store[(pid,team,stat)].append((parse_time(row["kickoff_utc"]),x,row["player_name"]))
                    if store is prev:prevteam[pid].add(team)
    # 2025 priors combine an athlete across teams only by verified ESPN ID.
    by_id_prior=defaultdict(list)
    for (pid,team,stat),items in prev.items():
        for kick,val,name in items:by_id_prior[(pid,stat)].append((kick,val))
    for history in (curr,by_id_prior):
        for val in history.values():val.sort(key=lambda r:r[0])
    # First build opponent defense from all PRIOR completed real 2026 games.
    from_game=defaultdict(lambda:defaultdict(list))
    teams_by_game={}
    for gid,g in past26.items():
        teams_by_game[str(gid)]=(str(g["home_id"]),str(g["away_id"]))
    for row in rows26:
        gid=str(row["game_id"]);team=str(row["team_id"])
        for stat in ("passing_yards","rushing_yards"):
            val=row["values"].get(stat)
            if type(val) is int:from_game[(gid,team)][stat].append(val)
    allowed=defaultdict(list);league=defaultdict(list)
    for (gid,team),vals in from_game.items():
        if gid not in teams_by_game:continue
        a,b=teams_by_game[gid]
        if team not in (a,b):continue
        opponent=b if team==a else a
        kick=parse_time(past26[gid]["kickoff_utc"])
        for stat,nums in vals.items():
            total=sum(nums)
            allowed[(opponent,stat)].append((kick,total))
            league[stat].append((kick,total))
    for group in (allowed,league):
        for vals in group.values():vals.sort()
    count=0;rows_count=0;blocked=defaultdict(int)
    for g in board["games"]:
        gid=str(g["game_id"]);s=sched26.get(gid)
        g["player_props"]=_blank("No verified ESPN schedule-to-team ID match")
        if not s:
            blocked["NO_MATCHED_ESPN_SCHEDULE"]+=1;continue
        if not _id(s.get("home_id")) or not _id(s.get("away_id")):
            blocked["MISSING_ESPN_TEAM_ID"]+=1;continue
        try:
            sourcekick=parse_time(s["start_date"])
        except (KeyError,TypeError,ValueError):
            blocked["BAD_ESPN_KICKOFF"]+=1;continue
        if (abs((sourcekick-parse_time(g["kickoff_utc"])).total_seconds())>3600
            or not _visible_team(s.get("home_team"),g["home_team"])
            or not _visible_team(s.get("away_team"),g["away_team"])):
            blocked["UNMATCHED_FIXTURE_TEAM_OR_KICKOFF"]+=1;continue
        entries=[]
        for side in ("home","away"):
            teamid=_id(s[side+"_id"])
            opponent=_id(s[("away" if side=="home" else "home")+"_id"])
            picks=[]
            for (pid,team,stat),items in curr.items():
                if team!=teamid:continue
                observed=[(kick,val) for kick,val,_ in items if kick<now]
                if not observed:continue
                last=items[-1]
                name=last[2]
                if (stat=="passing_yards" and
                    any(_name(a.get("player"))==_name(name) and
                        a.get("status") in NO_OPENING_START
                        for a in g.get("qb_availability_"+side,[]))):
                    blocked["QB_REPORTED_UNAVAILABLE"]+=1;continue
                old=[(kick,val) for kick,val in by_id_prior.get((pid,stat),[]) if kick<now]
                f=_playerform(observed,old,stat,prevteam[pid],teamid)
                if f is None:continue
                if f["current_games"]<2 and f["prior_games"]<2:
                    continue
                metric=DEFENSE[stat]
                against=[x for t,x in allowed.get((opponent,metric),[]) if t<now]
                total=[x for t,x in league.get(metric,[]) if t<now]
                matchup=None
                if len(against)>=3 and len(total)>=25 and _mean(total)>0:
                    raw=max(-.25,min(.25,_mean(against[-6:])/_mean(total[-2000:])-1))
                    matchup=round(raw,6)
                factor=1+.25*matchup if matchup is not None else 1.
                projected=round(max(0.,f["base"]*factor),1)
                picks.append({
                    "player_id":pid,"player":name,"team_side":side,
                    "team":g[side+"_team"],"metric":stat,"label":GROUP[stat],
                    "projection":projected,"unit":"yards",
                    "recent_game_low":f["recent_min"],
                    "recent_game_high":f["recent_max"],
                    "recent_games":f["current_games"],
                    "prior_year_games":f["prior_games"],
                    "prior_season_weight":f["prior_share"],
                    "recent_method":f["base_method"],
                    "opponent_matchup_factor":factor if matchup is not None else None,
                    "player_participation_status":"RECENT_GAME_PARTICIPANT_NOT_CONFIRMED",
                    "real_bookmaker_line":None,
                    "over_probability":None,
                    "source_observed_at_utc":now.isoformat(),
                })
            # One glance: max one QB passing, one rushing and one receiving
            # candidate per team; rank by past team opportunity/production.
            for stat in PICK:
                subset=[p for p in picks if p["metric"]==stat]
                subset.sort(key=lambda p:(-p["projection"],-p["recent_games"],p["player_id"]))
                if subset:entries.append(subset[0])
        if entries:
            entries.sort(key=lambda p:(0 if p["metric"]=="passing_yards" else
                                       1 if p["metric"]=="rushing_yards" else 2,
                                       0 if p["team_side"]=="away" else 1))
            g["player_props"]={"status":STATUS,"model":MODEL,
                "entries":entries,"source_observed_at_utc":now.isoformat(),
                "source_hashes":source_hashes or {},
                "real_bookmaker_prop_lines":0,
                "no_model_market_edge_available":True,
                "player_participation_confirmed":False,
                "historical_publication_time_authenticated":False}
            count+=1;rows_count+=len(entries)
        else:
            g["player_props"]=_blank("Insufficient player-game observations")
            blocked["INSUFFICIENT_PLAYER_HISTORY"]+=1
    if original!=_freeze_labels(board,now):
        raise ValueError("Player model must not change immutable V03 score fields")
    board["player_prop_display"]={
        "status":STATUS,"model":MODEL,"covered_games":count,
        "player_stat_projections":rows_count,"total_games":len(board["games"]),
        "unavailable_by_reason":dict(blocked),
        "model_scores_updated":False,"real_bookmaker_quotes_present":False,
        "valid_over_under_model_edges":False,
        "research_prior_and_matchup_components_jointly_validated":False,
        "all_player_participation_verified":False,
        "description":"Conditional player-stat research projections; not sportsbook props or live player confirmation."}
    return board

def run(path,now=None,fetcher=fetch_asset):
    import pyarrow.parquet as pq
    observed=now or dt.datetime.now(dt.timezone.utc)
    if isinstance(observed,str):observed=parse_time(observed)
    board_path=Path(path);board=json.loads(board_path.read_text(encoding="utf-8"))
    sources={
        "box2026":(SOURCE+"/espn_cfb_player_box/player_box_2026.parquet",NEEDED),
        "box2025":(SOURCE+"/espn_cfb_player_box/player_box_2025.parquet",NEEDED),
        "schedule2026":(SOURCE+"/cfb_schedules/cfb_schedules_2026.parquet",SCHEDULE_COLS),
        "schedule2025":(SOURCE+"/cfb_schedules/cfb_schedules_2025.parquet",SCHEDULE_COLS)}
    cols={};hashes={}
    try:
        for key,(uri,required) in sources.items():
            blob=fetcher(uri,max_bytes=150_000_000)
            sha=hashlib.sha256(blob).hexdigest()
            obj=pq.ParquetFile(io.BytesIO(blob))
            if not set(required).issubset(obj.schema_arrow.names):
                raise ValueError("Source column contract changed: "+key)
            cols[key]=obj.read(columns=sorted(required)).to_pylist()
            hashes[key]=sha
        board=overlay(board,cols["box2026"],cols["box2025"],
                      cols["schedule2026"],cols["schedule2025"],
                      observed.isoformat(),hashes)
    except (TimeoutError,ConnectionError,OSError,ValueError) as exc:
        _freeze_labels(board,observed)
        for g in board["games"]:g["player_props"]=_blank("Player source unavailable")
        board["player_prop_display"]={
            "status":"PLAYER_OUTLOOK_SOURCE_UNAVAILABLE",
            "model":MODEL,"covered_games":0,"total_games":len(board["games"]),
            "player_stat_projections":0,"model_scores_updated":False,
            "real_bookmaker_quotes_present":False,
            "reason":type(exc).__name__+":"+str(exc)[:100]}
    board_path.write_text(json.dumps(board,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(board["player_prop_display"],allow_nan=False))
    return board

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dashboard",required=True)
    a=p.parse_args();run(a.dashboard)

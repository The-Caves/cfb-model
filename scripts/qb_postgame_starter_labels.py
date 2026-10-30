"""Postgame actual QB starter label evidence: explicit provider flags ONLY.

This collector does not infer starters from passer volume, QB depth rank,
quarterback participation, first pass, or a postgame scoreboard. The ESPN game
summary may NOT carry an explicit QB starter indicator; in that case the label
is UNKNOWN. These observations are postgame labels, never pregame features.
"""
import argparse,csv,datetime as dt,hashlib,json,re,urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts.game_context import parse_time
from scripts.qb_passer_history import player_key

STATUS="POSTGAME_QB_STARTER_SOURCE_EVIDENCE_RESEARCH_ONLY"
SOURCE="ESPN_SITE_GAME_SUMMARY"
URL="https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event="
MAX_ERRORS=60
MAX_PLAYERS=20
LABEL="EXPLICIT_ESPN_POSTGAME_QB_STARTER_FLAG"
UNKNOWN="UNKNOWN_NOT_VERIFIED_STARTER"

def fetch(gid):
    if not re.fullmatch(r"\d{6,12}",str(gid)):
        raise ValueError("Invalid ESPN game identifier")
    req=urllib.request.Request(URL+str(gid),headers={
        "User-Agent":"CFB-QB-Start-Label-Audit/0.1","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=12) as resp:
        if resp.geturl()!=URL+str(gid):
            raise ValueError("ESPN summary redirect changed source")
        data=resp.read(3_000_001)
    if len(data)>3_000_000:raise ValueError("Oversized game summary")
    return json.loads(data)

def _flag(athlete):
    """Only a literal boolean on the athlete record establishes a starter."""
    return athlete.get("starter") is True or athlete.get("isStarter") is True

def _position(athlete):
    position=athlete.get("position")
    if isinstance(position,dict):
        return position.get("abbreviation")
    return position if isinstance(position,str) else None

def _athlete_name(a):
    for name in ("displayName","fullName"):
        value=a.get(name)
        if isinstance(value,str) and 2<=len(value.strip())<=100:
            return " ".join(value.split())
    return None

def parse(game,summary,observed_at):
    """Reject unverified game identity; permit unknown starter per team."""
    now=parse_time(observed_at);gid=str(game["game_id"])
    if not gid.isdigit():raise ValueError("Non-numeric game identifier")
    if parse_time(game["kickoff_utc"])>=now:
        raise ValueError("Future/uncompleted game requested for postgame QB evidence")
    comp=(summary.get("header") or {}).get("competitions") or []
    if len(comp)!=1 or not isinstance(comp[0],dict):
        raise ValueError("No unambiguous ESPN game summary competition")
    item=comp[0]
    if item.get("id") is not None and str(item["id"])!=gid:
        raise ValueError("ESPN game ID mismatch")
    sides=item.get("competitors") or []
    if len(sides)!=2:raise ValueError("Missing two-sided ESPN competitors")
    by_side={s.get("homeAway"):s for s in sides}
    if set(by_side)!={"home","away"}:
        raise ValueError("Ambiguous home/away opponent identity")
    if not item.get("status",{}).get("type",{}).get("completed"):
        raise ValueError("ESPN game not completed")
    for side in ("home","away"):
        side_record=by_side[side]
        if side_record.get("team",{}).get("displayName")!=game[side]:
            raise ValueError("ESPN team identity mismatch")
        if int(side_record.get("score",-1))!=int(game[side+"_score"]):
            raise ValueError("Independently observed final score mismatch")
    box=(summary.get("boxscore") or {}).get("players") or []
    teams={}
    for side in ("home","away"):
        team=game[side]
        teams[team]={"game_id":gid,"team":team,
            "opponent":game["away" if side=="home" else "home"],
            "kickoff_utc":game["kickoff_utc"],
            "home":game["home"],"away":game["away"],
            "starter_player":None,"label_status":UNKNOWN,
            "evidence_class":"NONE",
            "source_url":URL+gid,
            "source_payload_sha256":hashlib.sha256(json.dumps(summary,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest(),
            "captured_at_utc":now.isoformat(),
            "candidate_qb_passers":[],
            "explicit_qb_starter_flags":0,
            "requires_manual_review":True,
            "not_from_passing_leader":True,
            "historical_publication_time_verified":False,
            "betting_status":"PASS_UNVALIDATED"}
    seen_teams=set()
    for entry in box:
        name=(entry.get("team") or {}).get("displayName")
        if name not in teams or name in seen_teams:
            raise ValueError("Ambiguous two-sided boxscore player team")
        seen_teams.add(name)
        positive=[];seen=set();passing=[]
        for stat in entry.get("statistics") or []:
            category=str(stat.get("name") or "").casefold()
            if category=="passing":
                for raw in stat.get("athletes") or []:
                    athlete=raw.get("athlete") or {}
                    player=_athlete_name(athlete)
                    if player and player_key(player) not in {player_key(x) for x in passing}:
                        passing.append(player)
            for raw in stat.get("athletes") or []:
                athlete=raw.get("athlete") or {}
                player=_athlete_name(athlete)
                if not player or _position(athlete)!="QB":
                    continue
                key=player_key(player)
                if _flag(raw) or _flag(athlete):
                    # raw is the individual stat-athlete result; no coercion
                    # from missing, 1, string, position group or summary leader.
                    if key not in seen:
                        positive.append(player);seen.add(key)
        teams[name]["candidate_qb_passers"]=passing[:MAX_PLAYERS]
        teams[name]["explicit_qb_starter_flags"]=len(positive)
        if len(positive)==1:
            teams[name].update({"starter_player":positive[0],
                "label_status":LABEL,
                "evidence_class":"PROVIDER_EXPLICIT_BOX_SCORE_FLAG",
                "requires_manual_review":False})
        elif len(positive)>1:
            teams[name].update({"label_status":"CONFLICT_MULTIPLE_EXPLICIT_QB_FLAGS",
                "evidence_class":"AMBIGUOUS_PROVIDER_FLAGS"})
    return [teams[game["away"]],teams[game["home"]]]

def collect(games,observed_at,fetcher=fetch,workers=8):
    now=parse_time(observed_at)
    if not isinstance(games,list) or len({str(g["game_id"]) for g in games})!=len(games):
        raise ValueError("Duplicate or invalid completed football games")
    rows=[];errors=[];checked=0
    def one(g):
        try:
            return parse(g,fetcher(g["game_id"]),observed_at),None
        except (OSError,ValueError,KeyError,TypeError,TimeoutError,OverflowError) as exc:
            return [],{"game_id":str(g["game_id"]),"reason":type(exc).__name__}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for result,error in executor.map(one,games):
            checked+=1
            rows.extend(result)
            if error:errors.append(error)
    classified=Counter(x["label_status"] for x in rows)
    return {"status":STATUS,"season":2026,"captured_at_utc":now.isoformat(),
        "source":SOURCE,"completed_games_checked":checked,
        "verified_game_identities":len(rows)//2,
        "missing_or_rejected_games":len(errors),
        "team_slots":len(rows),
        "explicit_starter_labels":classified[LABEL],
        "unknown_or_conflict_starter_labels":len(rows)-classified[LABEL],
        "rows":rows,"errors":errors[:MAX_ERRORS],
        "postgame_labels_never_pregame_features":True,
        "historical_publication_times_verified":False,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

def run(games_file,output):
    with open(games_file,newline="",encoding="utf-8-sig") as handle:
        games=list(csv.DictReader(handle))
    result=collect(games,dt.datetime.now(dt.timezone.utc).isoformat())
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("rows","errors")}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True);p.add_argument("--output",required=True)
    args=p.parse_args();run(args.games,args.output)

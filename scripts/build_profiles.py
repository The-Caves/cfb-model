"""Build 2026-only score-based team profiles, strictly before --asof.

EPA, injuries, and betting market inputs are deliberately left unpopulated.
"""
import argparse,csv,datetime as dt,json
from collections import defaultdict
from pathlib import Path
from statistics import mean
FIELDS=("game_id","date","away","home","away_score","home_score","neutral")
def read_games(path,asof):
    cutoff=dt.date.fromisoformat(asof)
    if cutoff.year!=2026:raise ValueError("This pipeline profiles 2026 only")
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        r=csv.DictReader(f)
        if not set(FIELDS).issubset(set(r.fieldnames or [])):raise ValueError("Bad game ledger schema")
        raw=list(r)
    accepted=[];rejected=[];future=0;seen=set()
    for line,g in enumerate(raw,2):
        try:
            day=dt.date.fromisoformat(g["date"][:10])
            if day.year!=2026:rejected.append({"line":line,"reason":"wrong_season"});continue
            if day>=cutoff:future+=1;continue
            away=g["away"].strip();home=g["home"].strip()
            if not away or not home or away==home:raise ValueError("invalid teams")
            a,h=int(g["away_score"]),int(g["home_score"])
            if not 0<=a<=160 or not 0<=h<=160:raise ValueError("invalid score")
            gid=g["game_id"].strip();key=gid or (str(day),away,home)
            if key in seen:raise ValueError("duplicate game")
            seen.add(key)
            accepted.append({"game_id":gid,"date":day.isoformat(),"away":away,"home":home,
                             "away_score":a,"home_score":h,
                             "neutral":str(g["neutral"]).lower() in ("true","1","yes")})
        except (ValueError,TypeError,KeyError) as exc:
            rejected.append({"line":line,"reason":str(exc)})
    accepted.sort(key=lambda g:(g["date"],g["game_id"],g["home"]))
    return accepted,{"input_rows":len(raw),"accepted_games":len(accepted),
        "excluded_on_or_after_asof":future,"rejected":rejected}
def build_profiles(games,asof,team_registry=None):
    cutoff=dt.date.fromisoformat(asof)
    by=defaultdict(list)
    for g in games:
        if dt.date.fromisoformat(g["date"])>=cutoff:raise ValueError("future-game leakage")
        for side in ("away","home"):
            is_home=side=="home"
            pf=g["home_score"] if is_home else g["away_score"]
            pa=g["away_score"] if is_home else g["home_score"]
            opp=g["away"] if is_home else g["home"]
            by[g[side]].append({"date":g["date"],"opponent":opp,"pf":pf,"pa":pa,
                "margin":pf-pa,"win":int(pf>pa)})
    out=[]
    for team,rows in sorted(by.items()):
        if team_registry is not None and team not in team_registry:continue
        rows.sort(key=lambda r:r["date"]);last3=rows[-3:]
        wins=sum(x["win"] for x in rows)
        losses=sum(x["pf"]<x["pa"] for x in rows)
        out.append({"team":team,"season":2026,"asof_exclusive":asof,
            "games":len(rows),"wins":wins,"losses":losses,"ties":len(rows)-wins-losses,
            "points_for_per_game":round(mean(x["pf"] for x in rows),3),
            "points_against_per_game":round(mean(x["pa"] for x in rows),3),
            "avg_margin":round(mean(x["margin"] for x in rows),3),
            "last3_margin":round(mean(x["margin"] for x in last3),3),
            "last3_wins":sum(x["win"] for x in last3),
            "last_game_date":rows[-1]["date"],"last_opponent":rows[-1]["opponent"],
            "source_quality":"ESPN_SCOREBOARD_AS_RETRIEVED_UNVERIFIED",
            "epa_offense":"","epa_defense":"","injury_adjustment":"",
            "market_adjustment":"","betting_status":"PASS_UNVALIDATED"})
    return out
def write_profiles(path,asof,output,registry=None):
    games,qa=read_games(path,asof)
    if not games:raise ValueError("No 2026 completed games before cutoff")
    allowed=None
    if registry is not None:
        with Path(registry).open(newline='',encoding='utf-8-sig') as stream:
            registry_rows=list(csv.DictReader(stream))
        allowed={row['espn_display_name'].strip() for row in registry_rows}
        if not allowed or len(allowed)!=len(registry_rows):raise ValueError('Empty or duplicate FBS team registry')
    profiles=build_profiles(games,asof,allowed)
    if not profiles:raise ValueError('No eligible teams available in score ledger')
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    with (out/"team_profiles_2026.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(profiles[0]));w.writeheader();w.writerows(profiles)
    (out/"profile_manifest.json").write_text(json.dumps({
        "source":str(path),"asof_exclusive":asof,**qa,"teams_observed":len(profiles),
        "registry":str(registry) if registry else None,"expected_teams":len(allowed) if allowed is not None else None,
        "status":"COMPLETE_WITH_WARNINGS" if qa["rejected"] else "SUCCESS",
        "advanced_fields_populated":False,"betting_status":"PASS_UNVALIDATED"},indent=2))
    return len(profiles),qa
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",default="data/games_2026.csv")
    p.add_argument("--asof",default=dt.date.today().isoformat())
    p.add_argument("--output",default="data")
    p.add_argument("--registry",default=None)
    a=p.parse_args();n,qa=write_profiles(a.games,a.asof,a.output,a.registry)
    print(json.dumps({"teams":n,**qa},indent=2))
    if qa["rejected"]:raise SystemExit(2)

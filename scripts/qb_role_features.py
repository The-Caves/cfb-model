"""Pregame quarterback role and return context, research only.

Separate 'historical season passing-play leader' from actual QB1 and next-game
starter. Only a reviewed exact-game starter declaration may confirm QB1.
Historical PBP is not publication-authenticated for past game replays.
"""
import argparse,csv,datetime as dt,json
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.personnel_features import verify_joined

from scripts.game_context import parse_time
from scripts.qb_passer_history import prior_qb_form

STATUS="QB_PERSONNEL_ROLE_CHANGE_RESEARCH_ONLY"
MIN_NAMED_SEASON_PLAYS=35
MIN_SEASON_LEAD_SHARE=.55
MIN_GAME_SHARE=.65

def _past_games(rows,team,game_date,decision):
    cutoff=dt.date.fromisoformat(game_date)
    out={}
    for r in rows:
        if r["team"]!=team:continue
        if r.get("historical_source_time_verified") not in (False,"False","false"):
            raise ValueError("Untrusted source provenance")
        if r.get("betting_status")!="PASS_UNVALIDATED":
            raise ValueError("Untrusted QB record")
        day=dt.date.fromisoformat(r["date"])
        retrieved=parse_time(r["source_retrieved_at_utc"])
        if retrieved>decision or day>=cutoff:continue
        key=(str(r["game_id"]),r["player"].casefold())
        if key in out:raise ValueError("Duplicate passer attribution")
        out[key]=r
    return list(out.values())

def _profile(rows):
    if not rows:return {"season_leading_passer_proxy":None,"prior_games":0,
                        "last_game_leading_passer_proxy":None,
                        "observed_recent_qb_switch":None,
                        "source":"NO_PRIOR_QB_PASSER_EVIDENCE"}
    totals=defaultdict(int);games=defaultdict(list)
    for r in rows:
        n=int(r["pass_tagged_plays"])
        if n<0:raise ValueError("Negative QB play count")
        totals[r["player"]]+=n
        games[(r["date"],str(r["game_id"]))].append(r)
    total=sum(totals.values())
    ordered=sorted(totals.items(),key=lambda x:(-x[1],x[0]))
    lead=(ordered[0][0] if ordered and total>=MIN_NAMED_SEASON_PLAYS
          and ordered[0][1]/total>=MIN_SEASON_LEAD_SHARE else None)
    latest_day=max(games)
    last=sorted(games[latest_day],key=lambda r:(-int(r["pass_tagged_plays"]),r["player"]))
    game_total=sum(int(r["pass_tagged_plays"]) for r in last)
    last_leader=(last[0]["player"] if game_total and
                 int(last[0]["pass_tagged_plays"])/game_total>=MIN_GAME_SHARE else None)
    return {"season_leading_passer_proxy":lead,
            "prior_games":len(games),
            "last_game_leading_passer_proxy":last_leader,
            "observed_recent_qb_switch":(lead!=last_leader if lead and last_leader else None),
            "source":"PRIOR_OBSERVED_PASSER_USAGE_NOT_DEPTH_CHART"}

def _official_context(game,team,registry,decision):
    cfg=registry or {}
    if cfg.get("status")!="REVIEWED_OFFICIAL_GAMEWEEK_LINKS_NOT_QB_STARTERS":
        return None
    review_date=dt.date.fromisoformat(cfg["first_review_date"])
    if review_date>decision.date():return None
    for e in cfg.get("entries",[]):
        if str(e.get("game_id"))!=str(game["game_id"]) or e.get("team")!=team:
            continue
        if (e.get("opponent")!=(game["away"] if team==game["home"] else game["home"])
            or parse_time(e["kickoff_utc"])!=parse_time(game["kickoff_utc"])
            or e["starter_confirmed"] is not False):
            raise ValueError("Gameweek QB context not exact or fabricated")
        if dt.date.fromisoformat(e["published_date"])>decision.date():
            return None
        ctx=e.get("qb_context") or {}
        if ctx.get("mention_type")=="RETURNED_FROM_INJURY_IN_PREVIOUS_GAME":
            return {"player":ctx["player"],
                    "signal":"RETURNED_IN_PRIOR_GAME_NOT_CONFIRMED_THIS_GAME",
                    "source_url":ctx["source_url"],
                    "source_publication_instant_authenticated":False,
                    "next_game_starter_confirmed":False}
    return None

def build(games,passers,registry,asof_utc,reviewed_starters=None):
    decision=parse_time(asof_utc)
    starters=reviewed_starters or {}
    out=[];seen=set()
    for g in games:
        kickoff=parse_time(g["kickoff_utc"])
        if kickoff<=decision:continue
        gid=str(g["game_id"])
        if gid in seen:raise ValueError("Duplicate future game")
        seen.add(gid)
        for team,other in ((g["home"],g["away"]),(g["away"],g["home"])):
            history=_past_games(passers,team,kickoff.astimezone(
                ZoneInfo("America/New_York")).date().isoformat(),decision)
            profile=_profile(history)
            key=(gid,team)
            reviewed=starters.get(key)
            official=_official_context(g,team,registry,decision)
            confirmed=None
            if reviewed is not None:
                if (reviewed.get("status")!="CONFIRMED_REVIEWED_PREKICKOFF" or
                    not reviewed.get("player") or parse_time(reviewed["observed_at_utc"])>decision):
                    raise ValueError("Unreviewed next-game starter")
                confirmed=reviewed["player"]
            selected=confirmed
            form=None
            if selected:
                # Current verified game-specific starter is required; never
                # treat the historical passing-play leader as next-game QB.
                form=prior_qb_form(history,team,selected,
                    kickoff.astimezone(dt.timezone(dt.timedelta(hours=-4))).date().isoformat(),
                    decision.isoformat())
            out.append({"game_id":gid,"home":g["home"],"away":g["away"],
                "team":team,"opponent":other,"kickoff_utc":g["kickoff_utc"],
                "asof_utc":decision.isoformat(),
                **profile,"official_recent_return_context":official,
                "current_qb_status":("CONFIRMED_REVIEWED_PREKICKOFF" if confirmed else "UNKNOWN"),
                "current_starting_qb":confirmed,
                "current_qb_conditional_history":form,
                "model_qb_points_adjustment":None,
                "eligible_to_adjust_live_model":False})
    return {"status":STATUS,"season":2026,"asof_utc":decision.isoformat(),
            "team_game_slots":len(out),
            "unknown_upcoming_qb_slots":sum(x["current_qb_status"]=="UNKNOWN" for x in out),
            "historical_usage_leader_slots":sum(bool(x["season_leading_passer_proxy"]) for x in out),
            "observed_return_context_slots":sum(bool(x["official_recent_return_context"]) for x in out),
            "rows":out,"model_promoted":False,"betting_status":"PASS_UNVALIDATED",
            "safe_for_betting":False}

def reviewed_starters_from_joined(joined,context):
    """Use only the independently reviewed current-game starter snapshot."""
    verify_joined(joined)
    if parse_time(joined["captured_at_utc"])<parse_time(context["asof_utc"]):
        raise ValueError("Historical personnel snapshot before current context")
    idx={}
    games={str(g["game_id"]):g for g in context["games"]}
    for row in joined["games"]:
        gid=str(row["game_id"])
        expected=games.get(gid)
        if expected is None:raise ValueError("Future QB fixture absent from context")
        if ((row["home"],row["away"],parse_time(row["kickoff_utc"]))!=
            (expected["home"],expected["away"],parse_time(expected["kickoff_utc"]))):
            raise ValueError("QB joined matchup identity mismatch")
        for side in ("home","away"):
            info=row["personnel_by_side"][side]
            if info["qb_status"]=="CONFIRMED_REVIEWED_PREKICKOFF":
                idx[(gid,row[side])]={
                    "status":"CONFIRMED_REVIEWED_PREKICKOFF",
                    "player":info["reviewed_qb_player"],
                    "observed_at_utc":info["qb_observed_at_utc"]}
    return idx

def run(games_path,passers_path,registry_path,output_path,joined_path=None):
    context=json.loads(Path(games_path).read_text())
    with open(passers_path,newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
    config=json.loads(Path(registry_path).read_text())
    verified={}
    decision=context["asof_utc"]
    if joined_path:
        joined=json.loads(Path(joined_path).read_text())
        verified=reviewed_starters_from_joined(joined,context)
        decision=joined["captured_at_utc"]
    result=build(context["games"],rows,config,decision,verified)
    target=Path(output_path);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x") as f:json.dump(result,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("rows",)}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--context",required=True);p.add_argument("--passers",required=True)
    p.add_argument("--registry",required=True);p.add_argument("--output",required=True)
    p.add_argument("--joined")
    a=p.parse_args()
    run(a.context,a.passers,a.registry,a.output,a.joined)

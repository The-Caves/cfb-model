"""Timestamp-safe game-context snapshots, meaningful deltas and kickoff freezes.

Important: a disappeared player status is not evidence of recovery. A missing
weather value is not zero wind. All snapshots are retrospective research only.
"""
import datetime as dt
import json
from scripts.game_context import parse_time

NUMERIC_THRESHOLDS={"wind_mph":5,"gust_mph":8,"precip_probability_pct":20,
                    "temperature_f":8,"home_approx_straight_line_miles":60,
                    "away_approx_straight_line_miles":60}
TRACK_FIELDS=("kickoff_utc","venue","venue_city","venue_state","weather_status",
              "injury_report_status","home_days_since_last_game",
              "away_days_since_last_game")
SIGNIFICANT={"kickoff_utc","venue","venue_city","venue_state"}
def names(qb):
    if not isinstance(qb,dict):return {}
    return {team:x["player"] for team,x in qb.items()
            if isinstance(x,dict) and x.get("player") and x.get("source_url")}
def observed_injuries(r):
    items=r.get("injury_reports") or []
    if not isinstance(items,list):return {}
    return {(p.get("team"),p.get("player")):p["status"] for p in items
            if isinstance(p,dict) and p.get("team") and p.get("player")
            and p.get("status") and p.get("source_url")}
def snapshot_changes(previous,current,now):
    """Return (meaningful deltas, kickoff-frozen previously observed records, QA).

    A freeze only uses the *previous* pregame capture. Never copy a postgame
    current-game record into its own frozen pregame history.
    """
    issue=parse_time(now)
    if previous is None:
        return [],[],{"previous_present":False,"new_games":len(current.get("games",[])),
                      "changed_games":0,"frozen_games":0}
    earlier=parse_time(previous["asof_utc"])
    if earlier>issue:raise ValueError("Previous snapshot is from the future")
    old={str(g["game_id"]):g for g in previous.get("games",[])}
    new={str(g["game_id"]):g for g in current.get("games",[])}
    if len(old)!=len(previous.get("games",[])) or len(new)!=len(current.get("games",[])):
        raise ValueError("Duplicate game ID in context snapshot")
    changes=[];frozen=[];changed_games=set()
    for gid,a in sorted(old.items()):
        kickoff=parse_time(a["kickoff_utc"])
        if earlier<kickoff<=issue:
            frozen.append({"game_id":gid,"final_pregame_snapshot_asof_utc":previous["asof_utc"],
                           "kickoff_utc":a["kickoff_utc"],"snapshot":a,
                           "freeze_recorded_utc":issue.isoformat()})
            continue
        if kickoff<=issue:continue
        b=new.get(gid)
        if b is None:
            # A game missing in an incomplete/short-horizon run is not canceled.
            continue
        def add(field,before,after,kind):
            changes.append({"game_id":gid,"home":a.get("home"),"away":a.get("away"),
                            "field":field,"before":before,"after":after,"kind":kind,
                            "previous_asof_utc":previous["asof_utc"],
                            "current_asof_utc":current["asof_utc"]})
            changed_games.add(gid)
        for field in TRACK_FIELDS:
            x,y=a.get(field),b.get(field)
            if x==y:continue
            if field in SIGNIFICANT and x is not None and y is not None:
                add(field,x,y,"SCHEDULE_OR_VENUE_CHANGED")
            elif field=="injury_report_status" and x!=y:
                add(field,x,y,"PERSONNEL_COVERAGE_CHANGED")
            elif field=="weather_status" and x!=y:
                add(field,x,y,"WEATHER_COVERAGE_CHANGED")
        for field,threshold in NUMERIC_THRESHOLDS.items():
            if field in ("wind_mph","gust_mph","precip_probability_pct","temperature_f") and (a.get("weather_status")!="LIVE_FORECAST" or b.get("weather_status")!="LIVE_FORECAST"):
                continue
            x,y=a.get(field),b.get(field)
            if not isinstance(x,(int,float)) or isinstance(x,bool):continue
            if not isinstance(y,(int,float)) or isinstance(y,bool):
                add(field,x,None,"NUMERIC_SOURCE_UNAVAILABLE")
            elif abs(y-x)>=threshold:
                add(field,x,y,"SIGNIFICANT_NUMERIC_FORECAST_CHANGE")
        oldq,newq=names(a.get("verified_qb_starters")),names(b.get("verified_qb_starters"))
        for team in sorted(set(oldq)|set(newq)):
            x,y=oldq.get(team),newq.get(team)
            if x==y:continue
            add("verified_qb_starters."+team,x,y,
                "CONFIRMED_QB_CHANGE" if x and y else
                "NEW_VERIFIED_QB" if y else "QB_REPORT_UNAVAILABLE")
        oldinj,newinj=observed_injuries(a),observed_injuries(b)
        for team,player in sorted(set(oldinj)|set(newinj)):
            x,y=oldinj.get((team,player)),newinj.get((team,player))
            if x==y:continue
            add("injury."+str(team)+"."+str(player),x,y,
                "VERIFIED_INJURY_STATUS_CHANGE" if x and y else
                "NEW_VERIFIED_INJURY_CLAIM" if y else "INJURY_SOURCE_NOT_PRESENT")
    for gid,b in sorted(new.items()):
        if gid not in old and parse_time(b["kickoff_utc"])>issue:
            changes.append({"game_id":gid,"home":b.get("home"),"away":b.get("away"),
                "field":"game","before":None,"after":"AVAILABLE","kind":"NEW_UPCOMING_GAME",
                "previous_asof_utc":previous["asof_utc"],
                "current_asof_utc":current["asof_utc"]})
            changed_games.add(gid)
    return changes,frozen,{"previous_present":True,"new_games":sum(k not in old for k in new),
                            "changed_games":len(changed_games),"delta_events":len(changes),
                            "frozen_games":len(frozen),"personnel_changes":sum(
                                x["kind"] in ("CONFIRMED_QB_CHANGE","NEW_VERIFIED_QB",
                                  "VERIFIED_INJURY_STATUS_CHANGE","NEW_VERIFIED_INJURY_CLAIM")
                                for x in changes)}

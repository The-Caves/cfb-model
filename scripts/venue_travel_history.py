"""Retrospective game-day travel context with past-only school home-base inference.

Read ESPN *archived* completed-game venue metadata and a separately captured
named-city geocode cache. Distances are centroid-to-centroid great circles, NOT
actual itineraries, time on plane, arrival dates, sleep/acclimation or medical
fatigue. The cache is fetched after historical games; historical publication
timestamps are NOT authenticated. Source is research-only.
"""
import argparse,csv,datetime as dt,json
from collections import Counter,defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.game_context import (load_archived_events,home_venue_city,parse_time,
                                  distance_miles)
from scripts.venue_travel_candidate import travel_inputs,TRAVEL_KEYS,VENUE_SOURCE

STATUS="RETROSPECTIVE_2026_VENUE_TRAVEL_GEOGRAPHY_NOT_ASOF_ATTESTED"

def load_cache(path):
    obj=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj,dict):raise ValueError("Invalid geocode cache")
    cache={}
    for label,geo in obj.items():
        try:key=tuple(json.loads(label))
        except (TypeError,ValueError):continue
        if (len(key)!=3 or not isinstance(geo,dict) or
            geo.get("precision")!="CITY_CENTROID_NOT_STADIUM_COORDINATE"):
            continue
        name=geo.get("timezone")
        try:valid_zone=bool(isinstance(name,str) and "/" in name and ZoneInfo(name))
        except (ValueError,KeyError):valid_zone=False
        if (not valid_zone or not isinstance(geo.get("latitude"),(int,float))
            or not isinstance(geo.get("longitude"),(int,float))):
            continue
        cache[key]=geo
    return cache

def _location(geo_cache,event):
    return geo_cache.get((event.get("city"),event.get("state"),event.get("country")))

def reconstruct(games,events,geo_cache,asof_utc):
    asof=parse_time(asof_utc)
    game_index={str(g["game_id"]):g for g in games}
    if len(game_index)!=len(games):raise ValueError("Duplicate game in scoreboard")
    event_index={str(e["game_id"]):e for e in events}
    if len(event_index)!=len(events):raise ValueError("Duplicate archived event")
    for game in games:
        if parse_time(game["kickoff_utc"])>=asof:
            raise ValueError("Future or incomplete scoreboard at retrospective research cutoff")
    groups=defaultdict(list)
    for g in games:groups[g["date"]].append(g)
    past=[];most_recent={}
    outputs=[];counts=Counter()
    for date in sorted(groups):
        # Before observing this Eastern football date, build both schools'
        # home-city baselines exclusively from earlier completed games.
        home_candidates=home_venue_city(past)
        for g in groups[date]:
            gid=str(g["game_id"])
            event=event_index.get(gid)
            if event is None:
                counts["missing_event"]+=1;continue
            if (g["home"]!=event["home"] or g["away"]!=event["away"] or
                parse_time(g["kickoff_utc"])!=parse_time(event["kickoff_utc"]) or
                (str(g["neutral"]).lower()=="true")!=event["neutral"]):
                raise ValueError("Retrospective ESPN event identity mismatch")
            venue=_location(geo_cache,event)
            if venue is None:
                counts["missing_venue_timezone_or_geocode"]+=1;continue
            kickoff=parse_time(g["kickoff_utc"])
            source={"venue_location_quality":"CITY_CENTROID_NOT_STADIUM_COORDINATE",
                    "travel_source":"INFERRED_PRIOR_HOME_CITY_TO_GEOCODED_VENUE_CITY"}
            for side in ("home","away"):
                tid=event[side+"_id"]
                base=home_candidates.get(tid)
                base_geo=_location(geo_cache,base) if base else None
                last=most_recent.get(tid)
                source[side+"_days_since_last_game"]=(kickoff-last).total_seconds()/86400 if last else None
                if base_geo is None:
                    counts["unknown_prior_home_base_"+side]+=1
                    source[side+"_approx_straight_line_miles"]=None
                    source[side+"_timezone_shift_hours"]=None
                    source[side+"_body_clock_kickoff_hour"]=None
                else:
                    source[side+"_approx_straight_line_miles"]=distance_miles(
                        (base_geo["latitude"],base_geo["longitude"]),
                        (venue["latitude"],venue["longitude"]))
                    origin=ZoneInfo(base_geo["timezone"])
                    destination=ZoneInfo(venue["timezone"])
                    offset=(kickoff.astimezone(destination).utcoffset().total_seconds()-
                            kickoff.astimezone(origin).utcoffset().total_seconds())/3600
                    source[side+"_timezone_shift_hours"]=offset
                    origin_kickoff=kickoff.astimezone(origin)
                    source[side+"_body_clock_kickoff_hour"]=origin_kickoff.hour+origin_kickoff.minute/60
            features=travel_inputs(source)
            if features is None:
                counts["partial_location_or_rest_context"]+=1;continue
            counts["audited_games"]+=1
            outputs.append({"game_id":gid,"date":g["date"],"home":g["home"],
                "away":g["away"],"kickoff_utc":g["kickoff_utc"],
                "travel_evidence_status":VENUE_SOURCE,
                "audited_travel_features":features,
                "source_retrieved_at_utc":asof.isoformat(),
                "historical_snapshot_publication_authenticated":False,
                "betting_status":"PASS_UNVALIDATED"})
        # Only after every game that day was evaluated may those venue
        # facts and recent trips enter the NEXT day's home/away baselines.
        for g in groups[date]:
            e=event_index.get(str(g["game_id"]))
            if e is None:continue
            past.append(e)
            kickoff=parse_time(e["kickoff_utc"])
            for side in ("home","away"):
                k=e[side+"_id"]
                if k not in most_recent or most_recent[k]<kickoff:most_recent[k]=kickoff
    return {"status":STATUS,"season":2026,
        "asof_utc":asof.isoformat(),"source_reconstructed_from_archived_finals":True,
        "historical_location_published_before_games":False,
        "travel_scenarios_not_actual_itineraries":True,
        "source_city_centroids_available":len(geo_cache),
        "scoreboard_completed_games":len(games),
        "rows":outputs,"qa":dict(counts),
        "betting_status":"PASS_UNVALIDATED","safe_for_betting":False}

def run(games_path,raw_dir,geo_cache,output):
    with open(games_path,newline="",encoding="utf-8") as stream:
        games=list(csv.DictReader(stream))
    completed=load_archived_events(raw_dir)
    cache=load_cache(geo_cache)
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    report=reconstruct(games,completed,cache,now)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":report["status"],"historical_games":len(games),
         "geocoded_cities":len(cache),"qa":report["qa"]}))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True);p.add_argument("--raw-dir",required=True)
    p.add_argument("--geo-cache",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.games,a.raw_dir,a.geo_cache,a.output)

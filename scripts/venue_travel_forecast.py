"""Freeze separate neutral-field and restrained-travel research forecasts.

Pre-kickoff snapshots are genuine, but historical venue/PBP publication clocks
remain unverified. No V03 overwrite and no unsupported travel deductions.
"""
import argparse,csv,datetime as dt,json
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.game_context import parse_time,home_venue_city,load_archived_events,distance_miles
from scripts.personnel_forecast import verify as verify_baseline,checksum
from scripts.venue_travel_candidate import fit,predict,VENUE_SOURCE
from scripts.venue_travel_history import load_cache

STATUS="VENUE_TRAVEL_PREGAME_SHADOW_RESEARCH_ONLY"
def fixture_trip(row,homes,cache,kickoff):
    site=cache.get((row.get("venue_city"),row.get("venue_state"),"USA"))
    if site is None:return None
    out={"venue_location_quality":"CITY_CENTROID_NOT_STADIUM_COORDINATE",
         "travel_source":"INFERRED_PRIOR_HOME_CITY_TO_GEOCODED_VENUE_CITY"}
    for side in ("home","away"):
        base=homes.get(str(row.get(side+"_team_id")))
        geo=cache.get((base["city"],base["state"],base["country"])) if base else None
        rest=row.get(side+"_days_since_last_game")
        if geo is None or rest is None:return None
        out[side+"_approx_straight_line_miles"]=distance_miles(
            (geo["latitude"],geo["longitude"]),(site["latitude"],site["longitude"]))
        origin=ZoneInfo(geo["timezone"])
        zone=ZoneInfo(site["timezone"])
        out[side+"_timezone_shift_hours"]=(
            kickoff.astimezone(zone).utcoffset().total_seconds()-
            kickoff.astimezone(origin).utcoffset().total_seconds())/3600
        clock=kickoff.astimezone(origin)
        out[side+"_body_clock_kickoff_hour"]=clock.hour+clock.minute/60
        out[side+"_days_since_last_game"]=rest
    return out

def build(frozen,context,games,historical,geocodes,events,observed_at):
    verify_baseline(frozen)
    now=parse_time(observed_at)
    if not (parse_time(frozen["forecast_observed_utc"])<=now and
        (now-parse_time(frozen["forecast_observed_utc"])).total_seconds()<=1800 and
        parse_time(context["asof_utc"])<=now):
        raise ValueError("Stale or future venue decision")
    if (historical.get("status")!="RETROSPECTIVE_2026_VENUE_TRAVEL_GEOGRAPHY_NOT_ASOF_ATTESTED"
        or historical.get("betting_status")!="PASS_UNVALIDATED" or
        historical.get("historical_location_published_before_games") is not False):
        raise ValueError("Untrusted travel reconstruction")
    if len({str(g["game_id"]) for g in games})!=len(games):
        raise ValueError("Duplicate training game")
    if checksum(sorted(str(g["game_id"]) for g in games))!=frozen["model_training"]["training_game_ids_sha256"]:
        raise ValueError("Historical training ID drift")
    remaining=[g for g in frozen["games"] if parse_time(g["kickoff_utc"])>now]
    if not remaining:raise ValueError("No future fixtures")
    cutoff=min(parse_time(g["kickoff_utc"]).astimezone(
        ZoneInfo("America/New_York")).date() for g in remaining)
    archive={str(x["game_id"]):x for x in historical["rows"]}
    if len(archive)!=len(historical["rows"]):raise ValueError("Duplicate travel evidence")
    history=[]
    for g in games:
        if dt.date.fromisoformat(g["date"])>=cutoff:continue
        row={**g,"home_score":int(g["home_score"]),
             "away_score":int(g["away_score"]),
             "neutral":str(g["neutral"]).lower()=="true"}
        e=archive.get(str(g["game_id"]))
        if e:
            if (g["home"],g["away"],g["kickoff_utc"])!=(e["home"],e["away"],e["kickoff_utc"]):
                raise ValueError("Historical travel wrong fixture")
            row["travel_evidence_status"]=VENUE_SOURCE
            row["audited_travel_features"]=e["audited_travel_features"]
        history.append(row)
    venue=fit(history,cutoff)
    travel=fit(history,cutoff,travel=True)
    homes=home_venue_city([e for e in events if e["completed"] and
             parse_time(e["kickoff_utc"])<now])
    index={str(g["game_id"]):g for g in context["games"]}
    rows=[]
    for pred in remaining:
        gid=str(pred["game_id"]);row=index.get(gid)
        if row is None or (row["home"],row["away"],row["kickoff_utc"])!=(
            pred["home"],pred["away"],pred["kickoff_utc"]):
            raise ValueError("Future context mismatches forecast")
        regular=predict(venue,row)
        source=fixture_trip(row,homes,geocodes,parse_time(row["kickoff_utc"]))
        adjusted=predict(travel,{**row,**(source or {})},travel=True) if source else None
        rows.append({"game_id":gid,"home":row["home"],"away":row["away"],
             "kickoff_utc":row["kickoff_utc"],"baseline_row_sha256":pred["row_sha256"],
             "v03_frozen_margin":pred["projection"]["predicted_home_margin"],
             "venue_only_margin":regular["predicted_home_margin"] if regular else None,
             "venue_only_home_field_points":regular["home_field_points"] if regular else None,
             "venue_plus_travel_margin":adjusted["predicted_home_margin"] if adjusted else None,
             "small_travel_adjustment_points":adjusted["travel_adjustment"] if adjusted else None,
             "travel_source_complete":source is not None,
             "no_travel_adjustment_when_missing":adjusted is None,
             "prediction_total_unchanged":pred["projection"]["predicted_total_points"]})
    return {"status":STATUS,"season":2026,"observed_at_utc":now.isoformat(),
         "baseline_run_id":frozen["run_id"],
         "baseline_forecast_sha256":checksum(frozen),
         "training_games":len(history),"historically_qualified_trips":len(historical["rows"]),
         "travel_training_games":travel.get("travel_training_games",0),
         "summary":{"future_games":len(rows),
                    "venue_predictions":sum(r["venue_only_margin"] is not None for r in rows),
                    "travel_predictions":sum(r["venue_plus_travel_margin"] is not None for r in rows)},
         "games":rows,"betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
         "model_promoted":False,"historical_publication_authenticated":False}

def run(forecast,context,games,history,geo,raw,output):
    frozen=json.loads(Path(forecast).read_text())
    ctx=json.loads(Path(context).read_text())
    with open(games,newline="",encoding="utf-8") as f:past=list(csv.DictReader(f))
    hist=json.loads(Path(history).read_text())
    result=build(frozen,ctx,past,hist,load_cache(geo),load_archived_events(raw),
                 dt.datetime.now(dt.timezone.utc).isoformat())
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x") as f:json.dump(result,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({"status":STATUS,**result["summary"],
          "travel_training_games":result["travel_training_games"],"model_promoted":False}))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for field in ("forecast","context","games","history","geo","raw","output"):
        p.add_argument("--"+field,required=True)
    args=p.parse_args()
    run(args.forecast,args.context,args.games,args.history,args.geo,args.raw,args.output)

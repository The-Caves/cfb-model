"""Live pregame schedule, venue, rest, approximate travel, weather and personnel audit.

Never present historical weather analysis as pregame forecast. No injury source
is inferred from missing coverage. All outputs remain PASS_UNVALIDATED.
"""
import argparse,csv,datetime as dt,hashlib,json,time,urllib.parse,urllib.request
from pathlib import Path
from scripts.game_context import (ET,UTC,build_context,extract_game,geocode_match,
                                  load_archived_events,parse_forecast,parse_time)
from scripts.availability_context import evaluate,load_reports

ESPN="https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
GEO="https://geocoding-api.open-meteo.com/v1/search"
WX="https://api.open-meteo.com/v1/forecast"
HOURLY="temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation_probability,precipitation"

def request_json(url,timeout=25):
    request=urllib.request.Request(url,headers={"User-Agent":"cfb-2026-research/0.4",
                                                "Accept":"application/json"})
    with urllib.request.urlopen(request,timeout=timeout) as res:
        data=res.read(6_000_000)
    if len(data)>=6_000_000:raise ValueError("Source response exceeded size limit")
    response=json.loads(data)
    if not isinstance(response,dict) or response.get("error"):
        raise ValueError("Invalid API response: "+str(response.get("reason","unknown"))[:100])
    return response

def load_upcoming(issue,days,out):
    start=issue.astimezone(ET).date()
    events={};errors=[];fetched=0
    raw=out/"upcoming_scoreboards";raw.mkdir(parents=True,exist_ok=True)
    for offset in range(days+1):
        day=start+dt.timedelta(days=offset)
        if day.year!=2026:continue
        url=ESPN+"?"+urllib.parse.urlencode({"dates":day.strftime("%Y%m%d"),
                                             "groups":80,"limit":500})
        try:
            payload=request_json(url,timeout=10)
            if not isinstance(payload.get("events"),list):raise ValueError("Missing events")
            fetched+=1
            (raw/(str(day)+".json")).write_text(json.dumps({
                "retrieved_at_utc":dt.datetime.now(UTC).isoformat(),
                "source_url":url,"payload":payload})+"\n")
            for event in payload["events"]:
                g=extract_game(event)
                if g and not g["completed"] and parse_time(g["kickoff_utc"])>issue:
                    events[g["game_id"]]=g
        except Exception as exc:errors.append({"date":str(day),"error":str(exc)[:160]})
        time.sleep(.04)
    return list(events.values()),{"days_fetched":fetched,"days_requested":days+1,
                                  "errors":errors}

class WeatherProvider:
    def __init__(self,geo_cache=None):
        self.coords={};self.forecasts={};self.errors=[];self.forecast_requests=0
        self.persisted_coords={}
        if geo_cache and Path(geo_cache).is_file():
            try:
                self.persisted_coords=json.loads(Path(geo_cache).read_text())
                if not isinstance(self.persisted_coords,dict):raise ValueError("Invalid geo cache")
            except (ValueError,TypeError,json.JSONDecodeError):
                self.persisted_coords={}
        self.geocode_requests=0
        self.deadline_monotonic=time.monotonic()+160
        self.skipped_due_budget=0
    def geocode(self,city,state,country):
        key=(city,state,country)
        if key in self.coords:return self.coords[key]
        cache_key=json.dumps(key,separators=(",",":"))
        cached=self.persisted_coords.get(cache_key)
        if isinstance(cached,dict) and cached.get("precision")=="CITY_CENTROID_NOT_STADIUM_COORDINATE":
            self.coords[key]=cached
            return cached
        if time.monotonic()>=self.deadline_monotonic:
            self.skipped_due_budget+=1
            self.coords[key]=None
            return None
        self.geocode_requests+=1
        code="US" if country in ("USA","US") else "CA" if country in ("CAN","Canada") else None
        if not code or not city or not state:
            self.coords[key]=None;return None
        url=GEO+"?"+urllib.parse.urlencode({"name":city,
                    "count":100,"language":"en","format":"json","countryCode":code})
        try:
            response=request_json(url,timeout=8)
            match=geocode_match(response.get("results") or [],city,state,country)
        except Exception as exc:
            match=None;self.errors.append({"location":str(key),"provider":"geocoding",
                                           "error":str(exc)[:160]})
        self.coords[key]=match
        if match is not None:self.persisted_coords[cache_key]=match
        return match
    def forecast(self,geo,kickoff):
        ident=(geo["latitude"],geo["longitude"])
        if ident not in self.forecasts:
            if time.monotonic()>=self.deadline_monotonic:
                self.skipped_due_budget+=1
                self.forecasts[ident]=None
                return None
            url=WX+"?"+urllib.parse.urlencode({
                "latitude":geo["latitude"],"longitude":geo["longitude"],
                "hourly":HOURLY,"temperature_unit":"fahrenheit","wind_speed_unit":"mph",
                "precipitation_unit":"mm","timezone":"UTC","forecast_days":16})
            self.forecast_requests+=1
            try:
                payload=request_json(url,timeout=10)
                self.forecasts[ident]=(payload,dt.datetime.now(UTC).isoformat())
            except Exception as exc:
                self.errors.append({"location":str(ident),"provider":"forecast",
                                    "error":str(exc)[:160]})
                self.forecasts[ident]=None
        result=self.forecasts[ident]
        if result is None:return None
        payload,captured=result
        w=parse_forecast(payload.get("hourly") or {},kickoff)
        return {**w,"forecast_retrieved_utc":captured,"weather_source":"OPEN_METEO_LIVE_FORECAST",
                "weather_location_precision":"CITY_CENTROID"} if w else None

def run(raw_dir,output,reports=None,horizon_days=10,now=None,geo_cache=None,
        auto_official=False,alias_registry="data/archive/2026_team_aliases.csv"):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    issued=parse_time(now) if now else dt.datetime.now(UTC)
    report={"generated_at_utc":issued.isoformat(),"season":2026,
            "forecast_cutoff_utc":issued.isoformat(),"betting_status":"PASS_UNVALIDATED",
            "pregame_snapshots_historically_available":False,
            "weather_source":"https://open-meteo.com/en/docs",
            "schedule_source":ESPN,
            "injury_coverage_expected":"UNKNOWN_UNLESS_EXPLICIT_SOURCE_REPORT"}
    try:
        prev=load_archived_events(raw_dir)
        report["historical_completed_game_events"]=len(prev)
        upcoming,qa=load_upcoming(issued,horizon_days,output)
        report["schedule_fetch"]=qa
        source_rows=load_reports(reports)
        if auto_official:
            from scripts.official_availability import fetch_and_match
            official,official_qa=fetch_and_match(upcoming,alias_registry,output/"official")
            report["official_availability"]=official_qa
            source_rows+=official
            # Official publisher responses must be retrieved BEFORE our
            # context cutoff; compare their actual capture timestamps against
            # the updated as-of, never an earlier run-start timestamp.
            issued=dt.datetime.now(UTC)
            report["forecast_cutoff_utc"]=issued.isoformat()
        weather=WeatherProvider(geo_cache)
        context,metrics=build_context(upcoming,prev,issued.isoformat(),
            weather.geocode,weather.forecast,
            lambda game,when:evaluate(game,when,source_rows))
        report["coverage"]=metrics
        report["weather_provider"]={"geocode_requests":weather.geocode_requests,
            "forecast_requests":weather.forecast_requests,
            "errors":weather.errors,
            "skipped_due_time_budget":weather.skipped_due_budget,
            "geocode_and_forecast_max_processing_seconds":160}
        report["source_report_rows"]=len(source_rows)
        (output/"geo_cache.json").write_text(json.dumps(weather.persisted_coords,indent=2)+"\n")
        report["weather_provider"]["persistent_geocoded_cities"]=len(weather.persisted_coords)
        report["status"]="SOURCE_FETCH_FAILURE" if qa["errors"] else (
            "NO_UPCOMING_GAMES" if not context else
            "CONTEXT_RESEARCH_PARTIAL_COVERAGE" if (
                weather.skipped_due_budget>0 or
                metrics["forecast_available"]+metrics["indoor"]<metrics["upcoming_games"] or
                metrics["personnel_verified_both_teams"]<metrics["upcoming_games"]
            ) else "CONTEXT_RESEARCH_READY")
        report["game_records"]=len(context)
        report["safe_for_betting"]=False
        (output/"upcoming_game_context_2026.json").write_text(json.dumps({
            "captured_at_utc":dt.datetime.now(UTC).isoformat(),"asof_utc":issued.isoformat(),
            "games":context},indent=2)+"\n")
        names=["game_id","date_et","kickoff_utc","home","away","venue","venue_city","venue_state",
          "neutral","venue_indoor","home_days_since_last_game","away_days_since_last_game",
          "home_approx_straight_line_miles","away_approx_straight_line_miles",
          "home_home_base_verified_by_games","away_home_base_verified_by_games",
          "weather_status","temperature_f","wind_mph","gust_mph","precip_probability_pct",
          "injury_report_status","verified_qb_starters","personnel_warnings","betting_status"]
        with (output/"upcoming_game_context_2026.csv").open("w",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=names,extrasaction="ignore")
            writer.writeheader()
            for row in context:
                item=dict(row)
                for key in ("verified_qb_starters","personnel_warnings"):
                    item[key]=json.dumps(item[key])
                writer.writerow(item)
    except Exception as exc:
        report["status"]="CONTEXT_PIPELINE_FAILED";report["error"]=str(exc)[:350]
    (output/"context_manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--raw-dir",default="data/raw")
    p.add_argument("--output",default="data/context")
    p.add_argument("--availability-csv",default="data/manual/availability_2026.csv")
    p.add_argument("--horizon-days",type=int,default=10)
    p.add_argument("--geo-cache",default=None)
    p.add_argument("--auto-official",action="store_true")
    p.add_argument("--alias-registry",default="data/archive/2026_team_aliases.csv")
    args=p.parse_args()
    if not 1<=args.horizon_days<=14:raise SystemExit("horizon days must be 1..14")
    result=run(args.raw_dir,args.output,args.availability_csv,args.horizon_days,
               geo_cache=args.geo_cache,auto_official=args.auto_official,
               alias_registry=args.alias_registry)
    raise SystemExit(2 if result["status"] in ("SOURCE_FETCH_FAILURE","CONTEXT_PIPELINE_FAILED") else 0)

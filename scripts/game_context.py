"""2026 future-game context from ESPN scoreboard snapshots.

Rest and approximate venue-city travel are descriptive, not trained adjustments.
Only games with kickoff > current UTC collection time are considered.
"""
import csv,datetime as dt,json,math,re
from collections import Counter,defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

UTC=dt.timezone.utc
ET=ZoneInfo("America/New_York")
STATE_NAMES=dict(zip(
"AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split(),
"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia".split("|")))

def parse_time(value):
    x=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if x.tzinfo is None:raise ValueError("Timestamp must include timezone")
    return x.astimezone(UTC)

def place(competition):
    venue=competition.get("venue") or {}
    addr=venue.get("address") or {}
    return {"venue_id":str(venue.get("id") or ""),
      "venue":str(venue.get("fullName") or ""),
      "city":str(addr.get("city") or "").strip(),
      "state":str(addr.get("state") or "").strip(),
      "country":str(addr.get("country") or "").strip(),
      "indoor":venue.get("indoor") if isinstance(venue.get("indoor"),bool) else None}

def extract_game(event):
    try:
        if int((event.get("season") or {}).get("year",0))!=2026:return None
        competition=event["competitions"][0]
        sides=competition["competitors"]
        home=next(x for x in sides if x.get("homeAway")=="home")
        away=next(x for x in sides if x.get("homeAway")=="away")
        kickoff=parse_time(event["date"])
        hid=str(home["id"]);aid=str(away["id"])
        hname=home["team"]["displayName"];aname=away["team"]["displayName"]
        if not all((hid,aid,hname,aname)) or hid==aid:return None
        return {"game_id":str(event["id"]),
          "kickoff_utc":kickoff.isoformat().replace("+00:00","Z"),
          "date_et":kickoff.astimezone(ET).date().isoformat(),
          "home_id":hid,"away_id":aid,"home":hname,"away":aname,
          "neutral":bool(competition.get("neutralSite",False)),
          "completed":bool((event.get("status") or {}).get("type",{}).get("completed",False)),
          **place(competition)}
    except (KeyError,IndexError,TypeError,ValueError,StopIteration):
        return None

def load_archived_events(raw_dir):
    """Deduplicate identical event IDs from date-scoped, saved ESPN responses."""
    events={}
    for path in sorted(Path(raw_dir).glob("*.json")):
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
            for ev in data["payload"]["events"]:
                g=extract_game(ev)
                if g and g["completed"]:events[g["game_id"]]=g
        except (KeyError,TypeError,json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid cached ESPN snapshot {path}: {exc}") from exc
    return list(events.values())

def home_venue_city(prior_games):
    sites=defaultdict(Counter)
    for g in prior_games:
        if g["completed"] and not g["neutral"] and g["city"] and g["state"]:
            sites[g["home_id"]][(g["city"],g["state"],g["country"])]+=1
    result={}
    for team,venues in sites.items():
        (city,state,country),votes=venues.most_common(1)[0]
        total=sum(venues.values())
        if votes>=2 and votes/total>=.6:
            result[team]={"city":city,"state":state,"country":country,
                          "home_games_supporting":votes,"home_games_observed":total}
    return result

def last_completed(prior_games,team_id,issue):
    eligible=[parse_time(g["kickoff_utc"]) for g in prior_games
              if team_id in (g["home_id"],g["away_id"]) and
              g["completed"] and parse_time(g["kickoff_utc"])<issue]
    return max(eligible) if eligible else None

def distance_miles(first,second):
    a,b=first; c,d=second
    return 3958.7613*2*math.asin(min(1,math.sqrt(
      math.sin(math.radians(c-a)/2)**2+
      math.cos(math.radians(a))*math.cos(math.radians(c))*
      math.sin(math.radians(d-b)/2)**2)))

def canonical_city(s):
    return re.sub(r"[^a-z0-9]","",s.lower())

def geocode_match(results,city,state,country="USA"):
    country_code="US" if country in ("USA","US") else "CA" if country in ("Canada","CAN") else None
    if country_code is None:return None
    allowed_state=STATE_NAMES.get(state.upper(),state)
    matches=[p for p in results if p.get("country_code")==country_code
       and canonical_city(p.get("name",""))==canonical_city(city)
       and (canonical_city(p.get("admin1",""))==canonical_city(allowed_state)
            or canonical_city(p.get("admin1",""))==canonical_city(state))]
    if len(matches)!=1:return None
    p=matches[0]
    lat,lon=p.get("latitude"),p.get("longitude")
    if not isinstance(lat,(int,float)) or not isinstance(lon,(int,float)):return None
    if not (-90<=lat<=90 and -180<=lon<=180):return None
    return {"latitude":float(lat),"longitude":float(lon),"geonames_id":p.get("id"),
            "name":p.get("name"),"admin1":p.get("admin1"),"country_code":country_code,
            "precision":"CITY_CENTROID_NOT_STADIUM_COORDINATE"}

def parse_forecast(hourly,kickoff):
    times=hourly.get("time") or []
    if not times:return None
    timestamp=kickoff.astimezone(UTC).replace(minute=0,second=0,microsecond=0)
    code=timestamp.strftime("%Y-%m-%dT%H:%M")
    if code not in times:return None
    i=times.index(code)
    fields={"temperature_f":"temperature_2m","wind_mph":"wind_speed_10m",
            "gust_mph":"wind_gusts_10m","precip_probability_pct":"precipitation_probability",
            "precip_mm":"precipitation"}
    out={}
    for label,field in fields.items():
        arr=hourly.get(field)
        val=arr[i] if isinstance(arr,list) and len(arr)>i else None
        out[label]=val if isinstance(val,(int,float)) and math.isfinite(val) else None
    return out if any(v is not None for v in out.values()) else None

def build_context(upcoming,completed,issued_at,geolocate,forecast,personnel_for_game):
    issued=parse_time(issued_at)
    homes=home_venue_city(completed)
    rows=[];issues=[]
    for g in sorted(upcoming,key=lambda x:(x["kickoff_utc"],x["game_id"])):
        kickoff=parse_time(g["kickoff_utc"])
        if g["completed"] or kickoff<=issued:continue
        site=(g["city"],g["state"],g["country"])
        geo=geolocate(*site) if g["city"] and g["state"] else None
        weather_status="UNKNOWN"
        wx={}
        if g["indoor"] is True:weather_status="INDOOR_NOT_APPLICABLE"
        elif geo is None:weather_status="UNAVAILABLE_GEOLOCATION"
        else:
            try:
                wx=forecast(geo,kickoff) or {}
                weather_status="LIVE_FORECAST" if wx else "UNAVAILABLE_FORECAST"
            except Exception as exc:
                weather_status="FORECAST_ERROR"
                issues.append({"game_id":g["game_id"],"field":"weather","error":str(exc)[:180]})
        injury=personnel_for_game(g,issued)
        record={"game_id":g["game_id"],"date_et":g["date_et"],"kickoff_utc":g["kickoff_utc"],
                "home":g["home"],"away":g["away"],"home_team_id":g["home_id"],
                "away_team_id":g["away_id"],"neutral":g["neutral"],
                "venue":g["venue"],"venue_city":g["city"],"venue_state":g["state"],
                "venue_indoor":g["indoor"],"venue_location_quality":geo["precision"] if geo else "UNKNOWN",
                "weather_status":weather_status,**wx,
                "injury_report_status":injury["coverage_status"],
                "verified_qb_starters":injury["confirmed_qb_starters"],
                "injury_reports":injury["injuries"],"availability_reports":injury["injuries"],
                "qb_availability_reports":[x for x in injury["injuries"] if x["position"]=="QB"],
                "qb_starters_confirmed_count":len(injury["confirmed_qb_starters"]),
                "personnel_warnings":injury["warnings"],
                "forecast_issue_utc":issued.isoformat().replace("+00:00","Z"),
                "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
        for side in ("away","home"):
            team_id=g[side+"_id"]
            last=last_completed(completed,team_id,issued)
            record[side+"_days_since_last_game"]=round((kickoff-last).total_seconds()/86400,2) if last else None
            base=homes.get(team_id)
            from_geo=geolocate(base["city"],base["state"],base["country"]) if base else None
            record[side+"_home_base_verified_by_games"]=base["home_games_supporting"] if base else 0
            record[side+"_approx_straight_line_miles"]=round(distance_miles(
                (from_geo["latitude"],from_geo["longitude"]),
                (geo["latitude"],geo["longitude"])),1) if from_geo and geo else None
        rows.append(record)
    return rows,{"upcoming_games":len(rows),
        "forecast_available":sum(r["weather_status"]=="LIVE_FORECAST" for r in rows),
        "indoor":sum(r["weather_status"]=="INDOOR_NOT_APPLICABLE" for r in rows),
        "venue_coordinates_available":sum(r["venue_location_quality"]!="UNKNOWN" for r in rows),
        "both_rest_available":sum(r["home_days_since_last_game"] is not None and
                                  r["away_days_since_last_game"] is not None for r in rows),
        "both_travel_approximations_available":sum(r["home_approx_straight_line_miles"] is not None and
                                                r["away_approx_straight_line_miles"] is not None for r in rows),
        "personnel_verified_both_teams":sum(r["injury_report_status"]=="BOTH_TEAMS_VERIFIED" for r in rows),
        "errors":issues,"betting_status":"PASS_UNVALIDATED"}

"""Refresh named IANA time zones for existing verified GeoNames city IDs.

Only the publisher's exact GeoNames ID, coordinates, country and zone are
accepted. No heuristic time-zone by state or longitude. This is RESEARCH-ONLY:
newly fetched geographical facts do not imply historical pregame publication.
"""
import argparse,concurrent.futures,datetime as dt,json,math,urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

STATUS="GEONAMES_CITY_ID_TIMEZONE_ENRICHMENT_RESEARCH_ONLY"
URL="https://geocoding-api.open-meteo.com/v1/get?id="

def valid_timezone_record(original,response):
    try:
        if (not isinstance(response,dict) or int(response["id"])!=int(original["geonames_id"])
            or response["country_code"]!=original["country_code"]
            or abs(float(response["latitude"])-float(original["latitude"]))>.025
            or abs(float(response["longitude"])-float(original["longitude"]))>.025):
            return None
        zone=response["timezone"]
        if not isinstance(zone,str) or "/" not in zone:return None
        ZoneInfo(zone)
        return zone
    except (KeyError,ValueError,TypeError,OverflowError):
        return None

def retrieve(source,max_requests=125,workers=5,fetch=None):
    if not isinstance(source,dict) or not 0<workers<=8:
        raise ValueError("Malformed cached geocode")
    prepared={key:dict(geo) for key,geo in source.items()}
    needed=[(key,geo) for key,geo in prepared.items()
            if geo.get("timezone") in (None,"") and
               isinstance(geo.get("geonames_id"),int)]
    if len(needed)>max_requests:raise ValueError("Bounded timezone enrichment request budget exceeded")
    def request(gid):
        req=urllib.request.Request(URL+str(gid),headers={
            "User-Agent":"cfb-model-venue-context/0.4","Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=8) as f:
            blob=f.read(24000)
        return json.loads(blob)
    api=fetch or request
    statuses=[]
    def task(item):
        key,original=item
        try:
            response=api(original["geonames_id"])
            zone=valid_timezone_record(original,response)
            return key,zone,"MATCHED_ID_COORD_COUNTRY" if zone else "ID_OR_LOCATION_MISMATCH"
        except Exception as e:
            return key,None,"FETCH_FAILED_"+type(e).__name__
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for key,zone,reason in executor.map(task,needed):
            if zone is not None:prepared[key]["timezone"]=zone
            statuses.append(reason)
    return prepared,{"status":STATUS,"requested":len(needed),
        "completed_with_verified_timezone":statuses.count("MATCHED_ID_COORD_COUNTRY"),
        "unresolved":sum(s!="MATCHED_ID_COORD_COUNTRY" for s in statuses),
        "original_geocode_count":len(source),
        "enriched_geocode_count":sum(bool(v.get("timezone")) for v in prepared.values()),
        "historical_source_publication_authenticated":False,
        "betting_status":"PASS_UNVALIDATED"}

def run(cache_path,out_path):
    source=json.loads(Path(cache_path).read_text())
    updated,summary=retrieve(source)
    path=Path(out_path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(updated,indent=2)+"\n")
    Path(str(path)+".audit.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary))
    return summary
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--cache",required=True)
    p.add_argument("--output",required=True);a=p.parse_args();run(a.cache,a.output)

"""Source-matched ESPN school colors/logos for an informational game-card identity.

No generated colors masquerading as a team's official palette; missing identity
falls back to a neutral monogram. Asset URLs MUST be ESPN's own CDN and never
transformed or rehosted. This does not change the frozen research forecast.
"""
import argparse,datetime as dt,json,re,urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from scripts.game_context import parse_time
STATUS="MATCHED_ESPN_TEAM_IDENTITY_DISPLAY_ONLY"
BASE="https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
HEX=re.compile(r"^[0-9a-fA-F]{6}$")
def logo_url(team):
    candidate=team.get("logo")
    if not candidate:
        for entry in team.get("logos") or []:
            if isinstance(entry,dict) and isinstance(entry.get("href"),str):
                candidate=entry["href"];break
    if not isinstance(candidate,str):return None
    u=urlsplit(candidate)
    if (u.scheme!="https" or u.hostname not in ("a.espncdn.com","a1.espncdn.com")
        or u.username or u.password or u.port not in (None,443)
        or not re.fullmatch(r"/i/teamlogos/[A-Za-z0-9/_-]+\.png",u.path)
        or u.query or u.fragment):
        return None
    return candidate
def parse_brand(team):
    color=team.get("color")
    if not isinstance(color,str) or not HEX.fullmatch(color):color=None
    abbr=team.get("abbreviation")
    if not isinstance(abbr,str) or not re.fullmatch("[A-Za-z0-9&.-]{1,8}",abbr):
        abbr=None
    return {"color":("#"+color.lower()) if color else None,
        "monogram":abbr or None,"logo_url":logo_url(team),
        "source":"ESPN_MATCHED_TEAM_METADATA","confirmed_mark_license":False}
def capture(dashboard,payload):
    if dashboard.get("schema_version")!=2 or dashboard.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Invalid research board")
    indexed={str(g["game_id"]):g for g in dashboard["games"]}
    if len(indexed)!=len(dashboard["games"]):raise ValueError("Duplicate dashboard game id")
    count=0;eligible=0;seen=set()
    for event in payload.get("events") or []:
        gid=str(event.get("id"))
        g=indexed.get(gid)
        if g is None or gid in seen:continue
        seen.add(gid)
        if parse_time(event["date"])!=parse_time(g["kickoff_utc"]):continue
        comps=event.get("competitions") or []
        if len(comps)!=1:continue
        competitors=comps[0].get("competitors") or []
        if len(competitors)!=2:continue
        by_side={s.get("homeAway"):s.get("team",{}) for s in competitors}
        if set(by_side)!={"home","away"}:continue
        if (by_side["home"].get("displayName")!=g["home_team"] or
            by_side["away"].get("displayName")!=g["away_team"]):
            continue
        eligible+=1
        for side in ("home","away"):
            brand=parse_brand(by_side[side])
            g["team_brand_"+side]=brand
            count+=bool(brand["color"] or brand["logo_url"])
    for g in dashboard["games"]:
        for side in ("home","away"):
            g.setdefault("team_brand_"+side,None)
    dashboard["team_brand_display"]={"status":STATUS,"matched_games":eligible,
        "sourced_team_marks_or_colors":count,"changes_frozen_forecast":False,
        "logo_source":"ESPN CDN only; third-party team marks belong to their respective owners",
        "missing_brand_fallback":"Neutral text monogram; never guess licensed identity"}
    return dashboard
def fetch_board(board):
    now=dt.datetime.now(dt.timezone.utc)
    upcoming=[parse_time(g["kickoff_utc"]) for g in board["games"]
              if parse_time(g["kickoff_utc"])>now]
    if not upcoming:return {"events":[]}
    earliest=min(upcoming).date()-dt.timedelta(days=1)
    latest=max(upcoming).date()+dt.timedelta(days=1)
    # Bound request so an accidental long-range fixture doesn't fetch seasons.
    latest=min(latest,earliest+dt.timedelta(days=15))
    url=BASE+"?dates="+earliest.strftime("%Y%m%d")+"-"+latest.strftime("%Y%m%d")+"&groups=80&limit=500"
    req=urllib.request.Request(url,headers={"User-Agent":"cfb-lab-team-identity/1.0",
                                            "Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=14) as response:
        return json.load(response)
def run(dashboard_path,fetcher=fetch_board):
    path=Path(dashboard_path);board=json.loads(path.read_text())
    try:payload=fetcher(board)
    except (OSError,ValueError,TimeoutError,json.JSONDecodeError) as e:
        payload={"events":[]}
        failure=type(e).__name__
    else:failure=None
    board=capture(board,payload)
    board["team_brand_display"]["fetch_error_type"]=failure
    path.write_text(json.dumps(board,indent=2,allow_nan=False)+"\n")
    print(json.dumps(board["team_brand_display"]))
    return board
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--dashboard",required=True)
    run(p.parse_args().dashboard)

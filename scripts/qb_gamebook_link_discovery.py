"""Discovery-only official athletics gamebook link worklist.

Takes postgame REVIEW targets (already matched to frozen pregame QB forecasts),
then fetches the corresponding athletics team's public 2026 schedule pages.
Only literal hrefs on an HTTPS same-host page are candidates; no URL is
manufactured and no names/starting status are inferred from passing leaders.

School hosts are external-directory CANDIDATES and link matching is a hint.
The existing independently checked game/score/date/STARTERS reviewer must
validate a source before it enters the official-starter manifest.
"""
import argparse,csv,datetime as dt,json,re,urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlsplit,unquote
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time

STATUS="QB_GAMEBOOK_LINK_CANDIDATES_REVIEW_REQUIRED"
SOURCE_STATUS="EXTERNALLY_CROSS_REFERENCED_ATHLETICS_DIRECTORY_CANDIDATES_V1"
MAX_HTML=2_500_000
MAX_LINKS_PER_SCHOOL=400
MAX_SCHOOLS=20
EASTERN=ZoneInfo("America/New_York")
GAMEBOOK=re.compile(r"^/sports/football/stats/2026/([a-z0-9-]+)/boxscore/([0-9]+?)/?$",re.I)
HEADERS={"User-Agent":"CFB2026-SourceReview/0.1","Accept":"text/html"}
STOP={"fighting","golden","state","university","college","at","of","the"}
ALIASES={
    "texas a&m":"texas-am","ole miss":"ole-miss","brigham young":"byu",
    "southern california":"usc","usc":"usc","ucla":"ucla",
    "ucf":"ucf","utsa":"utsa","louisiana state":"lsu",
    "app state":"appalachian-state",
    "miami (oh)":"miami-oh","miami oh":"miami-oh",
    "miami (fl)":"miami","miami fl":"miami",
    "southern methodist":"smu","north carolina state":"nc-state",
    "pitt":"pittsburgh","hawaii":"hawaii",
}

class Hrefs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            href=dict(attrs).get("href")
            if href and len(self.hrefs)<MAX_LINKS_PER_SCHOOL*8:self.hrefs.append(href)

def _host(value):
    parsed=urlsplit(value)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError("Unsafe athletics host")
    return parsed.hostname.lower().removeprefix("www.")

def safe_href(href,page,expected_host):
    try:
        url=urljoin(page,href)
        parsed=urlsplit(url)
        if (_host(url)!=expected_host or parsed.query or parsed.fragment
            or not GAMEBOOK.fullmatch(unquote(parsed.path))):
            return None
        return url
    except (ValueError,TypeError):return None

def _stem(name):
    s=re.sub(r"[^a-z0-9]+","-",name.casefold()).strip("-")
    return s

def opponent_slugs(name):
    if not isinstance(name,str) or not name.strip():raise ValueError("Missing opponent")
    normalized=" ".join(name.casefold().split())
    opts=set()
    for key,alias in ALIASES.items():
        if normalized==key or normalized.startswith(key+" "):
            opts.add(alias)
    words=normalized.split()
    if not words:return opts
    # Candidate link slugs often omit mascot/last words. These are hints,
    # never a verified match; never create a boxscore URL from the slug.
    for k in range(1,min(4,len(words))+1):
        candidate=_stem(" ".join(words[:k]))
        if candidate:opts.add(candidate)
    return opts

def _candidate_match(slug,opponent):
    stems=opponent_slugs(opponent)
    hits=sorted((s for s in stems if slug==s),key=len,reverse=True)
    if hits:return "EXACT_OPPONENT_SLUG",hits[0]
    hits=sorted((s for s in stems if len(s)>=5 and (slug.startswith(s+"-") or s.startswith(slug+"-"))),
                key=len,reverse=True)
    return ("PARTIAL_OPPONENT_SLUG_NEEDS_REVIEW",hits[0]) if hits else (None,None)

def default_fetch(url,host):
    if _host(url)!=host:raise ValueError("Off-host school schedule request")
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=15) as response:
        if _host(response.geturl())!=host or response.geturl()!=url:
            raise ValueError("Redirected school schedule request")
        if "text/html" not in response.headers.get("Content-Type","").lower():
            raise ValueError("Non-HTML athletics schedule")
        data=response.read(MAX_HTML+1)
    if len(data)>MAX_HTML:raise ValueError("Oversized athletics schedule")
    return data.decode("utf-8","replace")

def discover(targets,directory,asof_utc,fetch=default_fetch,max_schools=MAX_SCHOOLS):
    now=parse_time(asof_utc)
    if (directory.get("status")!=SOURCE_STATUS or directory.get("season")!=2026
        or len(directory.get("schools",[]))!=directory.get("expected_teams") or
        not isinstance(targets,list) or not 1<=max_schools<=MAX_SCHOOLS):
        raise ValueError("Untrusted official athletics directory / targets")
    sites={s["team"]:s for s in directory["schools"]}
    if len(sites)!=len(directory["schools"]):raise ValueError("Duplicate athletics school")
    selected={}
    for row in targets:
        gid=str(row.get("game_id",""))
        if not re.fullmatch(r"\d{6,12}",gid):raise ValueError("Invalid review game ID")
        team=row["team"]
        if team not in sites or row.get("review_required") not in ("True",True,"true","1"):
            raise ValueError("Not a reviewed completed game/team target")
        kickoff=parse_time(row["kickoff_utc"])
        if kickoff>=now:raise ValueError("Target kickoff has not passed")
        key=(gid,team)
        if key in selected:raise ValueError("Duplicate review target")
        selected[key]=row
    # Prefer earliest completed games and deterministic team ordering. No
    # background scanning of all 138 schools on every settlement.
    order=sorted({team for _,team in selected},
                 key=lambda team:(min(parse_time(x["kickoff_utc"]) for (gid,t),x in selected.items() if t==team),team))
    # Rotate deterministic daily batches. Otherwise the same earliest
    # eight inaccessible schools would starve the remaining national queue.
    # Re-running the same date yields the same audit cohort.
    offset=((now.date()-dt.date(2026,8,1)).days*max_schools)%len(order) if order else 0
    scheduled=(order[offset:]+order[:offset])[:max_schools]
    discovered=[];errors=[]
    for team in scheduled:
        site=sites[team]
        origin=site.get("athletics_homepage")
        try:
            host=_host(origin)
            if host!=site.get("source_host"):
                raise ValueError("Athletics directory host mismatch")
            page="https://"+host+"/sports/football/schedule/2026"
            html=fetch(page,host)
            if not isinstance(html,str) or len(html)>MAX_HTML:
                raise ValueError("Invalid returned athletics schedule")
            parser=Hrefs();parser.feed(html)
            urls=sorted({s for href in parser.hrefs
                         if (s:=safe_href(href,page,host)) is not None})[:MAX_LINKS_PER_SCHOOL]
            for (gid,t),target in selected.items():
                if t!=team:continue
                opponent=target["opponent"]
                found=[]
                for url in urls:
                    match=GAMEBOOK.fullmatch(urlsplit(url).path)
                    if not match:continue
                    rule,matched=_candidate_match(match.group(1).lower(),opponent)
                    if rule:
                        found.append({"game_id":gid,"team":team,"opponent":opponent,
                            "kickoff_utc":target["kickoff_utc"],
                            "source_url_candidate":url,"schedule_page_url":page,
                            "match_rule":rule,"matched_slug":matched,
                            "discovery_source_host":host,
                            "school_publisher_independently_verified":False,
                            "game_identity_verified":False,
                            "starter_identity_verified":False,
                            "manually_review_game_score_date_and_starters":True,
                            "source_status":STATUS})
                discovered.extend(found)
        except (OSError,ValueError,TimeoutError,TypeError) as exc:
            errors.append({"team":team,"reason":type(exc).__name__,
                           "note":"Official-school schedule candidate inaccessible or malformed"})
    return {"status":STATUS,"season":2026,"observed_at_utc":now.isoformat(),
        "source":"ATHLETICS_DIRECTORY_CANDIDATE_SCHEDULE_LINKS",
        "review_targets":len(selected),"school_sites_scanned":len(scheduled),
        "school_sites_deferred":len(order)-len(scheduled),
        "scan_offset":offset,"scanned_team_names":scheduled,
        "source_errors":errors[:MAX_SCHOOLS],
        "candidate_links_found":len(discovered),"candidates":discovered,
        "ready_to_be_starter_labels":False,
        "no_automatic_official_confirmation":True,
        "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}

def run(review_csv,sites,output,max_schools=MAX_SCHOOLS):
    with Path(review_csv).open(newline="",encoding="utf-8-sig") as f:
        targets=list(csv.DictReader(f))
    directory=json.loads(Path(sites).read_text(encoding="utf-8"))
    data=discover(targets,directory,dt.datetime.now(dt.timezone.utc).isoformat(),
                  max_schools=max_schools)
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("x",encoding="utf-8") as f:json.dump(data,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({k:v for k,v in data.items() if k not in ("candidates","source_errors")}))
    return data

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--review-csv",required=True)
    p.add_argument("--sites",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--max-schools",type=int,default=MAX_SCHOOLS)
    args=p.parse_args()
    run(args.review_csv,args.sites,args.output,args.max_schools)

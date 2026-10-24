"""Season-wide discovery of school-authored football notes, depth charts and injury information.

Source links are discoverable candidates, NOT verified athlete availability or QB1.
Never equate a directory listing, HTTP 200, headline, or PDF filename with a
timestamped game-specific starting-QB or injury claim.
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag
import urllib.request

HEADERS={"User-Agent":"CFB2026-Source-Audit/0.4 (public school athletics research)",
         "Accept":"text/html,application/xhtml+xml"}
MAX_BYTES=5_000_000
MAX_LINKS=2500
BAD_ENDPOINTS=("/roster","/stats","/staff","/coaches","/tickets","/shop","/watch","/video",
               "/basketball","/soccer","/baseball","/softball")
CATEGORIES={
    "game_notes":re.compile(r"\bgame[ -]?notes?\b|\bweekly[ -]?notes?\b|\bfootball[ -]?notes?\b",re.I),
    "depth_chart":re.compile(r"\bdepth[ -]?charts?\b|\btwo[ -]?deep\b",re.I),
    "injury_report":re.compile(r"\binjur(?:y|ies)[ -]?(?:reports?|updates?|lists?)\b|\bavailability[ -]?(?:reports?|updates?)\b",re.I)
}
FOOTBALL=re.compile(r"\bfootball\b",re.I)
BAD_NAV=re.compile(r"\b(?:basketball|volleyball|soccer|baseball|softball|lacrosse|hockey)\b",re.I)
NEWS=re.compile(r"\b(news|stories|archives|articles)\b",re.I)
SCHEDULE=re.compile(r"\bschedule\b",re.I)

class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[]
        self.current=None
    def handle_starttag(self,tag,attrs):
        if tag!="a" or self.current is not None:return
        attrs=dict(attrs)
        href=attrs.get("href","")
        if href:
            self.current={"href":href,"text":((attrs.get("title") or "")+" "+(attrs.get("aria-label") or "")).strip()}
    def handle_data(self,data):
        if self.current is not None:
            self.current["text"]+=((" "+data) if data else "")
    def handle_endtag(self,tag):
        if tag=="a" and self.current is not None:
            self.current["text"]=" ".join(html.unescape(self.current["text"]).split())[:160]
            self.links.append(self.current)
            self.current=None

def host_allowed(url,origin):
    a=urlsplit(url);b=urlsplit(origin)
    ah=(a.hostname or "").lower().removeprefix("www.")
    bh=(b.hostname or "").lower().removeprefix("www.")
    return (a.scheme=="https" and bool(a.hostname) and ah==bh
            and not a.username and not a.password and a.port in (None,443)
            and not a.fragment)

def resolved_links(document,page,origin):
    parser=Links();parser.feed(document.decode("utf-8",errors="replace"))
    found=[];seen=set()
    for raw in parser.links[:MAX_LINKS]:
        link,_=urldefrag(urljoin(page,raw["href"]))
        if not host_allowed(link,origin) or link in seen:continue
        seen.add(link)
        found.append({"url":link,"text":raw["text"]})
    return found

def default_fetch(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=10) as response:
        final=response.geturl()
        kind=response.headers.get("Content-Type","").lower()
        data=response.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:raise ValueError("PAGE_SIZE_LIMIT")
        if ("text/html" not in kind and "application/xhtml+xml" not in kind
                and b"<html" not in data[:500].lower()):
            raise ValueError("NOT_HTML")
        return final,data

def safe_page(url,origin,fetch):
    if not host_allowed(url,origin):raise ValueError("UNTRUSTED_PAGE")
    final,data=fetch(url)
    if not host_allowed(final,origin):raise ValueError("CROSS_DOMAIN_REDIRECT:"+str(urlsplit(final).hostname))
    return resolved_links(data,final,origin),hashlib.sha256(data).hexdigest()

def football_pages(home_links,home):
    scored=[]
    for link in home_links:
        u=link["url"].lower().split("?")[0].rstrip("/")
        text=link["text"].lower()
        if BAD_NAV.search(text) or any(x in u for x in BAD_ENDPOINTS):continue
        if not (FOOTBALL.search(text) or "/football" in u):continue
        score=0
        if u.endswith("/sports/football"):score+=12
        if "/sports/football" in u:score+=6
        if text in ("football","football home"):score+=5
        if u.endswith("/football"):score+=5
        if "football" in text:score+=2
        if "football" in u:score+=2
        if u.endswith(".pdf"):continue
        if NEWS.search(text) or SCHEDULE.search(text):score-=4
        if "/news/" in u:score-=5
        scored.append((score,link["url"]))
    scored.sort(key=lambda t:-t[0])
    return list(dict.fromkeys(u for _,u in scored))[:3]

def secondary_pages(links):
    scored=[]
    for link in links:
        text=link["text"];url=link["url"].lower()
        if url.endswith(".pdf"):continue
        # Only follow football-section navigation pages, never unrelated sports.
        if BAD_NAV.search(text) or any(x in url for x in BAD_ENDPOINTS):continue
        score=0
        if ("football" in url or FOOTBALL.search(text)) and NEWS.search(text+" "+url):score+=6
        if ("football" in url or FOOTBALL.search(text)) and SCHEDULE.search(text+" "+url):score+=5
        if CATEGORIES["game_notes"].search(text+" "+url):score+=8
        if CATEGORIES["depth_chart"].search(text+" "+url):score+=8
        if CATEGORIES["injury_report"].search(text+" "+url):score+=8
        if score:scored.append((score,link["url"]))
    scored.sort(key=lambda a:-a[0])
    return list(dict.fromkeys(u for _,u in scored))[:2]

def extract_candidates(links,page,school,store):
    for link in links:
        text=link["text"];url=link["url"]
        path=urlsplit(url).path.lower()
        if BAD_NAV.search(text):continue
        if path.endswith((".jpg",".png",".gif",".mp4",".svg",".css",".js")):continue
        # Avoid generic keyword overlap in navigation footer and advertisements.
        label=(text+" "+path.replace("-"," ").replace("_"," "))[:350]
        for category,pattern in CATEGORIES.items():
            if not pattern.search(label):continue
            # Accept only pages/documents directly linked from school-owned pages.
            if len(store[category])>=12:continue
            if any(x["url"]==url for x in store[category]):continue
            store[category].append({
                "url":url,"label":text[:160],"found_on":page,
                "asset_kind":"PDF" if path.endswith(".pdf") else "WEB_PAGE",
                "status":"OFFICIAL_SITE_LINK_CANDIDATE_NEEDS_DOCUMENT_REVIEW",
                "game_specific_evidence_verified":False})

def inspect_school(school,fetch=default_fetch):
    root=school["athletics_homepage"]
    team=school["team"]
    outcome={"team":team,"official_athletics_homepage":root,
             "crawl_status":"NOT_STARTED","football_page":None,
             "football_page_status":"NOT_LOCATED",
             "pages_checked":[],"game_notes":[],"depth_chart":[],"injury_report":[],
             "game_specific_player_evidence_verified":False}
    first=[]
    try:
        first,hashsum=safe_page(root,root,fetch)
        outcome["pages_checked"].append({"url":root,"sha256":hashsum})
    except Exception as exc:
        outcome["homepage_error_type"]=type(exc).__name__
        outcome["homepage_error_reason"]=str(exc)[:180]
    options=football_pages(first,root)
    # Explicitly probe common athletics-site football routes only on the
    # school-owned host. These are guesses until a live page responds.
    base=root.rstrip("/")
    from urllib.parse import urlunsplit
    parsed=urlsplit(root)
    origin=urlunsplit((parsed.scheme,parsed.netloc,"","","")).rstrip("/")
    for path in ("/sports/football","/sport/football","/sports/m-footbl",
                 "/sports/football/index","/sports/football/index.aspx",
                 "/index.aspx?path=football"):
        url=origin+path
        if url not in options:options.append(url)
    football=None
    failed_probes=[]
    for page in options:
        try:
            links,digest=safe_page(page,root,fetch)
            football=(page,links,digest)
            break
        except Exception as exc:
            failed_probes.append({"url":page,"error_type":type(exc).__name__,
                                  "reason":str(exc)[:160]})
            continue
    if football is None:
        outcome["crawl_status"]="FOOTBALL_PAGE_FETCH_FAILED"
        outcome["football_probe_failures"]=failed_probes[:12]
        return outcome
    page,links,digest=football
    outcome["football_page"]=page
    outcome["football_page_status"]="LIVE_SCHOOL_DOMAIN_LINK_VERIFIED"
    outcome["pages_checked"].append({"url":page,"sha256":digest})
    extract_candidates(first,root,school,outcome)
    extract_candidates(links,page,school,outcome)
    for next_page in secondary_pages(links):
        if next_page==page:continue
        try:
            sub,digest=safe_page(next_page,root,fetch)
        except Exception:
            continue
        outcome["pages_checked"].append({"url":next_page,"sha256":digest})
        extract_candidates(sub,next_page,school,outcome)
    outcome["crawl_status"]="AUDITED"
    return outcome

def run(sites,output,workers=12):
    source=json.loads(Path(sites).read_text(encoding="utf-8"))
    schools=source.get("schools",[])
    if source.get("season")!=2026 or source.get("expected_teams")!=138 or len(schools)!=138:
        raise ValueError("Expected canonical 138-school 2026 directory")
    if len({x["team"] for x in schools})!=138:raise ValueError("Duplicate schools")
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max(workers,1),16)) as pool:
        results=list(pool.map(inspect_school,schools))
    counts={k:sum(bool(s[k]) for s in results) for k in CATEGORIES}
    output_data={"status":"CANDIDATE_DISCOVERY_NOT_PLAYER_VERIFICATION",
                 "season":2026,"expected_teams":138,
                 "captured_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
                 "football_pages_live":sum(s["football_page_status"]=="LIVE_SCHOOL_DOMAIN_LINK_VERIFIED" for s in results),
                 "schools_audited":sum(s["crawl_status"]=="AUDITED" for s in results),
                 "school_sources_with_candidates":counts,
                 "confirmed_game_specific_player_evidence_count":0,
                 "schools":results}
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(output_data,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in output_data.items() if k!="schools"}))
    return output_data

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--sites",required=True);p.add_argument("--output",required=True)
    p.add_argument("--workers",type=int,default=12)
    a=p.parse_args();run(a.sites,a.output,a.workers)

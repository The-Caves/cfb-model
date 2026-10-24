"""Source-labelled 2026 QB1/QB2/QB3 chart positions on the research site.

Ourlads public college-football depth charts are THIRD-PARTY DEPTH-CHART
PROJECTIONS, NOT official game-specific starting QB confirmations. Never
rewrite frozen predictions, official starter evidence or injury statuses.
Only ingest three explicitly numbered QB cells from bounded public pages.
"""
import argparse
import concurrent.futures
import csv
import datetime as dt
from html.parser import HTMLParser
import json
import re
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlsplit, parse_qs
from scripts.game_context import parse_time

INDEX="https://www.ourlads.com/ncaa-football-depth-charts/"
HOST="www.ourlads.com"
SOURCE="OURLADS_THIRD_PARTY_PROJECTED_DEPTH_CHART"
ALIASES={
    "mississippi":"ole miss",
    "miami":"miami (fl)",
    "miami fl":"miami (fl)",
    "north carolina state":"nc state",
    "louisiana-monroe":"louisiana monroe",
    "louisiana":"louisiana",
    "appalachian state":"appalachian state",
    "smu":"smu",
    "connecticut":"uconn",
    "florida international":"fiu",
    "central florida":"ucf",
    "south florida":"usf",
    "miami ohio":"miami oh",
    "texas-san antonio":"utsa",
    "alabama-birmingham":"uab",
    "southern miss":"southern miss",
}
MAX_BYTES=2_200_000

def normalized(text):
    s=re.sub(r"[^a-z0-9]+"," ",str(text).casefold()).strip()
    return " ".join(s.split())

def candidate_name(name):
    key=normalized(name)
    return normalized(ALIASES.get(key,key))

def allowed(url):
    p=urlsplit(url)
    return p.scheme=="https" and p.hostname==HOST and p.port in (None,443) and not p.username and not p.password

def depth_link(url):
    if not allowed(url):return False
    p=urlsplit(url)
    if p.path!="/ncaa-football-depth-charts/depth-chart.aspx":return False
    qs=parse_qs(p.query)
    return (len(qs.get("id",[]))==1 and qs["id"][0].isdigit()
            and len(qs.get("s",[]))==1
            and bool(re.fullmatch(r"[a-z0-9-]{2,65}",qs["s"][0])))

def download(url):
    if not allowed(url) or (url!=INDEX and not depth_link(url)):
        raise ValueError("Unreviewed depth-chart URL")
    req=urllib.request.Request(url,headers={
        "User-Agent":"CFB-2026-public-depth-order/0.1 (contact via project repo)",
        "Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=13) as r:
        if not allowed(r.geturl()):raise ValueError("Cross-origin redirect")
        raw=r.read(MAX_BYTES+1)
        ctype=r.headers.get("Content-Type","")
    if len(raw)>MAX_BYTES or (b"<html" not in raw[:1000].lower() and "text/html" not in ctype.lower()):
        raise ValueError("Invalid or oversized depth-chart page")
    return raw.decode("utf-8",errors="replace")

class IndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.school=None
        self.pages={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="img":
            alt=a.get("alt","").strip()
            if alt and len(alt)<85:self.school=alt
        if tag=="a":
            href=urljoin(INDEX,a.get("href",""))
            if self.school and depth_link(href):
                self.pages.setdefault(candidate_name(self.school),href)

class TableParser(HTMLParser):
    """Read table cells only, never copy or republish complete chart tables."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="tr":self.row=[]
        elif tag in ("td","th") and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.row is not None and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell=None
        elif tag=="tr" and self.row is not None:
            self.rows.append(self.row);self.row=None;self.cell=None

YEARS=re.compile(r"\s+(?:RS(?:\s+|[-/])|R[- ]?)?(?:FR|SO|JR|SR)\b|\s+(?:GR|TR|GS|5TH)\b",re.I)
NAME=re.compile(r"^[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ .'\u2019-]{1,80}$")
def clean_name(text):
    value=" ".join(text.strip().split())
    value=YEARS.split(value,maxsplit=1)[0].strip()
    # e.g., Taylor, Kamario -> Kamario Taylor
    if value.count(",")==1:
        a,b=(s.strip() for s in value.split(",",1))
        value=b+" "+a
    if not 4<=len(value)<=85 or not NAME.fullmatch(value):return None
    return value

def extract_chart(html):
    parser=TableParser();parser.feed(html)
    candidates=[]
    for cells in parser.rows:
        cells=[x.strip() for x in cells]
        if not cells or cells[0].upper()!="QB":continue
        # Chart rows must have explicit number/name column pairs.
        # Reject alternative table layouts rather than inventing ranks.
        names=[]
        for i in range(1,len(cells)-1,2):
            number=cells[i];name=clean_name(cells[i+1])
            if not re.fullmatch(r"#?\d{1,2}",number) or not name:break
            names.append(name)
            if len(names)==3:break
        if names and len(set(x.casefold() for x in names))==len(names):
            candidates.append(names)
    # Multiple inconsistent QB rows are NOT a stable depth chart.
    if not candidates or any(c!=candidates[0] for c in candidates[1:]):
        return []
    return candidates[0]

def source_updated(html,observed):
    """Website-provided chart-update timestamp, not an independent publication audit."""
    flat=re.sub(r"<[^>]*>"," ",html).replace("&nbsp;"," ")
    flat=" ".join(flat.split())
    match=re.search(r"\bUpdated:\s*(\d{1,2}/\d{1,2}/2026)\s+(\d{1,2}:\d{2})\s*([AP]M)\s*(?:ET|EST|EDT)\b",flat,re.I)
    if not match:return None
    try:
        updated=dt.datetime.strptime(" ".join(match.groups()),"%m/%d/%Y %I:%M %p").replace(tzinfo=ZoneInfo("America/New_York"))
    except ValueError:return None
    if updated>observed or (observed-updated).total_seconds()>35*86400:return None
    return {"source_updated_et":updated.isoformat(),"label":" ".join(match.groups())+" ET"}

def load_names(path):
    with Path(path).open(newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    by_name={}
    for r in rows:
        keys=[normalized(r["archived_team"]),normalized(r["espn_display_name"])]
        for key in keys:
            by_name[key]=r["espn_display_name"]
    return by_name

def chart_for_teams(board,alias_file,fetch=download,max_workers=7):
    if board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Untrusted board")
    names=load_names(alias_file)
    wanted={g[k] for g in board["games"] for k in ("home_team","away_team")}
    key_to_name={}
    for team in wanted:
        key=normalized(next((arch for arch,esp in []),team))
        # Reverse our season alias registry, preferring archived school names.
        rows=[k for k,v in names.items() if v==team]
        for k in rows:key_to_name[k]=team
    index=IndexParser();index.feed(fetch(INDEX))
    routes={}
    for key,url in index.pages.items():
        matched=key_to_name.get(key)
        if matched:
            if matched in routes and routes[matched]!=url:
                routes.pop(matched,None)
            else:routes[matched]=url
    # Do not try to scrape arbitrary unrecognized or duplicated school pages.
    captured=dt.datetime.now(dt.timezone.utc)
    records={};failures=[]
    def one(item):
        team,url=item
        data=fetch(url)
        return team,url,extract_chart(data),source_updated(data,captured)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures={pool.submit(one,item):item[0] for item in sorted(routes.items())}
        for fut in concurrent.futures.as_completed(futures):
            team=futures[fut]
            try:
                team,url,players,updated=fut.result()
                if players and updated:
                    records[team]={"source_url":url,"players":players,
                        "source_updated_et":updated["source_updated_et"],
                        "source_updated_label":updated["label"],
                        "observed_at_utc":captured.isoformat(),
                        "source_type":SOURCE}
                else:failures.append({"team":team,"issue":"NO_UNAMBIGUOUS_QB_ROW"})
            except (ValueError,OSError,TimeoutError) as exc:
                failures.append({"team":team,"issue":type(exc).__name__})
    return records,{"listed_schools":len(index.pages),"matched_schools":len(routes),
                    "charted_schools":len(records),"unmatched_schools":sorted(wanted-set(routes)),
                    "unmatched_index_keys":sorted(k for k in index.pages if k not in key_to_name)[:30],
                    "failures":sorted(failures,key=lambda r:r["team"])[:150]}

def overlay(board,charts,now,coverage=None):
    if board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Wrong research data clearance")
    metrics={"teams_charted":len(charts),"games_with_both_charts":0,
             "slots_ranked":0,"last_passer_matched_to_chart":0,
             "official_starters_promoted":0}
    for game in board["games"]:
        both=True
        for side in ("away","home"):
            team=game[side+"_team"];source=charts.get(team)
            ranks=[]
            if source:
                observed=parse_time(source["observed_at_utc"])
                if observed>now or observed>=parse_time(game["kickoff_utc"]):
                    source=None
                elif source.get("source_type")!=SOURCE or not allowed(source.get("source_url","")):
                    source=None
            if source:
                for n,player in enumerate(source["players"][:3],1):
                    if not clean_name(player):continue
                    ranks.append({"rank":n,"label":"QB"+str(n),"player":player,
                        "source_url":source["source_url"],
                        "source_type":SOURCE,"observed_at_utc":source["observed_at_utc"],
                        "source_updated_et":source.get("source_updated_et"),
                        "confirmed_starter":False})
            game["qb_depth_"+side]=ranks
            both &= bool(ranks)
            metrics["slots_ranked"]+=len(ranks)
            reported=game.get("qb_"+side) or {}
            if reported.get("status")=="RECENT_GAME_PASSER" and reported.get("player"):
                if any(normalized(r["player"])==normalized(reported["player"]) for r in ranks):
                    metrics["last_passer_matched_to_chart"]+=1
        metrics["games_with_both_charts"]+=int(both)
    board["qb_depth_display"]={
        **metrics,**(coverage or {}),"source":SOURCE,
        "provenance":"Third-party 2026 chart as observed at site build; not an official game-week starter declaration",
        "confirmed_starting_QB_from_chart":False,"changes_frozen_model_picks":False,
        "note":"QB1 is a chart rank, not proof of who will take the first snap; status can change with injuries, coach decisions, and game-week official notes."}
    return board

def run(board_file,aliases="data/archive/2026_team_aliases.csv",now=None,collector=chart_for_teams,cache=None):
    when=now or dt.datetime.now(dt.timezone.utc)
    path=Path(board_file);board=json.loads(path.read_text())
    charts=None;coverage=None;cached=False
    if cache and Path(cache).exists():
        try:
            existing=json.loads(Path(cache).read_text())
            observed=parse_time(existing["retrieved_at_utc"])
            if observed.date()==when.date() and observed<=when and existing["charts"]:
                charts=existing["charts"];coverage=existing["coverage"];cached=True
        except (KeyError,ValueError,TypeError):
            pass
    if charts is None:
        charts,coverage=collector(board,aliases)
        if cache and charts:
            dest=Path(cache);dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(json.dumps({"retrieved_at_utc":(when if now is not None else dt.datetime.now(dt.timezone.utc)).isoformat(),
                "charts":charts,"coverage":coverage})+"\n")
    if now is None:when=dt.datetime.now(dt.timezone.utc)
    board=overlay(board,charts,when,coverage)
    board["qb_depth_display"]["cache_reused"]=cached
    path.write_text(json.dumps(board,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(board["qb_depth_display"]))
    return board

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dashboard",required=True)
    p.add_argument("--cache",default=None)
    args=p.parse_args()
    run(args.dashboard,cache=args.cache)

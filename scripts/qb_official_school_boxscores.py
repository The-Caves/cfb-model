"""Reviewed OFFICIAL university football boxscores with explicit STARTERS lists.

These are postgame actual-starter observations, NOT estimates from passing
statistics, and never inputs to any earlier frozen prediction. A manually
reviewed specific game URL is necessary; the collector does not guess links,
game identity, scores, teams, or source ownership.
"""
import argparse,csv,datetime as dt,hashlib,json,re,urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from scripts.game_context import parse_time
from scripts.qb_passer_history import player_key
from scripts.qb_postgame_starter_labels import STATUS as LABEL_STATUS,LABEL,UNKNOWN

STATUS="REVIEWED_OFFICIAL_SCHOOL_BOXSCORE_QB_LABEL_CAPTURE_RESEARCH_ONLY"
SOURCE="REVIEWED_OFFICIAL_SCHOOL_BOXSCORE_HTML"
MAX_HTML_BYTES=2_500_000

class Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.excluded=0
        self.stack=[]
        self.parts=[]
    def handle_starttag(self,tag,attrs):
        self.stack.append(tag)
        if tag in ("script","style","noscript","svg"):self.excluded+=1
        if tag=="img" and not self.excluded:
            alt=dict(attrs).get("alt")
            if alt and 2<=len(alt)<120:
                self.parts.append(" ".join(alt.split()))
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript","svg") and self.excluded:self.excluded-=1
        if tag in self.stack:self.stack=self.stack[:len(self.stack)-1-self.stack[::-1].index(tag)]
    def handle_data(self,value):
        if self.excluded:return
        part=" ".join(value.split())
        if part:self.parts.append(part)

def _norm(s):
    return re.sub(r"\s+"," ",str(s).strip()).casefold()

def _heading(tokens,label):
    matched=[]
    name=_norm(label)
    for i,t in enumerate(tokens):
        low=_norm(t)
        if low==name+" offense":
            matched.append(i+1)
        elif low=="offense" and any(_norm(p)==name for p in tokens[max(0,i-2):i]):
            matched.append(i+1)
    if len(matched)!=1:raise ValueError("School starters team offensive heading absent or duplicated")
    return matched[0]

def _reorder(raw):
    name=" ".join(raw.split())
    if "," not in name:return name
    a,b=name.split(",",1)
    if not a.strip() or not b.strip():raise ValueError("Malformed official gamebook QB")
    return b.strip()+" "+a.strip()

def _qbs(tokens,start,end):
    section=tokens[start:end];qbs=[]
    for i,t in enumerate(section):
        if _norm(t)!="qb":continue
        candidate=None
        for back in (2,3,4):
            j=i-back
            if j>=0 and re.fullmatch(r"\d{1,2}",section[j]):
                candidate=" ".join(section[j+1:i])
                break
        if candidate is None or not re.search(r"[A-Za-z]",candidate):
            raise ValueError("Unparseable quarterback row in school starters table")
        name=_reorder(candidate)
        if not 2<=len(name)<=100:raise ValueError("Invalid official starter name")
        if player_key(name) not in {player_key(v) for v in qbs}:qbs.append(name)
    return qbs

def valid_source(entry):
    url=entry.get("source_url")
    try:
        u=urlsplit(url)
        if (u.scheme!="https" or not u.hostname or u.username or u.password
            or u.port not in (None,443) or u.fragment):
            raise ValueError("Unsafe official boxscore source")
    except (ValueError,TypeError) as exc:
        raise ValueError("Unsafe official boxscore source") from exc
    if (entry.get("reviewed_official_publisher") is not True or
        entry.get("publisher_hostname")!=u.hostname or
        not re.fullmatch(r"[a-z0-9.-]+",u.hostname) or
        u.hostname in ("localhost","127.0.0.1") or
        entry.get("season")!=2026 or
        not str(entry.get("game_id","")).isdigit()):
        raise ValueError("Unreviewed source URL or game")
    return url

def fetch(entry):
    url=valid_source(entry)
    req=urllib.request.Request(url,headers={"User-Agent":"CFB-Official-School-QB1-Research/0.1",
                                            "Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=16) as response:
        if (response.geturl()!=url or
            "text/html" not in response.headers.get("Content-Type","").lower()):
            raise ValueError("Off-publisher redirect or non-HTML boxscore")
        body=response.read(MAX_HTML_BYTES+1)
    if len(body)>MAX_HTML_BYTES:raise ValueError("Oversized school boxscore")
    return body.decode("utf-8","replace")

def parse(game,entry,html,observed_at):
    valid_source(entry)
    obs=parse_time(observed_at)
    if (str(game["game_id"])!=str(entry["game_id"])
        or any(str(game[k])!=str(entry[k]) for k in
               ("home","away","home_score","away_score","kickoff_utc"))
        or parse_time(game["kickoff_utc"])>=obs or
        entry.get("game_date_et")!=game["date"]):
        raise ValueError("Official school source does not match independently captured game")
    if not isinstance(html,str) or len(html)<100:raise ValueError("Empty official school boxscore")
    parser=Visible();parser.feed(html)
    tokens=parser.parts
    st=[i for i,t in enumerate(tokens) if _norm(t)=="starters"]
    if len(st)!=1:raise ValueError("No unambiguous official STARTERS section; visible_count="+str(len(st)))
    start=st[0];end=next((i for i in range(start+1,len(tokens))
                        if _norm(tokens[i])=="player participation"),len(tokens))
    section=tokens[start+1:end]
    aliases={k:entry[k+"_source_label"] for k in ("home","away")}
    if any(not isinstance(v,str) or len(v)<2 for v in aliases.values()):
        raise ValueError("Missing reviewed source team aliases")
    if _norm(aliases["home"])==_norm(aliases["away"]):
        raise ValueError("Duplicate official source names")
    before=tokens[:start]
    expected_date=dt.date.fromisoformat(game["date"]).strftime("%m/%d/%Y")
    alt_date=dt.date.fromisoformat(game["date"]).strftime("%-m/%-d/%Y")
    if not any(expected_date in s or alt_date in s for s in before):
        raise ValueError("School source does not show matching game date")
    # Exact final-score frame, not arbitrary game-wide numeric counts.
    head=" ".join(before)
    # School-published boxscores may place the publishing university
    # second even for an away fixture. The exact visible score order must
    # be independently reviewed per official source, never inferred.
    first=entry.get("scoreboard_first_side","away")
    if first not in ("home","away"):raise ValueError("Unreviewed school scoreboard score order")
    second="away" if first=="home" else "home"
    score_pattern=(r"\b"+re.escape(str(game[first+"_score"]))+
                   r"\b.{0,160}\bFinal\b.{0,160}\b"+
                   re.escape(str(game[second+"_score"]))+r"\b")
    if re.search(score_pattern,head,re.I|re.S) is None:
        raise ValueError("School final score frame does not match independent ESPN final")
    offsets={k:_heading(section,alias) for k,alias in aliases.items()}
    if offsets["home"]==offsets["away"]:raise ValueError("Overlapping offensive lineup")
    candidates={}
    for side,begin in offsets.items():
        finish=min([v for k,v in offsets.items() if v>begin]+
                   [i for i,x in enumerate(section) if i>begin and _norm(x)=="defense"]+
                   [len(section)])
        candidates[side]=_qbs(section,begin,finish)
    payload_sha=hashlib.sha256(html.encode("utf-8")).hexdigest()
    rows=[]
    for side in ("away","home"):
        qbs=candidates[side]
        status=LABEL if len(qbs)==1 else ("CONFLICT_MULTIPLE_EXPLICIT_QB_FLAGS" if len(qbs)>1 else UNKNOWN)
        rows.append({"game_id":str(game["game_id"]),"team":game[side],
            "opponent":game["home" if side=="away" else "away"],
            "home":game["home"],"away":game["away"],
            "kickoff_utc":game["kickoff_utc"],
            "label_status":status,"starter_player":qbs[0] if len(qbs)==1 else None,
            "explicit_qb_starter_flags":len(qbs),
            "candidate_qb_passers":[],
            "official_offense_qb_rows":qbs,
            "source_url":entry["source_url"],"source_payload_sha256":payload_sha,
            "source_class":SOURCE,"captured_at_utc":obs.isoformat(),
            "requires_manual_review":len(qbs)!=1,
            "not_from_passing_leader":True,
            "historical_publication_time_verified":False,
            "betting_status":"PASS_UNVALIDATED"})
    return rows

def collect(games,registry,asof,reader=fetch):
    at=parse_time(asof)
    if (registry.get("status")!="MANUALLY_REVIEWED_OFFICIAL_SCHOOL_POSTGAME_BOXSCORES"
        or registry.get("season")!=2026 or not isinstance(registry.get("entries"),list)):
        raise ValueError("Untrusted school boxscore manifest")
    index={str(g["game_id"]):g for g in games}
    if len(index)!=len(games):raise ValueError("Duplicate completed scoreboard games")
    seen=set();rows=[];errors=[];checked=0
    for entry in registry["entries"]:
        gid=str(entry["game_id"])
        if gid in seen:raise ValueError("Repeated reviewed school gamebook")
        seen.add(gid)
        valid_source(entry)
        game=index.get(gid)
        if game is None:continue
        checked+=1
        html=None
        try:
            html=reader(entry)
            rows.extend(parse(game,entry,html,asof))
        except (OSError,ValueError,TypeError,KeyError,TimeoutError) as exc:
            diagnostic={}
            if isinstance(html,str):
                scan=Visible();scan.feed(html)
                low=html.casefold();loc=low.find("starters")
                diagnostic={"html_characters":len(html),
                    "visible_tokens":len(scan.parts),
                    "visible_starters":sum(_norm(x)=="starters" for x in scan.parts),
                    "raw_starters_count":low.count("starters"),
                    "first_tokens":[x[:90] for x in scan.parts[:16]],
                    "raw_starters_context":html[max(0,loc-100):loc+150] if loc>=0 else None}
            errors.append({"game_id":gid,"source_url":entry["source_url"],
                           "reason":type(exc).__name__,"detail":str(exc)[:170],
                           "source_format_diagnostic":diagnostic})
    return {"status":LABEL_STATUS,"season":2026,"captured_at_utc":at.isoformat(),
        "source":SOURCE,"completed_games_checked":checked,
        "verified_game_identities":len(rows)//2,
        "missing_or_rejected_games":len(errors),
        "team_slots":len(rows),"explicit_starter_labels":sum(r["label_status"]==LABEL for r in rows),
        "unknown_or_conflict_starter_labels":sum(r["label_status"]!=LABEL for r in rows),
        "rows":rows,"errors":errors[:60],
        "postgame_labels_never_pregame_features":True,
        "historical_publication_times_verified":False,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

def run(games_file,registry_file,output):
    with open(games_file,newline="",encoding="utf-8-sig") as f:
        games=list(csv.DictReader(f))
    registry=json.loads(Path(registry_file).read_text(encoding="utf-8"))
    result=collect(games,registry,dt.datetime.now(dt.timezone.utc).isoformat())
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("rows","errors")}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for a in ("games","registry","output"):p.add_argument("--"+a,required=True)
    a=p.parse_args();run(a.games,a.registry,a.output)

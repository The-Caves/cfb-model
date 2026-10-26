"""Read-only monitor of reviewed official 2026 football preview pages.

Language hits require human review and do NOT confirm a starter or modify picks.
"""
import argparse,csv,datetime as dt,hashlib,json,re,urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

STATUS="OFFICIAL_GAMEWEEK_QB_LANGUAGE_REVIEW_ONLY"
START=re.compile(r"\b(?:will start|starting quarterback|named (?:the )?starter|start at quarterback|starting at quarterback|is starting|starting (?:this|the) (?:week|game))\b",re.I)
QB=re.compile(r"\b(?:quarterbacks?|QB|signal[- ]caller|passing|passer)\b",re.I)
INJURY=re.compile(r"\b(?:injur(?:y|ies|ed)|questionable|doubtful|game[- ]time decision|ruled out|available|return(?:s|ed|ing)? from|miss(?:ed|ing)? (?:the|two|three) games?)\b",re.I)
class Article(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.tags=[];self.skipped=0;self.all=[];self.main=[];self.article=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag)
        if tag in ("script","style","noscript","svg","nav","footer","header"):self.skipped+=1
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript","svg","nav","footer","header") and self.skipped:self.skipped-=1
        if tag in self.tags:self.tags=self.tags[:len(self.tags)-1-self.tags[::-1].index(tag)]
    def handle_data(self,value):
        if self.skipped or not value.strip():return
        self.all.append(value)
        if "main" in self.tags:self.main.append(value)
        if "article" in self.tags:self.article.append(value)

def text_from_html(markup):
    h=Article();h.feed(markup)
    return " ".join(" ".join(next((v for v in (h.article,h.main,h.all) if len(" ".join(v).split())>=35),h.all)).split())[:100000]

def safe(url):
    try:
        u=urlsplit(url)
        return u.scheme=="https" and bool(u.hostname) and u.port in (None,443) and not u.username and not u.password and not u.fragment
    except ValueError:return False

def fetch(url):
    if not safe(url):raise ValueError("Unapproved publisher")
    req=urllib.request.Request(url,headers={"User-Agent":"CFB-2026-Verified-Gameweek-Watch/0.1","Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=12) as resp:
        if not safe(resp.geturl()) or urlsplit(resp.geturl()).hostname!=urlsplit(url).hostname:
            raise ValueError("Off-publisher redirect")
        if "text/html" not in resp.headers.get("Content-Type","").lower():
            raise ValueError("Not a readable preview page")
        blob=resp.read(1600001)
    if len(blob)>1600000:raise ValueError("Oversized school release")
    return blob.decode("utf-8","replace")

def passages(text,pattern):
    out=[]
    for m in pattern.finditer(text):
        snippet=" ".join(text[max(0,m.start()-130):m.end()+130].split())
        if snippet not in out:out.append(snippet)
        if len(out)==5:break
    return out

def observe(config,now,reader=fetch,previous=None):
    if config.get("status")!="REVIEWED_OFFICIAL_GAMEWEEK_LINKS_NOT_QB_STARTERS" or config.get("season")!=2026 or not isinstance(config.get("entries"),list) or now.tzinfo is None:
        raise ValueError("Invalid reviewed gameweek source registry")
    old={(str(x["game_id"]),x["team"]):x for x in previous["entries"]} if isinstance(previous,dict) and previous.get("status")==STATUS else {}
    records=[];seen=set()
    for item in config["entries"]:
        if item.get("evidence_type")!="OFFICIAL_GAMEWEEK_PREVIEW_NO_QB1_CLAIM" or item.get("starter_confirmed") is not False:
            raise ValueError("Not a reviewed non-confirmation source")
        key=(str(item["game_id"]),item["team"])
        if key in seen:raise ValueError("Duplicated school/game")
        seen.add(key)
        kickoff=dt.datetime.fromisoformat(item["kickoff_utc"].replace("Z","+00:00"))
        date=dt.date.fromisoformat(item["published_date"])
        url=item["preview_url"]
        if date.year!=2026 or not safe(url):raise ValueError("Invalid reviewed article")
        if kickoff<=now:continue
        row={"game_id":key[0],"team":key[1],"opponent":item["opponent"],
            "kickoff_utc":item["kickoff_utc"],"source_url":url,
            "source_published_date_only":item["published_date"],"captured_at_utc":now.isoformat(),
            "status":"REVIEW_ONLY_NOT_CONFIRMED","confirmed_starter":False,
            "source_read_status":"NOT_FETCHED","source_change":"NOT_FETCHED",
            "language_flag":"NO_LANGUAGE_DETECTED","content_sha256":None,
            "starter_language_examples":[],"availability_language_examples":[]}
        try:
            markup=reader(url)
            text=text_from_html(markup)
            row["source_html_chars"]=len(markup)
            row["source_readable_text_chars"]=len(text)
            if len(text)<100:raise ValueError("Insufficient readable official article content")
            digest=hashlib.sha256(text.encode()).hexdigest()
            prior=old.get(key)
            row["content_sha256"]=digest
            row["source_change"]="FIRST_CAPTURE" if not prior or not prior.get("content_sha256") else "UNCHANGED" if prior["content_sha256"]==digest else "CHANGED_REVIEW_REQUIRED"
            row["starter_language_examples"]=passages(text,START)
            row["availability_language_examples"]=passages(text,INJURY)
            row["source_read_status"]="FETCHED_HTML"
            if row["starter_language_examples"]:row["language_flag"]="POSSIBLE_START_LANGUAGE_NEEDS_REVIEW"
            elif QB.search(text) and row["availability_language_examples"]:row["language_flag"]="QB_AVAILABILITY_CONTEXT_REVIEW"
            elif QB.search(text):row["language_flag"]="QB_CONTEXT_NOT_STARTER_CONFIRMATION"
        except (ValueError,OSError,UnicodeError) as exc:
            row["source_read_status"]="FETCH_FAILED";row["source_change"]="UNKNOWN_FETCH_FAILED";row["error_kind"]=type(exc).__name__;row["error_reason"]=str(exc)[:160]
        records.append(row)
    return {"status":STATUS,"season":2026,"captured_at_utc":now.isoformat(),
        "source_publication_times_attested":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED","confirmed_starters_added":0,
        "model_predictions_modified":False,
        "summary":{"future_source_pages":len(records),
                   "fetched":sum(x["source_read_status"]=="FETCHED_HTML" for x in records),
                   "fetch_failed":sum(x["source_read_status"]=="FETCH_FAILED" for x in records),
                   "changed":sum(x["source_change"]=="CHANGED_REVIEW_REQUIRED" for x in records),
                   "possible_start_language":sum(x["language_flag"]=="POSSIBLE_START_LANGUAGE_NEEDS_REVIEW" for x in records)},
        "monitor_health":("DEGRADED_ALL_ACTIVE_SOURCES_FAILED" if records and all(r["source_read_status"]=="FETCH_FAILED" for r in records) else "NO_ACTIVE_SOURCES" if not records else "PARTIAL_FAILURE" if any(r["source_read_status"]=="FETCH_FAILED" for r in records) else "OK"),
        "entries":records,
        "warning":"Source changes and keyword excerpts are review leads only. They never confirm QB1."}

def run(config_file,output,previous=None,csv_file=None):
    config=json.loads(Path(config_file).read_text())
    old=json.loads(Path(previous).read_text()) if previous and Path(previous).exists() else None
    result=observe(config,dt.datetime.now(dt.timezone.utc),previous=old)
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    if csv_file:
        fields=("game_id","team","opponent","kickoff_utc","source_url","source_change","source_read_status","language_flag","starter_language_examples","availability_language_examples")
        with Path(csv_file).open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
            for row in result["entries"]:
                writer.writerow({k:" | ".join(row.get(k,[])) if k.endswith("_examples") else row.get(k) for k in fields})
    print(json.dumps(result["summary"],sort_keys=True))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--config",required=True);p.add_argument("--output",required=True)
    p.add_argument("--previous");p.add_argument("--csv")
    a=p.parse_args();run(a.config,a.output,a.previous,a.csv)

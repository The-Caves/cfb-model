"""Official football media-center game-note link DISCOVERY only (not QB1 data).

Search only reviewed game-specific index sections. Never reuse an older game's
same-labelled "Game Notes" link or infer that an unpublished link exists.
"""
import argparse,datetime as dt,json,re,urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from scripts.qb_official_notes_watch import trusted_notes
from scripts.qb_gameweek_watch import safe

STATUS="OFFICIAL_FOOTBALL_MEDIA_INDEX_GAME_NOTE_LEADS_ONLY"
class _NotesIndex(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.chunks=[];self.link=None;self.ignored=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ("style","script","noscript","svg"):self.ignored+=1
        if tag=="a" and not self.ignored:self.link={"href":a.get("href",""),"parts":[]}
    def handle_data(self,s):
        if self.ignored or not s.strip():return
        if self.link is not None:self.link["parts"].append(s)
        else:self.chunks.append({"kind":"text","value":" ".join(s.split())})
    def handle_endtag(self,tag):
        if tag in ("style","script","noscript","svg") and self.ignored:self.ignored-=1
        if tag=="a" and self.link is not None:
            self.chunks.append({"kind":"anchor","value":" ".join(" ".join(self.link["parts"]).split()),"href":self.link["href"]})
            self.link=None

def retrieve(url):
    if not safe(url):raise ValueError("Unverified official index URL")
    req=urllib.request.Request(url,headers={"User-Agent":"CFB-2026-official-notes-index-audit/0.1","Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=12) as response:
        final=response.geturl();mime=response.headers.get("Content-Type","")
        data=response.read(2_000_001)
    if urlsplit(final).hostname!=urlsplit(url).hostname or len(data)>2_000_000 or "html" not in mime:
        raise ValueError("Unusable official media-center response")
    return data.decode("utf-8","replace")

def extract_links(html,config):
    parser=_NotesIndex();parser.feed(html)
    seq=parser.chunks
    marker=re.compile(r"\bgame\s*"+str(int(config["game_number"]))+r"\b",re.I)
    nextmarker=re.compile(r"\bgame\s*"+str(int(config["game_number"])+1)+r"\b",re.I)
    start=[i for i,item in enumerate(seq) if marker.search(item["value"])]
    if len(start)!=1:return [],"GAME_SECTION_MISSING_OR_AMBIGUOUS"
    i=start[0];stop=next((j for j in range(i+1,len(seq)) if nextmarker.search(seq[j]["value"])),min(i+90,len(seq)))
    block=seq[i:stop]
    text=" ".join(x["value"] for x in block).casefold()
    if (config["opponent_short"].casefold() not in text or
        config["target_game_date_label"].casefold() not in text):
        return [],"OPPONENT_OR_DATE_NOT_MATCHED"
    links=[]
    for item in block:
        if item["kind"]!="anchor" or not re.search(r"(?:game\s+notes|football\s+notes)",item["value"],re.I):continue
        if config["owner_label"].casefold() not in item["value"].casefold():continue
        href=urljoin(config["index_url"],item["href"])
        if not trusted_notes(href,config["preview_url"]):continue
        # The hub may publish a document landing page; same host + explicit
        # current game section are sufficient for review-only candidate.
        if href not in links:links.append(href)
        if len(links)>=4:break
    return links,"NOTES_LEAD_FOUND" if links else "GAME_SECTION_PRESENT_NOTES_NOT_PUBLISHED"

def observe(config,now,reader=retrieve):
    if config.get("status")!="REVIEWED_OFFICIAL_FOOTBALL_MEDIA_INDEX_PILOT_2026" or config.get("season")!=2026 or not isinstance(config.get("entries"),list):
        raise ValueError("Unreviewed media-center pilot")
    rows=[];keys=set()
    for item in config["entries"]:
        key=(str(item["game_id"]),item["team"])
        if key in keys:raise ValueError("Repeated media index")
        keys.add(key)
        kickoff=dt.datetime.fromisoformat(item["kickoff_utc"].replace("Z","+00:00"))
        if kickoff<=now:continue
        url=item["index_url"]
        if not safe(url) or urlsplit(url).hostname!=urlsplit(item["preview_url"]).hostname:
            raise ValueError("Not an official same-school index")
        row={"game_id":key[0],"team":key[1],"opponent":item["opponent"],
             "kickoff_utc":item["kickoff_utc"],"source_url":url,"captured_at_utc":now.isoformat(),
             "status":"REVIEW_ONLY_NOT_CONFIRMED","confirmed_starter":False,
             "source_read_status":"NOT_FETCHED","links":[],"link_match_status":"UNKNOWN"}
        try:
            html=reader(url)
            links,status=extract_links(html,item)
            row.update({"source_read_status":"READ_HTML","links":links,"link_match_status":status})
        except (ValueError,OSError) as exc:
            row["source_read_status"]="FETCH_FAILED"
            row["error_kind"]=type(exc).__name__
        rows.append(row)
    return {"status":STATUS,"season":2026,"captured_at_utc":now.isoformat(),
            "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
            "starter_confirmations_added":0,"predictions_changed":False,
            "summary":{"indexes_checked":len(rows),
                       "indexes_fetched":sum(r["source_read_status"]=="READ_HTML" for r in rows),
                       "game_note_candidate_links":sum(len(r["links"]) for r in rows),
                       "confirmed_gameweek_note_links":0},
            "entries":rows,
            "warning":"Media-center link detection is a review candidate only; the source has not been opened, provenance-verified or used as QB1 starter evidence."}

def run(config_path,output):
    conf=json.loads(Path(config_path).read_text())
    out=observe(conf,dt.datetime.now(dt.timezone.utc))
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,indent=2,allow_nan=False)+"\n")
    print(json.dumps(out["summary"],sort_keys=True))
    return out
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.config,a.output)

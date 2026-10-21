"""Read-only pilot: discover QB-related official athletics news for human review.

RSS titles/summaries are NOT game-specific starter confirmations. Records from
this watcher MUST NEVER be promoted directly into QB_STARTER evidence.
"""
import argparse,datetime as dt,html,json,re,urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
from scripts.game_context import parse_time

FEEDS={
    "NC State Wolfpack":"https://gopack.com/rss?path=football",
    "Iowa State Cyclones":"https://cyclones.com/rss?path=football",
    "James Madison Dukes":"https://jmusports.com/rss?path=football",
    "Navy Midshipmen":"https://navysports.com/rss.aspx?path=football",
    "Florida International Panthers":"https://fiusports.com/rss.aspx?path=football",
    # Both additional feeds are documented by the university on its own
    # public RSS Story Feeds directory; do not substitute fan/news sites.
    "Texas Longhorns":"https://texaslonghorns.com/rss?path=football",
    "North Carolina Tar Heels":"https://goheels.com/rss?path=football"
}
QB_TOPIC=re.compile(r"\b(quarterback|quarterbacks|qb|qbs|signal.caller)\b",re.I)
# The word "named" alone is noisy: award lists routinely say a QB was named
# an honoree. Specific starting language or personnel-news terms are required.
START_TOPIC=re.compile(r"\b(start|starts|starter|starting|depth chart|availability|"
                       r"injury|injuries|injured|questionable|doubtful|out)\b",re.I)
TAG=re.compile(r"<[^>]{0,500}>")

def clean(value,max_chars=500):
    return " ".join(html.unescape(TAG.sub(" ",value or "")).split())[:max_chars]

def article_candidates(xml_bytes,team,games,captured):
    """Extract a bounded, candidate-only review queue from an RSS2 XML feed."""
    root=ET.fromstring(xml_bytes)
    entries=root.findall("./channel/item")
    if root.tag!="rss" or not root.find("channel") is not None:
        raise ValueError("Unsupported or missing RSS channel")
    now=parse_time(captured)
    associated=[g for g in games if team in (g["home"],g["away"])
                and parse_time(g["kickoff_utc"])>now]
    out=[]
    for entry in entries[:75]:
        title=clean(entry.findtext("title"),200)
        summary=clean(entry.findtext("description"),450)
        candidate_text=title+" "+summary
        if not (QB_TOPIC.search(candidate_text) and START_TOPIC.search(candidate_text)):
            continue
        link=(entry.findtext("link") or "").strip()
        u=urlsplit(link)
        source_host=urlsplit(FEEDS[team]).hostname
        if not (u.scheme=="https" and u.hostname==source_host and not u.username and not u.password):
            continue
        date_string=(entry.findtext("pubDate") or "").strip()
        published=None
        if date_string:
            try:
                d=parsedate_to_datetime(date_string)
                if d.tzinfo is not None:
                    published=d.astimezone(dt.timezone.utc)
            except (ValueError,TypeError,IndexError):
                pass
        if published and (published>now or (now-published).total_seconds()>14*86400):
            continue
        # Candidate identity is scoped to team. With multiple future games,
        # do not pretend that an article necessarily refers to one of them.
        out.append({"team":team,"title":title,"summary":summary,
                    "source_url":link,"published_at_utc":published.isoformat() if published else None,
                    "captured_at_utc":now.isoformat(),"potential_game_ids":[str(g["game_id"]) for g in associated],
                    "status":"UNREVIEWED_NEWS_CANDIDATE",
                    "disclaimer":"Topic match only; not evidence of a confirmed starter"})
    return out

def fetch_rss(url,timeout=9,max_bytes=2_000_000):
    req=urllib.request.Request(url,headers={"User-Agent":"CFB-2026-Official-QB-Candidate-Research/0.1",
                                          "Accept":"application/rss+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        final=urlsplit(response.geturl())
        expected=urlsplit(url)
        if final.scheme!="https" or final.hostname!=expected.hostname:
            raise ValueError("Official publisher host redirected outside its domain")
        result=response.read(max_bytes+1)
    if len(result)>max_bytes:raise ValueError("RSS feed exceeds byte limit")
    return result

def run(context_file,output_file,reader=fetch_rss,now=None):
    data=json.loads(Path(context_file).read_text(encoding="utf-8"))
    games=data.get("games")
    if not isinstance(games,list):raise ValueError("Missing context games")
    captured=parse_time(now or dt.datetime.now(dt.timezone.utc).isoformat()).isoformat()
    qa={"status":"OFFICIAL_NEWS_REVIEW_ONLY","asof_utc":captured,
        "feeds_configured":len(FEEDS),"feeds_read":0,"feeds_skipped_no_upcoming_game":0,
        "feeds_failed":0,"errors":[],"candidate_count":0,"feed_status":{},
        "confirmed_qb_starter_count":0}
    out=[]
    for team,url in FEEDS.items():
        if not any(team in (g.get("home"),g.get("away")) and
                   parse_time(g["kickoff_utc"])>parse_time(captured) for g in games):
            qa["feeds_skipped_no_upcoming_game"]+=1
            qa["feed_status"][team]="NOT_SCHEDULED"
            continue
        try:
            payload=reader(url)
            records=article_candidates(payload,team,games,captured)
            out.extend(records);qa["feeds_read"]+=1
            qa["feed_status"][team]="FETCHED"
        except (OSError,ValueError,ET.ParseError,KeyError) as exc:
            qa["feeds_failed"]+=1
            qa["feed_status"][team]="FETCH_FAILED"
            qa["errors"].append({"team":team,"reason":type(exc).__name__,"detail":str(exc)[:120]})
    qa["candidate_count"]=len(out)
    result={"manifest":qa,"candidates":out,
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    output_file=Path(output_file);output_file.parent.mkdir(parents=True,exist_ok=True)
    output_file.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(qa,indent=2))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--context",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.context,a.output)

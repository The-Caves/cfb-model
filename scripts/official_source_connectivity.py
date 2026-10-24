"""Probe configured official RSS endpoints; HTTP success is not personnel verification."""
import argparse,datetime as dt,json,urllib.error,urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from pathlib import Path
from scripts.qb_official_news_watch import load_feed_registry

def probe(feeds,fetch=None):
    if fetch is None:
        def fetch(url):
            req=urllib.request.Request(url,headers={"User-Agent":"cfb-model-research/0.2","Accept":"application/rss+xml, application/xml, text/xml"})
            with urllib.request.urlopen(req,timeout=12) as response:
                return response.status,response.headers.get("Content-Type",""),response.read(512)
    def check(item):
        team,url=item
        try:
            status,content_type,sample=fetch(url)
            reachable=200<=status<300
            looks_xml=b"<rss" in sample.lower() or b"<?xml" in sample.lower() or b"<feed" in sample.lower()
            return {"team":team,"url":url,"http_status":status,
                         "reachable":reachable,"looks_like_feed":bool(reachable and looks_xml),
                         "personnel_evidence_verified":False}
        except Exception as exc:
            return {"team":team,"url":url,"reachable":False,"looks_like_feed":False,
                         "error_type":type(exc).__name__,"personnel_evidence_verified":False}
    with ThreadPoolExecutor(max_workers=12) as executor:
        rows=list(executor.map(check,sorted(feeds.items())))
    return {"status":"CONNECTIVITY_ONLY_NOT_PERSONNEL_VERIFICATION",
            "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "checked":len(rows),"reachable":sum(r["reachable"] for r in rows),
            "feed_like":sum(r["looks_like_feed"] for r in rows),"sources":rows}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True);p.add_argument("--output",required=True)
    p.add_argument("--athletics")
    a=p.parse_args()
    result=probe(load_feed_registry(a.registry))
    if a.athletics:
        directory=json.loads(Path(a.athletics).read_text(encoding="utf-8"))
        sites={item["team"]:item["athletics_homepage"] for item in directory["schools"]}
        if len(sites)!=directory["expected_teams"]:
            raise ValueError("Incomplete athletics site registry")
        homepage_result=probe(sites)
        result["athletics_homepages"]=homepage_result["sources"]
        result["athletics_homepage_checked"]=homepage_result["checked"]
        result["athletics_homepage_reachable"]=homepage_result["reachable"]
        result["athletics_homepage_feed_like"]=homepage_result["feed_like"]
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="sources"}))

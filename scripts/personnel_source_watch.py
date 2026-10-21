"""Monitor official availability publication pages without fabricating player statuses.

A changed page hash is a candidate *report publication* requiring structured
extraction or review. HTML includes changing site chrome; no healthy/injured
claim is produced from page content alone.
"""
import argparse,datetime as dt,hashlib,json,urllib.request
from pathlib import Path

SOURCES={
"SEC_FOOTBALL_OFFICIAL":"https://www.secsports.com/fbreports",
"BIG_TEN_FOOTBALL_OFFICIAL":"https://bigten.org/sports/2026/9/10/FB_Availability_Reports.aspx",
}
def fetch(source,url,timeout=9):
    req=urllib.request.Request(url,headers={"User-Agent":"CFB-2026-research-availability-watcher/0.1"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        raw=response.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError("Source page exceeds size limit")
        return {"url":url,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
                "content_type":response.headers.get("Content-Type","unknown")}
def monitor(previous=None,fetcher=fetch,now=None):
    issue=now or dt.datetime.now(dt.timezone.utc).isoformat()
    old=(previous or {}).get("sources",{})
    result={"captured_at_utc":issue,"parse_status":"NO_VERIFIED_PLAYER_EXTRACTION",
            "source_reports_are_player_statuses":False,
            "sources":{},"sources_status":{},"candidate_source_changes":[]}
    for label,url in SOURCES.items():
        try:
            record=fetcher(label,url)
            old_hash=(old.get(label) or {}).get("sha256")
            status="FIRST_SNAPSHOT" if old_hash is None else "CHANGED_UNREVIEWED" if old_hash!=record["sha256"] else "UNCHANGED"
            result["sources"][label]={**record,"captured_at_utc":issue}
            if status=="CHANGED_UNREVIEWED":
                result["candidate_source_changes"].append({"source":label,"url":url,
                    "event":"OFFICIAL_SOURCE_PAGE_CHANGED_NEEDS_REPORT_REVIEW"})
        except Exception as exc:
            status="SOURCE_UNAVAILABLE"
            result["sources"][label]={"url":url,"error":str(exc)[:200],
                "last_known_hash":(old.get(label) or {}).get("sha256")}
        result["sources_status"][label]=status
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--previous",default="data/context_state/previous_sources.json")
    p.add_argument("--output",default="data/context_refresh/personnel_source_watch.json")
    a=p.parse_args()
    prev=json.loads(Path(a.previous).read_text()) if Path(a.previous).exists() else None
    result=monitor(prev)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"captured_at_utc":result["captured_at_utc"],
                      "statuses":result["sources_status"],
                      "unreviewed_changes":len(result["candidate_source_changes"])},indent=2))

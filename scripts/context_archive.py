"""Persist pregame context with an immutable GitHub branch, run deltas and freezes.

All writes target context-state only. History uses compressed JSON, leaving the
main code branch untouched. Workflow token requires contents:write. Never log token.
"""
import argparse,base64,datetime as dt,gzip,hashlib,json,os,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from scripts.context_delta import snapshot_changes
from scripts.qb_review_archive import close_qb_review
from scripts.game_context import parse_time

API="https://api.github.com"
BRANCH="context-state"
def api(method,path,payload=None):
    token=os.environ.get("GITHUB_TOKEN")
    if not token:raise ValueError("Missing GitHub Actions token")
    url=API+path
    request=urllib.request.Request(url,method=method,
        headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
                 "X-GitHub-Api-Version":"2022-11-28","User-Agent":"cfb-context-archive/0.1",
                 "Content-Type":"application/json"},
        data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.urlopen(request,timeout=20) as resp:return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code==404:return None
        raise RuntimeError(f"GitHub {method} {path} failed with HTTP {exc.code}") from exc
def repo_path():
    repo=os.environ.get("GITHUB_REPOSITORY","")
    if repo.count("/")!=1:raise ValueError("GITHUB_REPOSITORY not set")
    return "/repos/"+repo
def branch_head():
    data=api("GET",repo_path()+"/git/ref/heads/"+BRANCH)
    return data["object"]["sha"] if data else None
def get_blob_file(file,branch=BRANCH):
    path=repo_path()+"/contents/"+urllib.parse.quote(file,safe="/")+"?ref="+branch
    data=api("GET",path)
    if data is None:return None
    if data.get("encoding")!="base64":raise ValueError("Unexpected content encoding")
    return base64.b64decode(data["content"])
def encode(data):return json.dumps(data,sort_keys=True,separators=(",",":"),default=str).encode()
def pack(data):return gzip.compress(encode(data),mtime=0)
def unpack(data):return json.loads(gzip.decompress(data))
def restore(folder):
    out=Path(folder);out.mkdir(parents=True,exist_ok=True)
    prior=None;geo={};previous_sources=None
    if branch_head():
        b=get_blob_file("state/latest.json.gz")
        if b:prior=unpack(b)
        a=get_blob_file("state/geocache.json")
        if a:geo=json.loads(a)
        sources=get_blob_file("state/personnel_sources_latest.json")
        if sources:previous_sources=json.loads(sources)
    (out/"previous_sources.json").write_text(json.dumps(previous_sources,indent=2)+"\n")
    (out/"previous.json").write_text(json.dumps(prior,indent=2)+"\n")
    (out/"geocache.json").write_text(json.dumps(geo,indent=2)+"\n")
    return {"prior_available":prior is not None,"cached_cities":len(geo),
            "prior_personnel_source_watch":previous_sources is not None}
def asof_id(current):
    t=parse_time(current["asof_utc"])
    return t.strftime("%Y%m%dT%H%M%SZ")
def close_snapshot(current,observed_at):
    """Ensure persisted as-of is AFTER every source collection, yet BEFORE kickoff."""
    end=parse_time(observed_at)
    start=parse_time(current["asof_utc"])
    if end<start:raise ValueError("Collection ended before it started")
    newer=dict(current)
    newer["collection_started_utc"]=current["asof_utc"]
    newer["asof_utc"]=end.isoformat()
    games=current.get("games")
    if not isinstance(games,list):raise ValueError("No game list")
    newer["games"]=[g for g in games if parse_time(g["kickoff_utc"])>end]
    newer["excluded_game_kickoffs_during_collection"]=len(games)-len(newer["games"])
    return newer

def write(current_path,previous_path,geo_path,manifest_path,output_path,source_watch=None,qb_review=None):
    cur=json.loads(Path(current_path).read_text())
    prior=json.loads(Path(previous_path).read_text())
    manifest=json.loads(Path(manifest_path).read_text())
    if manifest["status"] in ("CONTEXT_PIPELINE_FAILED","SOURCE_FETCH_FAILURE"):
        raise ValueError("Refusing to persist failed source collection")
    if manifest.get("schedule_fetch",{}).get("errors"):
        raise ValueError("Refusing to replace snapshot after partial schedule fetch")
    if not isinstance(cur.get("games"),list) or not cur.get("asof_utc"):
        raise ValueError("Invalid current snapshot")
    issued=parse_time(cur["asof_utc"])
    if abs((dt.datetime.now(dt.timezone.utc)-issued).total_seconds())>1200:
        raise ValueError("Snapshot issue time not recent; refused")
    cur=close_snapshot(cur,dt.datetime.now(dt.timezone.utc).isoformat())
    issued=parse_time(cur["asof_utc"])
    if prior and parse_time(prior["asof_utc"])>=issued:
        raise ValueError("Stale or duplicate snapshot; refused")
    changes,freezes,qa=snapshot_changes(prior,cur,cur["asof_utc"])
    summary={"asof_utc":cur["asof_utc"],"run_id":os.environ.get("GITHUB_RUN_ID"),
             "status":manifest["status"],"games_collected":len(cur["games"]),
             "delta":qa,"safe_for_betting":False,"latest_context_ref":"state/latest.json.gz"}
    official=manifest.get("official_availability")
    if isinstance(official,dict):
        summary["verified_official_availability"]={
            "reports":official.get("official_game_reports",0),
            "designations":official.get("player_designations",0),
            "source_errors":official.get("errors",0),
            "conferences":{key:{
                "publisher_snapshot_sha256":value.get("sha256"),
                "fetched_at_utc":value.get("fetched_at_utc"),
                "reports_published_accepted":value.get("official_reports_accepted",0),
                "reports_pending":value.get("pending_cards",0)}
                for key,value in official.get("feeds",{}).items()}}
    qb_queue=None
    if qb_review:
        candidate_path=Path(qb_review)
        if not candidate_path.is_file():
            raise ValueError("Missing required QB review queue artifact")
        qb_queue=close_qb_review(json.loads(candidate_path.read_text()),cur)
        summary["qb_review"]=qb_queue["summary"]
    source=None
    if source_watch and Path(source_watch).exists():
        source=json.loads(Path(source_watch).read_text())
        summary["personnel_source_watch"]=source.get("sources_status",{})
        candidate=source.get("candidate_source_changes") or []
        qa["unreviewed_official_index_changes"]=len(candidate)
        summary["unreviewed_official_index_changes"]=len(candidate)
        for item in candidate:
            changes.append({"game_id":None,"field":"official_source_index",
                "source":item.get("source"),"source_url":item.get("url"),
                "kind":"OFFICIAL_SOURCE_INDEX_CHANGED_UNREVIEWED",
                "before":None,"after":"SOURCE_PAGE_CONTENT_CHANGED",
                "current_asof_utc":cur["asof_utc"],
                "note":"Page hash change does not establish a player injury or QB status."})
    report={"summary":summary,"changes":changes,"frozen_games":[
        {"game_id":f["game_id"],"last_known_pregame_asof_utc":f["final_pregame_snapshot_asof_utc"]}
        for f in freezes]}
    output=Path(output_path);output.mkdir(parents=True,exist_ok=True)
    (output/"delta.json").write_text(json.dumps(report,indent=2)+"\n")
    (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    sha=branch_head()
    if sha is None:
        base=os.environ.get("GITHUB_SHA")
        if not base:raise ValueError("GITHUB_SHA missing for branch bootstrap")
        api("POST",repo_path()+"/git/refs",{"ref":"refs/heads/"+BRANCH,"sha":base})
        sha=branch_head()
    commit=api("GET",repo_path()+"/git/commits/"+sha)
    if not commit:raise ValueError("Could not load branch head commit")
    stamp=asof_id(cur)
    day=issued.strftime("%Y/%m/%d")
    blobs={
        "state/latest.json.gz":pack(cur),
        "state/geocache.json":Path(geo_path).read_bytes() if Path(geo_path).exists() else b"{}",
        "state/summary.json":encode(summary),
        "history/"+day+"/"+stamp+".json.gz":pack(cur),
        "deltas/"+day+"/"+stamp+".json.gz":pack(report),
    }
    if qb_queue is not None:
        blobs["state/qb_review_latest.json"]=encode(qb_queue)
        blobs["qb_review/"+day+"/"+stamp+".json.gz"]=pack(qb_queue)
    if source is not None:
        blobs["state/personnel_sources_latest.json"]=encode(source)
        blobs["sources/"+day+"/"+stamp+".json.gz"]=pack(source)
    for f in freezes:
        # A pregame snapshot is never retrospectively revised.
        fname="frozen/"+str(f["game_id"])+".json.gz"
        if get_blob_file(fname) is None:
            blobs[fname]=pack(f)
    tree_entries=[]
    for file,bytes_ in blobs.items():
        o=api("POST",repo_path()+"/git/blobs",{"content":base64.b64encode(bytes_).decode(),
            "encoding":"base64"})
        tree_entries.append({"path":file,"mode":"100644","type":"blob","sha":o["sha"]})
    tree=api("POST",repo_path()+"/git/trees",{"base_tree":commit["tree"]["sha"],"tree":tree_entries})
    new=api("POST",repo_path()+"/git/commits",{
        "message":"Capture timestamped 2026 context "+stamp+"; "+str(len(changes))+" deltas",
        "tree":tree["sha"],"parents":[sha]})
    api("PATCH",repo_path()+"/git/refs/heads/"+BRANCH,{"sha":new["sha"],"force":False})
    (output/"github_commit.json").write_text(json.dumps({
        "branch":BRANCH,"sha":new["sha"],"paths":list(blobs)},indent=2)+"\n")
    return {"state_commit_sha":new["sha"],**summary}
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("operation",choices=("restore","save"))
    p.add_argument("--state-dir",default="data/context_state")
    p.add_argument("--context",default="data/context_refresh/upcoming_game_context_2026.json")
    p.add_argument("--manifest",default="data/context_refresh/context_manifest.json")
    p.add_argument("--output",default="data/context_delta")
    p.add_argument("--geo-cache",default="data/context_refresh/geo_cache.json")
    p.add_argument("--source-watch",default="data/context_refresh/personnel_source_watch.json")
    p.add_argument("--qb-review",default=None)
    a=p.parse_args()
    result=restore(a.state_dir) if a.operation=="restore" else write(
        a.context,Path(a.state_dir)/"previous.json",a.geo_cache,a.manifest,a.output,
        a.source_watch,a.qb_review)
    print(json.dumps(result,indent=2))

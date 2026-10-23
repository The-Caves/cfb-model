"""Persist free ESPN market observations as immutable, checksummed Git blobs.

No paid quotes, no overwrite, no inferred opening/closing prices.
"""
import argparse,datetime as dt,gzip,hashlib,json,os
from pathlib import Path
from scripts import context_archive as store
from scripts.game_context import parse_time

def persist(folder):
    paths=sorted(Path(folder).glob("*.json"))
    if not paths:raise ValueError("No market snapshots to persist")
    head=store.branch_head()
    if not head:raise ValueError("context-state branch missing")
    commit=store.api("GET",store.repo_path()+"/git/commits/"+head)
    entries=[];written=[];existing=[]
    for file in paths:
        raw=file.read_bytes()
        snapshot=json.loads(raw)
        if snapshot.get("source")!="ESPN_SCOREBOARD_FREE" or snapshot.get("paid_api_calls")!=0:
            raise ValueError("Unexpected market snapshot source")
        observed=parse_time(snapshot["observed_at_utc"])
        if abs((dt.datetime.now(dt.timezone.utc)-observed).total_seconds())>3600:
            raise ValueError("Stale market capture cannot be archived as current")
        digest=hashlib.sha256(raw).hexdigest()
        run=os.environ.get("GITHUB_RUN_ID","manual")
        dest="research_2026/free_market/"+observed.strftime("%Y/%m/%d")+"/"+run+"-"+digest[:16]+".json.gz"
        payload=gzip.compress(raw,mtime=0)
        old=store.get_blob_file(dest)
        if old is not None:
            if old!=payload:raise ValueError("Immutable market snapshot mismatch")
            existing.append(dest);continue
        blob=store.api("POST",store.repo_path()+"/git/blobs",{
            "content":__import__("base64").b64encode(payload).decode(),"encoding":"base64"})
        entries.append({"path":dest,"mode":"100644","type":"blob","sha":blob["sha"]})
        written.append({"path":dest,"sha256":digest,"quotes":len(snapshot["quotes"])})
    if entries:
        tree=store.api("POST",store.repo_path()+"/git/trees",{
            "base_tree":commit["tree"]["sha"],"tree":entries})
        new=store.api("POST",store.repo_path()+"/git/commits",{
            "message":"Archive observed free market research snapshots",
            "tree":tree["sha"],"parents":[head]})
        store.api("PATCH",store.repo_path()+"/git/refs/heads/"+store.BRANCH,{
            "sha":new["sha"],"force":False})
        for item in written:
            saved=store.get_blob_file(item["path"])
            if saved is None or gzip.decompress(saved)!=next(
                p.read_bytes() for p in paths if hashlib.sha256(p.read_bytes()).hexdigest()==item["sha256"]):
                raise ValueError("Market snapshot archive readback mismatch")
    return {"written":written,"existing":existing}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--market-dir",required=True)
    a=p.parse_args();print(json.dumps(persist(a.market_dir)))

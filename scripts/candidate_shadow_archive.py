"""Append-only GitHub archive for newly frozen QB and venue research shadows.

The two candidates are NOT published website picks. Archive observations
before kickoff, and never overwrite an earlier forecast when sources change.
"""
import argparse,datetime as dt,json,os
from pathlib import Path
from scripts import context_archive as store
from scripts.personnel_results_archive import ROOT,_commit_material
from scripts.personnel_forecast import checksum
from scripts.game_context import parse_time
from scripts.qb_conditional_forecast import STATUS as QB
from scripts.venue_travel_forecast import STATUS as VENUE

VERSIONS={"qb":QB,"venue":VENUE}
def validate(data,kind):
    if kind not in VERSIONS or data.get("status")!=VERSIONS[kind]:
        raise ValueError("Wrong prospective candidate type")
    if (data.get("season")!=2026 or data.get("model_promoted") is not False
        or data.get("safe_for_betting") is not False
        or data.get("betting_status")!="PASS_UNVALIDATED"
        or data.get("historical_publication_authenticated",False) is not False
            and kind=="venue"):
        raise ValueError("Untrusted candidate source clearance")
    if kind=="qb" and data.get("historical_pbp_publication_authenticated") is not False:
        raise ValueError("Pretend QB original publication was verified")
    observed=parse_time(data["observed_at_utc"])
    run=str(data["baseline_forecast_run_id" if kind=="qb" else "baseline_run_id"])
    if not run.isdigit() or len(str(data.get("baseline_forecast_sha256","")))!=64:
        raise ValueError("No bound immutable V03 forecast")
    rows=data.get("games")
    if not rows or len({str(r["game_id"]) for r in rows})!=len(rows):
        raise ValueError("Missing or duplicate game slots")
    for r in rows:
        if (parse_time(r["kickoff_utc"])<=observed
            or len(str(r.get("baseline_row_sha256","")))!=64
            or r["home"]==r["away"]):
            raise ValueError("Postkickoff or unbound candidate matchup")
        if kind=="qb":
            c=r["candidate"]
            if c.get("model_promoted") is not False or c.get("betting_status")!="PASS_UNVALIDATED":
                raise ValueError("Illegal QB model promotion")
        else:
            pts=r.get("small_travel_adjustment_points")
            if pts is not None and abs(float(pts))>1.25+1e-6:
                raise ValueError("Excessive travel effect")
    return run,observed

def archive(data,kind):
    run,observed=validate(data,kind)
    if run!=str(os.environ.get("GITHUB_RUN_ID","")):
        raise ValueError("Archive must belong to current GitHub run")
    elapsed=(dt.datetime.now(dt.timezone.utc)-observed).total_seconds()
    if not 0<=elapsed<1200:raise ValueError("Cannot archive old research as pregame")
    root=ROOT+"/candidate_shadow_"+kind
    day=observed.strftime("%Y/%m/%d")
    filename=root+"/"+day+"/run-"+run+".json.gz"
    index_path=root+"/index.json"
    packed=store.pack(data)
    old=store.get_blob_file(filename)
    if old is not None:
        if old!=packed:raise ValueError("Cannot rewrite a frozen candidate")
        return {"status":"EXACT_ARCHIVE_ALREADY_PRESENT","path":filename}
    oldidx=store.get_blob_file(index_path)
    idx=json.loads(oldidx) if oldidx else {"status":VERSIONS[kind],"season":2026,
                                           "runs":[],"betting_status":"PASS_UNVALIDATED"}
    if idx.get("status")!=VERSIONS[kind] or idx.get("season")!=2026:
        raise ValueError("Corrupt candidate index")
    if any(x["run_id"]==run for x in idx["runs"]):
        raise ValueError("Conflicting immutable candidate run")
    idx["runs"].append({"run_id":run,"path":filename,
        "captured_at_utc":observed.isoformat(),"sha256":checksum(data),
        "games":len(data["games"])})
    idx["runs"].sort(key=lambda r:r["captured_at_utc"])
    commit=_commit_material({filename:packed,index_path:store.encode(idx)},run)
    return {"status":"ARCHIVED_PROSPECTIVE_CANDIDATE","path":filename,
            "sha256":checksum(data),"commit_sha":commit}

def run(path,kind):
    data=json.loads(Path(path).read_text())
    report=archive(data,kind)
    print(json.dumps({"kind":kind,"archive":report,
                      "betting_status":"PASS_UNVALIDATED"}))
    return report
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--kind",choices=VERSIONS,required=True)
    a=p.parse_args();run(a.input,a.kind)

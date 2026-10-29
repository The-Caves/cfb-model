"""Archive 2026 team matchup profile board for source-labelled website overlay.

Game-level style profiles are descriptive/retrospective PBP, not validated
scores or changes to the frozen baseline prediction.
"""
import argparse,datetime as dt,json,os
from pathlib import Path
from scripts import context_archive as store
from scripts.personnel_results_archive import ROOT,_commit_material
from scripts.weekly_profiles import canonical,digest
from scripts.game_context import parse_time
from scripts.team_matchup_intelligence import STATUS

INDEX=ROOT+"/matchup_profiles/index.json"
def validate(board,observed):
    if (board.get("status")!=STATUS or board.get("season")!=2026
        or board.get("historical_publication_authenticated") is not False
        or board.get("model_promoted") is not False
        or board.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Untrusted matchup board")
    when=parse_time(observed)
    if when.date()<dt.date.fromisoformat(board["cutoff_date_exclusive"]):
        raise ValueError("Profile source from later football day")
    ids=set()
    for row in board["games"]:
        gid=str(row["game_id"])
        if gid in ids or row["home"]==row["away"]:
            raise ValueError("Duplicate or invalid fixture")
        ids.add(gid)
        if parse_time(row["kickoff_utc"])<=when:
            # A game begun during long ingestion must not be archived as pregame.
            continue
        if row["betting_status"]!="PASS_UNVALIDATED" or row["total_projection_generated_from_profile"] is not False:
            raise ValueError("Unverified betting total from descriptive profile")
    return True
def archive(board):
    now=dt.datetime.now(dt.timezone.utc)
    validate(board,now.isoformat())
    run_id=str(os.environ.get("GITHUB_RUN_ID",""))
    if not run_id.isdigit():raise ValueError("Live GitHub run required")
    path=ROOT+"/matchup_profiles/"+now.strftime("%Y/%m/%d")+"/run-"+run_id+".json.gz"
    existing=store.get_blob_file(path)
    package={"status":STATUS,"captured_at_utc":now.isoformat(),
             "run_id":run_id,"record":board}
    blob=store.pack(package)
    if existing is not None:
        if existing!=blob:raise ValueError("Cannot rewrite team profile snapshot")
        return {"status":"EXACT_SNAPSHOT_ALREADY_ARCHIVED","path":path}
    old=store.get_blob_file(INDEX)
    index=json.loads(old) if old else {"status":STATUS,"runs":[],"season":2026}
    if index.get("status")!=STATUS or index.get("season")!=2026 or any(
        x["run_id"]==run_id for x in index["runs"]):
        raise ValueError("Conflicting matchup index")
    index["runs"].append({"run_id":run_id,"path":path,
                           "captured_at_utc":now.isoformat(),
                           "sha256":digest(canonical(package))})
    index["runs"].sort(key=lambda r:r["captured_at_utc"])
    sha=_commit_material({path:blob,INDEX:store.encode(index)},run_id)
    return {"status":"ARCHIVED_MATCHUP_STYLE_BOARD","path":path,"sha":sha}
def run(source):
    result=archive(json.loads(Path(source).read_text()))
    print(json.dumps(result))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--board",required=True)
    run(p.parse_args().board)

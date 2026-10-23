"""Independent observed final-score archive for frozen market research.

Unlike personnel outcomes, this archive does not require a 24-72h capture.
Scores never authorize forecasts: market comparison chronology is checked separately.
"""
import argparse,csv,datetime as dt,hashlib,json,os
from pathlib import Path
from scripts import context_archive as store
from scripts.personnel_results_archive import _valid_manifest,_finals,_commit_material
from scripts.game_context import parse_time

ROOT="research_2026/market_finals"
INDEX=ROOT+"/index.json"
STATUS="OBSERVED_MARKET_FINAL_INDEX_RESEARCH_ONLY"

def empty():
    return {"status":STATUS,"season":2026,"games":{},"safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED"}

def verify(index):
    if (index.get("status")!=STATUS or index.get("season")!=2026 or
        index.get("safe_for_betting") is not False or
        index.get("betting_status")!="PASS_UNVALIDATED" or
        not isinstance(index.get("games"),dict)):
        raise ValueError("Invalid independent final index")
    for gid,item in index["games"].items():
        if not gid.isdigit() or item["path"]!=ROOT+"/"+gid+".json.gz":
            raise ValueError("Invalid final index path")
        if not isinstance(item.get("sha256"),str) or len(item["sha256"])!=64:
            raise ValueError("Invalid final digest")

def plan(index,games,manifest,score_bytes,now):
    verify(index)
    observed=parse_time(now)
    retrieved=_valid_manifest(manifest,observed)
    finals=_finals(games,retrieved)
    fresh=json.loads(json.dumps(index));new=[]
    pending={}
    for gid,game in sorted(finals.items()):
        path=ROOT+"/"+gid+".json.gz"
        record={"status":"OBSERVED_INDEPENDENT_MARKET_FINAL","season":2026,
                **game,"source_url":"https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
                "scoreboard_sha256":hashlib.sha256(score_bytes).hexdigest(),
                "outcome_known_at_utc":retrieved.isoformat(),
                "observed_at_utc":observed.isoformat(),
                "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
        digest=hashlib.sha256(store.encode(record)).hexdigest()
        old=fresh["games"].get(gid)
        if old:
            if any(old[k]!=game[k] for k in ("home","away","kickoff_utc","home_score","away_score")):
                pending[gid]="CHANGED_FINAL_REQUIRES_REVIEW"
            continue
        fresh["games"][gid]={**game,"path":path,"sha256":digest}
        new.append((path,record))
    return fresh,new,pending

def run(games_path,manifest_path,output):
    raw=Path(games_path).read_bytes()
    games=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    # Only persist results for already frozen research comparisons.
    from scripts.free_market_comparison_archive import INDEX as COMPARISONS,validate
    comparison_raw=store.get_blob_file(COMPARISONS)
    if comparison_raw is None:raise ValueError("Missing frozen market index")
    comparisons=json.loads(comparison_raw)
    if comparisons.get("status")!="RESEARCH_ONLY":raise ValueError("Invalid market index")
    eligible=set()
    for entry in comparisons["runs"]:
        blob=store.get_blob_file(entry["path"])
        if blob is None:raise ValueError("Missing frozen comparison board")
        board=store.unpack(blob);validate(board)
        if hashlib.sha256(store.encode(board)).hexdigest()!=entry["sha256"]:
            raise ValueError("Frozen comparison checksum mismatch")
        eligible.update(str(row["game_id"]) for row in board["rows"])
    games=[g for g in games if str(g["game_id"]) in eligible]
    manifest=json.loads(Path(manifest_path).read_text())
    blob=store.get_blob_file(INDEX)
    index=json.loads(blob) if blob else empty()
    updated,new,pending=plan(index,games,manifest,raw,dt.datetime.now(dt.timezone.utc).isoformat())
    for gid,item in index["games"].items():
        b=store.get_blob_file(item["path"])
        if b is None or hashlib.sha256(store.encode(store.unpack(b))).hexdigest()!=item["sha256"]:
            raise ValueError("Previously archived final integrity failure")
    result={"status":STATUS,"new_verified_finals":len(new),
            "total_verified_finals":len(updated["games"]),
            "conflicts":pending,"safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    if new:
        material={INDEX:store.encode(updated)}
        material.update({path:store.pack(rec) for path,rec in new})
        result["archive_commit_sha"]=_commit_material(material,os.environ.get("GITHUB_RUN_ID",""))
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("games","manifest","output"):p.add_argument("--"+key,required=True)
    a=p.parse_args();run(a.games,a.manifest,a.output)

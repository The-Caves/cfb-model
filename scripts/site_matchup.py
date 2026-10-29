"""Overlay source-labelled opponent matchup profiles on the actual V03 board.

Uses only earlier captured, validated identity-matched research observations.
Does NOT recompute a betting total, market direction or active model margin.
"""
import argparse,datetime as dt,gzip,json
from pathlib import Path
from scripts.game_context import parse_time
from scripts.team_matchup_intelligence import STATUS as STYLE
STATUS="SOURCE_MATCHED_UPCOMING_TEAM_STYLE_RESEARCH_ONLY"
def overlay(board,profile,observed):
    if board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Untrusted site data")
    if profile.get("status")!=STYLE or profile.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Untrusted team style data")
    index={str(g["game_id"]):g for g in profile["games"]}
    if len(index)!=len(profile["games"]):raise ValueError("Duplicate style game ID")
    obs=parse_time(observed)
    covered=0
    for g in board["games"]:
        row=index.get(str(g["game_id"]))
        if (row is None or (row["home"],row["away"],parse_time(row["kickoff_utc"]))!=
             (g["home_team"],g["away_team"],parse_time(g["kickoff_utc"]))
            or parse_time(g["kickoff_utc"])<=obs):
            g["matchup_intelligence"]=None
            continue
        home=profile["profiles"].get(row["home"])
        away=profile["profiles"].get(row["away"])
        if home is None or away is None:
            g["matchup_intelligence"]=None;continue
        g["matchup_intelligence"]={
            "home":home,"away":away,"matchup":row["matchup"],
            "two_way_run_pass_coverage":row["two_way_run_pass_coverage"],
            "both_turnover_records":row["both_turnover_records"],
            "historical_publication_authenticated":False,
            "source_last_team_profile_cutoff":profile["cutoff_date_exclusive"],
            "not_current_model_input":True}
        covered+=1
    board["matchup_display"]={"status":STATUS,"covered_games":covered,
        "source":"Accepted 2026 PBP and two-sided ESPN team boxscore",
        "changes_frozen_model":False,
        "warning":"These descriptive traits do not alter V03's archived totals or pick. No causal claim about run-stopping or turnovers."}
    return board
def run(board_file,source):
    path=Path(board_file)
    board=json.loads(path.read_text())
    idxpath=Path(source)/"research_2026/matchup_profiles/index.json"
    if not idxpath.exists():
        board["matchup_display"]={"status":"NO_ARCHIVED_RESEARCH_PROFILES",
            "covered_games":0,"changes_frozen_model":False}
        for g in board["games"]:g["matchup_intelligence"]=None
    else:
        idx=json.loads(idxpath.read_text())
        if idx.get("status")!=STYLE or idx.get("season")!=2026:
            raise ValueError("Untrusted profile archive index")
        from scripts.weekly_profiles import canonical,digest
        snapshots=[]
        for entry in idx["runs"]:
            loc=Path(entry["path"])
            if (loc.is_absolute() or ".." in loc.parts or
                not str(loc).startswith("research_2026/matchup_profiles/2026/") or
                not str(loc).endswith("/run-"+entry["run_id"]+".json.gz")):
                raise ValueError("Untrusted profile archive location")
            blob=json.loads(gzip.decompress((Path(source)/loc).read_bytes()))
            if digest(canonical(blob))!=entry["sha256"]:
                raise ValueError("Profile archive hash mismatch")
            snapshots.append(blob)
        snapshots.sort(key=lambda x:x["captured_at_utc"],reverse=True)
        if snapshots:
            chosen=snapshots[0]
            if parse_time(chosen["captured_at_utc"])>dt.datetime.now(dt.timezone.utc):
                raise ValueError("Future site snapshot")
            board=overlay(board,chosen["record"],dt.datetime.now(dt.timezone.utc).isoformat())
        else:
            board["matchup_display"]={"status":"NO_ARCHIVED_RESEARCH_PROFILES",
                "covered_games":0,"changes_frozen_model":False}
            for g in board["games"]:g["matchup_intelligence"]=None
    path.write_text(json.dumps(board,indent=2,allow_nan=False)+"\n")
    print(json.dumps(board["matchup_display"]))
    return board
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--dashboard",required=True)
    p.add_argument("--source",required=True);a=p.parse_args();run(a.dashboard,a.source)

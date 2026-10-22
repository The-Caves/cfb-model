"""2026 pregame feature observations, separate from retrospective histories.

Captures what THIS workflow had before future kickoffs, not historically
authenticated publication times of provider play-by-play releases.
"""
import argparse,datetime as dt,hashlib,json,os
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.model_v03 import load_inputs,timestamp
from scripts.weekly_profiles import build_snapshots,canonical,registry_teams

ET=ZoneInfo("America/New_York")
STATUS="OBSERVED_PREGAME_RESEARCH_CAPTURE"

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def create_capture(games_csv,advanced_csv,advanced_manifest,
                   score_manifest,context_json,registry_csv,
                   run_id,now=None):
    moment=timestamp(now) if now is not None else dt.datetime.now(dt.timezone.utc)
    am=read_json(advanced_manifest)
    sm=read_json(score_manifest)
    context=read_json(context_json)
    if sm.get("status")!="SUCCESS" or sm.get("failures"):
        raise ValueError("Incomplete scoreboard ingestion")
    if (not str(am.get("status","")).startswith("RESEARCH_PBP_IMPORTED")
        or am.get("historical_pregame_availability_verified") is not False):
        raise ValueError("Unverified retrospective source manifest required")
    if not am.get("sources",{}).get("pbp",{}).get("sha256"):
        raise ValueError("Missing provider source checksum")
    source_times={
        "score_retrieved_utc":sm["retrieved_at_utc"],
        "advanced_retrieved_utc":am["retrieved_at_utc"],
        "context_captured_utc":context["captured_at_utc"],
        "context_asof_utc":context["asof_utc"]}
    if timestamp(source_times["context_asof_utc"])>timestamp(source_times["context_captured_utc"]):
        raise ValueError("Context timestamps contradict")
    if any(timestamp(t)>moment for t in source_times.values()):
        raise ValueError("Future source timestamps cannot appear in capture")
    teams=registry_teams(registry_csv)
    if len(teams)!=138:
        raise ValueError("Require 138 canonical FBS teams")
    accepted_games,advanced,loaded=load_inputs(games_csv,advanced_csv,advanced_manifest)
    if any(timestamp(g["kickoff_utc"])>timestamp(sm["retrieved_at_utc"])
           for g in accepted_games):
        raise ValueError("Future completed score contaminates capture")
    existing_games={g["game_id"] for g in accepted_games}
    future=[]
    exclusions=Counter()
    seen=set()
    for g in context.get("games",[]):
        gid=str(g.get("game_id",""))
        if not gid or gid in seen:raise ValueError("Duplicate or empty upcoming game ID")
        seen.add(gid)
        try:
            kickoff=timestamp(g["kickoff_utc"])
            game_date=dt.date.fromisoformat(g["date_et"])
        except (KeyError,TypeError,ValueError):
            exclusions["bad_schedule_timestamp"]+=1
            continue
        if kickoff<=moment:
            exclusions["already_started"]+=1
            continue
        if game_date!=kickoff.astimezone(ET).date():
            exclusions["wrong_football_date"]+=1
            continue
        if (g.get("home") not in teams or g.get("away") not in teams
            or g["home"]==g["away"]):
            exclusions["outside_canonical_FBS"]+=1
            continue
        if gid in existing_games:
            exclusions["already_final"]+=1
            continue
        future.append((g,game_date))
    if not future:raise ValueError("No eligible future FBS matchups")
    frozen={
        p["cutoff_date_exclusive"]:p for p in
        build_snapshots(accepted_games,advanced,teams,
                        sorted({date for _,date in future}))}
    output_games=[]
    for g,date in future:
        by={p["team"]:p for p in frozen[date.isoformat()]["profiles"]}
        selected={"home":by[g["home"]],"away":by[g["away"]]}
        if any(x["last_game_kickoff_utc"] and
               timestamp(x["last_game_kickoff_utc"])>=moment
               for x in selected.values()):
            exclusions["unavailable_prior_game"]+=1
            continue
        output_games.append({
            "game_id":str(g["game_id"]),"kickoff_utc":g["kickoff_utc"],
            "date_et":g["date_et"],"home":g["home"],"away":g["away"],
            "home_team_id":str(g.get("home_team_id","")),
            "away_team_id":str(g.get("away_team_id","")),
            "team_profiles":selected,
            "team_profiles_sha256":sha(canonical(selected)),
            "profile_source":"RETROSPECTIVE_RECONSTRUCTION_UNVERIFIED"})
    if not output_games:raise ValueError("No eligible matchup profiles")
    files={"score_csv":games_csv,"advanced_csv":advanced_csv,
           "advanced_manifest":advanced_manifest,"score_manifest":score_manifest,
           "context_json":context_json,"registry_csv":registry_csv}
    return {
        "status":STATUS,"season":2026,"run_id":str(run_id),
        "captured_at_utc":moment.isoformat(),
        "sources":source_times,
        "source_file_sha256":{k:sha(Path(v).read_bytes()) for k,v in files.items()},
        "original_provider_pbp_sha256":loaded["sources"]["pbp"]["sha256"],
        "games":output_games,
        "qa":{"eligible_games":len(output_games),"excluded":dict(exclusions)},
        "historical_publication_times_verified":False,
        "capture_artifact_authenticity_verified":False,
        "durable_storage_verified":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

def get_asof_feature(capture,game_id,decision_utc):
    if (capture.get("status")!=STATUS or capture.get("safe_for_betting") is not False
        or capture.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Invalid capture state")
    when=timestamp(decision_utc)
    observed=timestamp(capture["captured_at_utc"])
    if observed>when:raise ValueError("Capture not available by decision")
    if any(timestamp(t)>observed for t in capture["sources"].values()):
        raise ValueError("Source after capture")
    games=[g for g in capture["games"] if str(g["game_id"])==str(game_id)]
    if len(games)!=1:raise ValueError("Absent or duplicate event ID")
    g=games[0]
    if when>=timestamp(g["kickoff_utc"]):
        raise ValueError("Prediction decision after kickoff")
    if sha(canonical(g["team_profiles"]))!=g["team_profiles_sha256"]:
        raise ValueError("Team profile checksum mismatch")
    if g.get("profile_source")!="RETROSPECTIVE_RECONSTRUCTION_UNVERIFIED":
        raise ValueError("Incorrect historical evidence status")
    return {"game_id":g["game_id"],"team_profiles":g["team_profiles"],
            "observed_at_utc":capture["captured_at_utc"],
            "provenance":"CAPTURED_BY_WORKFLOW_NOT_EXTERNALLY_ATTESTED",
            "historical_publication_times_verified":False,
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

def save(capture,path):
    if not str(capture["run_id"]).isdigit():
        raise ValueError("GitHub numeric run ID required")
    root=Path(path);root.mkdir(parents=True,exist_ok=True)
    target=root/("capture-"+capture["run_id"]+".json")
    blob=canonical(capture)
    with target.open("xb") as output:output.write(blob)
    return {"status":STATUS,"file":target.name,"sha256":sha(blob),
            "eligible_games":len(capture["games"]),
            "durable_storage_verified":False,"betting_status":"PASS_UNVALIDATED"}

if __name__=="__main__":
    a=argparse.ArgumentParser()
    for name in ("games","advanced","advanced-manifest","score-manifest",
                 "context","registry","output"):
        a.add_argument("--"+name,required=True)
    a.add_argument("--run-id",default=os.environ.get("GITHUB_RUN_ID",""))
    p=a.parse_args()
    obj=create_capture(p.games,p.advanced,p.advanced_manifest,
         p.score_manifest,p.context,p.registry,p.run_id)
    print(json.dumps(save(obj,p.output),sort_keys=True))

"""Reconstruct checksummed 2026-only weekly and game-date team profiles.

These are RETROSPECTIVE reconstructions, not authenticated pregame published
snapshots. Immutable means files never silently overwrite earlier captures.
"""
import argparse,csv,datetime as dt,hashlib,json
from pathlib import Path
from collections import defaultdict
from scripts.model_v03 import (
    load_inputs,group_by_date,advance_completed_day,summarize,timestamp
)

STATUS="RETROSPECTIVE_RECONSTRUCTION_UNVERIFIED"
METRICS=("points_for","points_against","margin","win","epa_off","epa_def",
         "epa_pass","epa_rush","success","explosive_pass","explosive_rush",
         "pressure","drive_yards","pass_rate","epa_off_adj","epa_def_adj",
         "epa_coverage")

def canonical(data):
    return (json.dumps(data,sort_keys=True,separators=(",",":"),
             ensure_ascii=False,allow_nan=False)+"\n").encode()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def registry_teams(path):
    with open(path,newline="",encoding="utf-8-sig") as handle:
        rd=csv.DictReader(handle)
        if "espn_display_name" not in (rd.fieldnames or []):
            raise ValueError("Canonical school registry column missing")
        teams=[r["espn_display_name"].strip() for r in rd]
    if not teams or any(not x for x in teams) or len(set(teams))!=len(teams):
        raise ValueError("Missing or duplicated canonical schools")
    return sorted(teams)

def cutoff_dates(games,through):
    end=dt.date.fromisoformat(through)
    anchor=dt.date(2026,8,1)
    if not anchor<=end or end.year!=2026:
        raise ValueError("Must choose a 2026 date from August onward")
    cutoffs={end}
    for g in games:
        day=dt.date.fromisoformat(g["date"])
        if anchor<=day<=end:cutoffs.add(day)
    cursor=anchor
    while cursor<=end:
        cutoffs.add(cursor)
        cursor+=dt.timedelta(days=7)
    return sorted(cutoffs)

def build_snapshots(games,advanced,teams,cutoffs):
    if not teams or len(teams)!=len(set(teams)):
        raise ValueError("Unique canonical team names required")
    if not cutoffs or list(cutoffs)!=sorted(set(cutoffs)):
        raise ValueError("Cutoffs must be strictly increasing and unique")
    histories=defaultdict(list)
    grouped=list(group_by_date(games))
    idx=0
    snapshots=[]
    for cutoff in cutoffs:
        if cutoff.year!=2026:raise ValueError("Season must be 2026")
        while idx<len(grouped):
            _,group=grouped[idx]
            if dt.date.fromisoformat(group[0]["date"])>=cutoff:break
            advance_completed_day(histories,group,advanced)
            idx+=1
        # Archive is indexed by a football date, not a fictional kickoff.
        # Rest varies by actual game kickoff and is deliberately not frozen.
        now=timestamp(cutoff.isoformat()+"T00:00:00Z")
        profiles=[]
        for team in sorted(teams):
            past=histories[team]
            if any(dt.date.fromisoformat(r["game_date"])>=cutoff for r in past):
                raise ValueError("Future game leaked into profile")
            metrics=summarize(past,now,cutoff)
            profiles.append({
                "team":team,"games_before_cutoff":len(past),
                "prior_game_ids":[r["game_id"] for r in past],
                "last_game_kickoff_utc":past[-1]["kickoff"].isoformat() if past else None,
                "recent_form":{key:metrics[key] for key in METRICS}
            })
        snapshots.append({
            "format":"2026-retro-profiles-v1",
            "season":2026,"cutoff_date_exclusive":cutoff.isoformat(),
            "profiles":profiles,"evidence_status":STATUS,
            "historical_publication_times_verified":False,
            "betting_status":"PASS_UNVALIDATED","safe_for_betting":False
        })
    return snapshots

def save_snapshots(snapshots,output,manifest,input_digests):
    root=Path(output)
    root.mkdir(parents=True,exist_ok=True)
    prepared=[]
    for snapshot in snapshots:
        name="asof-"+snapshot["cutoff_date_exclusive"]+".json"
        p=root/name
        blob=canonical(snapshot)
        if p.exists() and p.read_bytes()!=blob:
            raise ValueError("FROZEN_PROFILE_DRIFT "+name)
        prepared.append((p,blob,snapshot))
    if (root/"capture_manifest.json").exists():
        raise ValueError("Capture manifest already exists; choose a new output directory")
    for p,blob,_ in prepared:
        if not p.exists():
            with p.open("xb") as out:out.write(blob)
    report={
        "status":"RETROSPECTIVE_PROFILE_ARCHIVE_CREATED",
        "season":2026,"evidence_status":STATUS,
        "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
        "historical_publication_times_verified":False,
        "provider_retrieved_at_utc":manifest["retrieved_at_utc"],
        "source_csv_sha256":input_digests,
        "provider_asset_sha256":{k:v.get("sha256") for k,v in manifest["sources"].items()},
        "cutoff_count":len(prepared),
        "teams_per_cutoff":len(snapshots[0]["profiles"]) if snapshots else 0,
        "snapshots":[{
            "cutoff_date_exclusive":row["cutoff_date_exclusive"],
            "filename":p.name,"sha256":digest(blob),
            "teams_with_prior_games":sum(q["games_before_cutoff"]>0 for q in row["profiles"])
        } for p,blob,row in prepared],
        "limitations":[
            "Historical providers may have revised past data after the game.",
            "Source publication-time provenance is not authenticated.",
            "QB, injuries and live sportsbook lines have not been incorporated.",
            "GitHub Actions artifact retention is 30 days, not durable archival."]
    }
    with (root/"capture_manifest.json").open("xb") as out:
        out.write(canonical(report))
    return report

def run(games,advanced,manifest,registry,output,through):
    games_list,adv,src=load_inputs(games,advanced,manifest)
    teams=registry_teams(registry)
    if len(teams)!=138:raise ValueError("Expected 138 canonical FBS teams")
    cutoffs=cutoff_dates(games_list,through)
    records=build_snapshots(games_list,adv,teams,cutoffs)
    hashes={
        "espn_games":digest(Path(games).read_bytes()),
        "advanced_team_games":digest(Path(advanced).read_bytes()),
        "canonical_registry":digest(Path(registry).read_bytes())
    }
    report=save_snapshots(records,output,src,hashes)
    print(json.dumps({"status":report["status"],"cutoff_count":len(records),
                      "teams_per_cutoff":len(teams),"betting_status":"PASS_UNVALIDATED"}))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True)
    p.add_argument("--advanced",required=True)
    p.add_argument("--manifest",required=True)
    p.add_argument("--registry",default="data/archive/2026_team_aliases.csv")
    p.add_argument("--output",required=True)
    p.add_argument("--through-date",required=True)
    a=p.parse_args()
    run(a.games,a.advanced,a.manifest,a.registry,a.output,a.through_date)

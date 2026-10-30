"""Append-only observed postgame QB evidence, not first-passer guessed starters.

An archived first report, its source identity and SHA, and subsequent
different classifications are retained. Contradictory later provider labels
force a quarantine, never a silent edit of an established training label.
"""
import argparse,datetime as dt,hashlib,json,os,re
from pathlib import Path
from scripts import context_archive as store
from scripts.game_context import parse_time
from scripts.qb_passer_history import player_key
from scripts.qb_postgame_starter_labels import STATUS as OBSERVED,LABEL,UNKNOWN,URL
from scripts.personnel_results_archive import ROOT,_commit_material

STATUS="QB_POSTGAME_STARTER_OBSERVATION_LEDGER_RESEARCH_ONLY"
INDEX=ROOT+"/qb_postgame_starters/index.json"
PATH_PREFIX=ROOT+"/qb_postgame_starters/"
VALID={LABEL,UNKNOWN,"CONFLICT_MULTIPLE_EXPLICIT_QB_FLAGS"}
DANGER="CONFLICT_REQUIRES_INDEPENDENT_REVIEW"

def empty():
    return {"status":STATUS,"season":2026,"runs":[],"slots":{},
            "betting_status":"PASS_UNVALIDATED","model_promoted":False}

def _sha(value):
    return hashlib.sha256(store.encode(value)).hexdigest()

def verify_index(index):
    if (index.get("status")!=STATUS or index.get("season")!=2026
        or index.get("betting_status")!="PASS_UNVALIDATED"
        or index.get("model_promoted") is not False
        or not isinstance(index.get("runs"),list)
        or not isinstance(index.get("slots"),dict)):
        raise ValueError("Untrusted QB postgame label index")
    paths=set();runs=set()
    for r in index["runs"]:
        rid=str(r.get("run_id"));p=r.get("path")
        if (not rid.isdigit() or rid in runs or not isinstance(p,str)
            or not re.fullmatch(r"research_2026/qb_postgame_starters/2026/\d{2}/\d{2}/run-\d+\.json\.gz",p)
            or not p.endswith("/run-"+rid+".json.gz")
            or not re.fullmatch("[0-9a-f]{64}",r.get("sha256",""))):
            raise ValueError("Corrupt postgame QB archive index")
        runs.add(rid)
        if p in paths:raise ValueError("Duplicate label archive")
        paths.add(p)
    for key,value in index["slots"].items():
        if (not re.fullmatch(r"\d{6,12}\|[^|]+",key)
            or value.get("effective_status") not in VALID|{DANGER}
            or not isinstance(value.get("observations"),list)
            or not value["observations"]):
            raise ValueError("Invalid indexed game/team starter audit")
        for o in value["observations"]:
            if (o.get("path") not in paths
                or o.get("label_status") not in VALID
                or not re.fullmatch("[0-9a-f]{64}",o.get("source_payload_sha256",""))):
                raise ValueError("Unbound postgame QB observation")
    return True

def validate(snapshot):
    if (snapshot.get("status")!=OBSERVED or snapshot.get("season")!=2026
        or snapshot.get("source")!="ESPN_SITE_GAME_SUMMARY"
        or snapshot.get("postgame_labels_never_pregame_features") is not True
        or snapshot.get("historical_publication_times_verified") is not False
        or snapshot.get("model_promoted") is not False
        or snapshot.get("safe_for_betting") is not False
        or snapshot.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Untrusted postgame QB evidence")
    observed=parse_time(snapshot["captured_at_utc"])
    if snapshot["team_slots"]!=len(snapshot["rows"]):
        raise ValueError("Incorrect labeled row count")
    keys=set()
    for r in snapshot["rows"]:
        gid=str(r["game_id"]);team=r["team"];key=gid+"|"+team
        if (not re.fullmatch(r"\d{6,12}",gid) or "|" in team or
            key in keys or r["label_status"] not in VALID or
            r["betting_status"]!="PASS_UNVALIDATED" or
            r.get("source_url")!=URL+gid or
            r.get("not_from_passing_leader") is not True or
            r.get("historical_publication_time_verified") is not False or
            not re.fullmatch("[0-9a-f]{64}",r.get("source_payload_sha256","")) or
            parse_time(r["kickoff_utc"])>=parse_time(r["captured_at_utc"]) or
            parse_time(r["captured_at_utc"])>observed):
            raise ValueError("Source, timestamp, duplicate or row schema invalid")
        if (r["label_status"]==LABEL)!=(isinstance(r.get("starter_player"),str)
                                     and len(player_key(r["starter_player"]))>=2):
            raise ValueError("Unsigned or missing actual QB starter label")
        if r["label_status"]==LABEL and r.get("explicit_qb_starter_flags")!=1:
            raise ValueError("QB starter not uniquely flagged")
        keys.add(key)
    return observed

def plan(old,snapshot,run_id):
    verify_index(old);observed=validate(snapshot)
    if not str(run_id).isdigit():raise ValueError("Missing numeric GitHub run")
    day=observed.strftime("%Y/%m/%d")
    path=PATH_PREFIX+day+"/run-"+str(run_id)+".json.gz"
    if any(x["run_id"]==str(run_id) for x in old["runs"]):
        raise ValueError("Already archived this postgame run")
    next_index=json.loads(json.dumps(old))
    fresh=[]
    for row in snapshot["rows"]:
        key=str(row["game_id"])+"|"+row["team"]
        prior=next_index["slots"].get(key)
        # Avoid appending the same positive/negative interpretation on each
        # scheduled fetch, but preserve changes and source origin.
        sign=(row["label_status"],player_key(row["starter_player"] or ""))
        last=(prior["observations"][-1]["label_status"],
              player_key(prior["observations"][-1]["starter_player"] or "")) if prior else None
        if sign==last:continue
        entry={"path":path,"captured_at_utc":row["captured_at_utc"],
               "label_status":row["label_status"],"starter_player":row["starter_player"],
               "source_url":row["source_url"],
               "source_payload_sha256":row["source_payload_sha256"]}
        if prior is None:
            next_index["slots"][key]={"game_id":str(row["game_id"]),"team":row["team"],
                "observations":[entry],"effective_status":row["label_status"],
                "starter_player":row["starter_player"] if row["label_status"]==LABEL else None}
        else:
            prior["observations"].append(entry)
            # Once a source flips or contradicts its prior interpretation,
            # require independent adjudication; never auto-correct training labels.
            prior["effective_status"]=DANGER
            prior["starter_player"]=None
        fresh.append(row)
    if fresh:
        run={"status":STATUS,"season":2026,"run_id":str(run_id),
            "captured_at_utc":observed.isoformat(),"rows":fresh,
            "postgame_labels_never_pregame_features":True,
            "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}
        next_index["runs"].append({"run_id":str(run_id),"path":path,
                                   "sha256":_sha(run),"captured_at_utc":observed.isoformat(),
                                   "new_observations":len(fresh)})
    else:run=None
    verify_index(next_index)
    n=sum(r["effective_status"]==LABEL for r in next_index["slots"].values())
    conflicts=sum(r["effective_status"]==DANGER for r in next_index["slots"].values())
    return next_index,run,{"new_starter_observations":len(fresh),
       "cumulative_game_team_slots":len(next_index["slots"]),
       "eligible_provider_flag_starter_labels":n,
       "quarantined_conflicts":conflicts,
       "other_slots_unresolved":len(next_index["slots"])-n-conflicts,
       "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}

def run(input_file,output):
    snapshot=json.loads(Path(input_file).read_text(encoding="utf-8"))
    run_id=os.environ.get("GITHUB_RUN_ID","")
    now=dt.datetime.now(dt.timezone.utc)
    observed=validate(snapshot)
    if (not run_id.isdigit() or store.branch_head() is None
        or not 0<=(now-observed).total_seconds()<1200):
        raise ValueError("Cannot archive stale or unidentified postgame observation")
    raw=store.get_blob_file(INDEX)
    old=json.loads(raw) if raw else empty()
    # On every write, ensure the referenced immutable record bytes exist.
    verify_index(old)
    for entry in old["runs"]:
        blob=store.get_blob_file(entry["path"])
        if blob is None or _sha(store.unpack(blob))!=entry["sha256"]:
            raise ValueError("Immutable prior QB label evidence missing or changed")
    updated,extra,counts=plan(old,snapshot,run_id)
    if extra is not None:
        entry=updated["runs"][-1]
        commit=_commit_material({INDEX:store.encode(updated),
                                 entry["path"]:store.pack(extra)},run_id)
        counts["archive_commit_sha"]=commit
    else:counts["archive_status"]="NO_NEW_EVIDENCE"
    destination=Path(output);destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open("x",encoding="utf-8") as file:
        json.dump({"status":STATUS,**counts},file,indent=2,allow_nan=False);file.write("\n")
    print(json.dumps(counts))
    return counts

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.input,a.output)

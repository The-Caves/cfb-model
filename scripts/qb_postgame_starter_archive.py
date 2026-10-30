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
OFFICIAL_SOURCE="REVIEWED_OFFICIAL_SCHOOL_BOXSCORE_HTML"
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
        or snapshot.get("source") not in ("ESPN_SITE_GAME_SUMMARY",OFFICIAL_SOURCE)
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
            (r.get("source_url")!=URL+gid if snapshot["source"]=="ESPN_SITE_GAME_SUMMARY"
             else (r.get("source_class")!=OFFICIAL_SOURCE or not isinstance(r.get("source_url"),str)
                   or not r["source_url"].startswith("https://")
                   or "/sports/football/stats/2026/" not in r["source_url"])) or
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

def plan(old,snapshot,run_id,corrections=None):
    verify_index(old);observed=validate(snapshot)
    corrections=corrections or {}
    if not isinstance(corrections,dict):raise ValueError("Untrusted QB correction registry")
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
        last_obs=prior["observations"][-1] if prior else None
        last=(last_obs["label_status"],
              player_key(last_obs["starter_player"] or "")) if last_obs else None
        if sign==last:continue
        if (prior and prior["effective_status"]==LABEL and
            row["label_status"]==UNKNOWN and
            # ESPN's missing starter flag must never retract an accepted
            # independent official university offensive starter lineup.
            row["source_url"]!=last_obs["source_url"]):
            continue
        proposed=corrections.get(key)
        permitted_correction=False
        if proposed is not None:
            if (not prior or prior["effective_status"]!=LABEL or
                row["label_status"]!=LABEL or
                snapshot["source"]!="REVIEWED_OFFICIAL_SCHOOL_BOXSCORE_HTML" or
                proposed.get("source_url")!=row["source_url"] or
                proposed.get("source_url")!=last_obs["source_url"] or
                proposed.get("old_source_payload_sha256")!=last_obs["source_payload_sha256"] or
                proposed.get("old_player")!=prior["starter_player"] or
                proposed.get("new_player")!=row["starter_player"]):
                raise ValueError("Reviewed QB name correction provenance mismatch")
            permitted_correction=True
        entry={"path":path,"captured_at_utc":row["captured_at_utc"],
               "label_status":row["label_status"],"starter_player":row["starter_player"],
               "source_url":row["source_url"],
               "source_class":snapshot["source"],
               "source_payload_sha256":row["source_payload_sha256"]}
        if permitted_correction:
            entry["reviewed_adjudication"]={
                "kind":"SCHOOL_BOXSCORE_TEAM_LOGO_ALT_PARSER_REPAIR",
                "old_player":proposed["old_player"],
                "new_player":proposed["new_player"],
                "prior_source_payload_sha256":proposed["old_source_payload_sha256"],
                "provenance":"EXACT_REVIEWED_SOURCE_NAME_AND_ORIGINAL_CAPTURE_SHA",
                "source_url":proposed["source_url"]}
        if prior is None:
            next_index["slots"][key]={"game_id":str(row["game_id"]),"team":row["team"],
                "observations":[entry],"effective_status":row["label_status"],
                "starter_player":row["starter_player"] if row["label_status"]==LABEL else None}
        else:
            prior["observations"].append(entry)
            # UNKNOWN -> first genuine explicit label is useful new evidence,
            # not a contradiction. Any later removal/change of an accepted
            # explicit label or an existing conflict is quarantined.
            if permitted_correction:
                prior["effective_status"]=LABEL
                prior["starter_player"]=row["starter_player"]
            elif prior["effective_status"]==UNKNOWN and row["label_status"]==LABEL:
                prior["effective_status"]=LABEL
                prior["starter_player"]=row["starter_player"]
            elif prior["effective_status"]==DANGER:
                prior["starter_player"]=None
            else:
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

def reviewed_corrections(path):
    if not Path(path).is_file():return {}
    data=json.loads(Path(path).read_text())
    if (data.get("status")!="AUDITED_SCHOOL_GAMEBOOK_PARSER_ALT_TEXT_CORRECTIONS"
        or data.get("season")!=2026 or not isinstance(data.get("entries"),list)):
        raise ValueError("Untrusted reviewed starter name correction manifest")
    rows={}
    for item in data["entries"]:
        key=str(item.get("game_id"))+"|"+str(item.get("team"))
        if (key in rows or not str(item.get("game_id","")).isdigit()
            or not item.get("old_player") or not item.get("new_player")
            or not isinstance(item.get("source_url"),str)
            or not item["source_url"].startswith("https://")
            or not re.fullmatch("[0-9a-f]{64}",item.get("old_source_payload_sha256",""))):
            raise ValueError("Invalid QB starter name correction record")
        rows[key]=item
    return rows

def source_archive_run_id(actions_run_id,source):
    """One unique index key per source within a single serial workflow."""
    if not str(actions_run_id).isdigit():
        raise ValueError("Missing numeric Actions run")
    if source=="REVIEWED_OFFICIAL_SCHOOL_BOXSCORE_HTML":
        return str(actions_run_id)+"2"
    if source=="ESPN_SITE_GAME_SUMMARY":
        return str(actions_run_id)
    raise ValueError("Unreviewed actual-starter evidence source")

def run(input_file,output):
    snapshot=json.loads(Path(input_file).read_text(encoding="utf-8"))
    # Two source-specific archive keys per Actions run avoid index collisions.
    # The legacy ESPN key remains unchanged for existing archived observations.
    run_id=source_archive_run_id(os.environ.get("GITHUB_RUN_ID",""),
                                 snapshot.get("source"))
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
    corrections=(reviewed_corrections("config/official_school_qb_name_corrections_2026.json")
                 if snapshot["source"]=="REVIEWED_OFFICIAL_SCHOOL_BOXSCORE_HTML" else {})
    # The correction manifest is restricted to historical parser errors. When
    # the corrected source is not in this particular batch, leave it untouched.
    applicable={str(r["game_id"])+"|"+r["team"]:corrections[str(r["game_id"])+"|"+r["team"]]
                for r in snapshot["rows"]
                if str(r["game_id"])+"|"+r["team"] in corrections
                and old["slots"].get(str(r["game_id"])+"|"+r["team"],{}).get("starter_player")==
                   corrections[str(r["game_id"])+"|"+r["team"]]["old_player"]}
    updated,extra,counts=plan(old,snapshot,run_id,applicable)
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

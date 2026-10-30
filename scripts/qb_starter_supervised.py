"""As-of starter-training join: reviewed postgame labels × frozen pregame QB slates.

There is intentionally NO train(), fit(), or invented P(QB starts). A valid
example requires an independently captured real postgame QB starter, the exact
pre-kickoff team/fixture, and an archived QB candidate observation 24–72h
before kickoff. School parser correction mismatches are quarantined.
"""
import argparse,csv,datetime as dt,hashlib,json,math,re
from collections import Counter
from pathlib import Path
from scripts import context_archive as store
from scripts.game_context import parse_time
from scripts.qb_passer_history import player_key
from scripts.personnel_forecast import checksum
from scripts.qb_postgame_starter_archive import (
    STATUS as LEDGER_STATUS, LABEL, DANGER, UNKNOWN, verify_index)
from scripts.candidate_shadow_archive import validate as validate_shadow

STATUS="QB_STARTER_ASOF_LABELED_TRAINING_READINESS_RESEARCH_ONLY"
SHADOW_INDEX="research_2026/candidate_shadow_qb/index.json"
LABEL_INDEX="research_2026/qb_postgame_starters/index.json"
MIN_LABELED_SLOTS=80
MIN_DISTINCT_FOOTBALL_DATES=4
MIN_ROSTER_MATCH_FRACTION=.75
SCHOOL="REVIEWED_OFFICIAL_SCHOOL_BOXSCORE_HTML"

def _valid_registry(registry):
    if not isinstance(registry,dict) or registry.get(
        "status")!="MANUALLY_REVIEWED_OFFICIAL_SCHOOL_POSTGAME_BOXSCORES" or registry.get(
        "season")!=2026 or not isinstance(registry.get("entries"),list):
        raise ValueError("Untrusted official school starter name registry")
    out={}
    for entry in registry["entries"]:
        if not entry.get("reviewed_official_publisher") is True:
            raise ValueError("Unreviewed school boxscore source")
        gid=str(entry["game_id"])
        for side in ("home","away"):
            k=(gid,entry[side])
            if k in out:raise ValueError("Duplicate reviewed QB roster")
            name=entry.get(side+"_starting_qb_name")
            if not isinstance(name,str) or not player_key(name):
                raise ValueError("Missing reviewed actual starter name")
            out[k]=(name,entry["source_url"])
    return out

def _clean_name(name):
    if not isinstance(name,str) or not 2<=len(name)<=100:
        raise ValueError("Invalid quarterback name")
    key=player_key(name)
    if len(key)<2:raise ValueError("No quarterback identity")
    return key

def _maybe_positive(info,game_id,team,school_names,at):
    if info.get("effective_status")!=LABEL:return None,"NOT_REVIEWED_ACTUAL_STARTER"
    actual=info.get("starter_player")
    akey=_clean_name(actual)
    positive=[o for o in info["observations"] if o.get("label_status")==LABEL and
              isinstance(o.get("starter_player"),str) and
              player_key(o["starter_player"])==akey]
    if not positive:
        raise ValueError("Effective accepted QB starter missing original source observation")
    observation=positive[-1]
    if parse_time(observation["captured_at_utc"])>at:
        return None,"STARTER_LABEL_NOT_OBSERVED_YET"
    src=observation.get("source_class") or (
        "ESPN_SITE_GAME_SUMMARY" if "site.api.espn.com" in observation["source_url"] else "UNKNOWN")
    if src==SCHOOL:
        reviewed=school_names.get((game_id,team))
        if (reviewed is None or observation["source_url"]!=reviewed[1] or
            akey!=player_key(reviewed[0])):
            return None,"SCHOOL_PARSER_NAME_OR_SOURCE_UNREVIEWED"
    elif src=="ESPN_SITE_GAME_SUMMARY":
        if observation["source_url"]!=(
            "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event="+game_id):
            return None,"ESPN_STARTER_SOURCE_IDENTITY_MISMATCH"
    else:return None,"UNSUPPORTED_POSTGAME_STARTER_SOURCE"
    return (actual,observation),None

def _candidate_features(raw):
    if not isinstance(raw,dict):raise ValueError("Untrusted frozen player scenario")
    rank=raw.get("depth_rank")
    if rank is not None and (type(rank) is not int or not 1<=rank<=3):
        raise ValueError("Untrusted frozen player depth rank")
    played=raw.get("prior_passing_plays",0)
    if played is None:played=0
    if type(played) not in (int,float) or not 0<=played<=1500 or not math.isfinite(played):
        raise ValueError("Nonfinite QB historic play count")
    ep=raw.get("player_passing_epa")
    if ep is not None and (type(ep) not in (int,float) or not math.isfinite(ep) or abs(ep)>40):
        raise ValueError("Nonfinite QB predecision EPA")
    return {"depth_rank":rank,"prior_passing_plays":int(played),
            "player_passing_epa":ep,
            "has_prior_player_epa":ep is not None,
            "margin_impact_research_only":raw.get("margin_impact",0.)}

def build(shadows,ledger,reviewed_registry,asof_utc,verify_sources=False):
    asof=parse_time(asof_utc)
    verify_index(ledger)
    reviewed=_valid_registry(reviewed_registry)
    reasons=Counter()
    selected={}
    seen_runs=set()
    total_eligible=0
    for data in shadows:
        rid,observed=validate_shadow(data,"qb")
        if rid in seen_runs:raise ValueError("Repeated immutable QB shadow forecast run")
        seen_runs.add(rid)
        if observed>asof:continue
        for row in data["games"]:
            gid=str(row["game_id"])
            kickoff=parse_time(row["kickoff_utc"])
            hours=(kickoff-observed).total_seconds()/3600
            if not 24<=hours<=72:
                reasons["OUTSIDE_FIXED_24_TO_72H_WINDOW"]+=2
                continue
            cand=row["candidate"]
            if cand.get("status") not in (
                    "QB_PLAYER_CONDITIONAL_SHADOW","PASS_NO_VERIFIED_PERFORMANCE_SAMPLE"):
                reasons["NO_FROZEN_QB_CANDIDATE"]+=2
                continue
            for side in ("away","home"):
                team=row[side]
                slot_key=(gid,team)
                team_info=cand.get("expected_starters_by_side",{}).get(side)
                player_scenarios=cand.get("player_scenarios_by_side",{}).get(side)
                if not isinstance(team_info,dict) or not isinstance(player_scenarios,dict):
                    raise ValueError("QB shadow lacks frozen candidate information")
                total_eligible+=1
                # This is the same pre-registered latest eligible lead policy
                # as the immutable scored-forecast grade; never select by result.
                priority=(observed,rid)
                if slot_key in selected and priority<=selected[slot_key][0]:continue
                selected[slot_key]=(priority,row,side,team_info,player_scenarios,data)
    # Prioritize independently completed team-games with frozen pregame QB
    # candidates that still cannot yield a verified labeled example.
    # This is a REVIEW WORKLIST, never an automatically confirmed QB.
    review_targets=[]
    for (gid,team),(_,game,side,slot,candidates,shadow) in sorted(selected.items()):
        archived=ledger["slots"].get(gid+"|"+team)
        if archived is None:
            continue  # No independently completed game/ESPN label observation.
        kickoff=parse_time(game["kickoff_utc"])
        if kickoff>=asof or archived.get("team")!=team or archived.get("game_id")!=gid:
            raise ValueError("Invalid completed QB review game identity")
        positive,reason=_maybe_positive(archived,gid,team,reviewed,asof)
        if positive:
            actual=positive[0]
            if player_key(actual) not in {player_key(name) for name in candidates}:
                reason="VERIFIED_STARTER_NOT_IN_FROZEN_CANDIDATES"
            else:
                continue  # Already trainable: don't waste future review effort.
        review_targets.append({
            "game_id":gid,"team":team,
            "opponent":game["away"] if side=="home" else game["home"],
            "home":game["home"],"away":game["away"],
            "kickoff_utc":game["kickoff_utc"],
            "forecast_observed_utc":shadow["observed_at_utc"],
            "reason":reason,
            "postgame_label_status":archived["effective_status"],
            "projected_qb_not_confirmation":slot.get("player"),
            "frozen_qb_candidate_names":sorted(candidates),
            "review_required":True,
            "actual_starter":positive[0] if positive else None,
            "exact_school_gamebook_url":None,
            "do_not_guess_gamebook_url":True})
    examples=[]
    accepted_labels=0;unmatched=0
    for (gid,team),(_,game,side,slot,candidates,shadow) in sorted(selected.items()):
        archived=ledger["slots"].get(gid+"|"+team)
        if not archived:
            reasons["NO_POSTGAME_SOURCE_LABEL"]+=1;continue
        if archived.get("game_id")!=gid or archived.get("team")!=team:
            raise ValueError("Starter label game/team identity changed")
        label,skip=_maybe_positive(archived,gid,team,reviewed,asof)
        if skip:
            reasons[skip]+=1;continue
        accepted_labels+=1
        actual,source=label
        kickoff=parse_time(game["kickoff_utc"])
        when=parse_time(source["captured_at_utc"])
        if not kickoff<when<=asof:
            raise ValueError("After-game starter label missing proper chronology")
        names={}
        for name,player in candidates.items():
            normalized=_clean_name(name)
            if normalized in names:
                raise ValueError("Duplicate frozen normalized candidate")
            names[normalized]=(name,player)
        true_key=_clean_name(actual)
        if true_key not in names:
            reasons["VERIFIED_STARTER_NOT_IN_FROZEN_CANDIDATES"]+=1
            unmatched+=1
            continue
        exposure=cand_exposure=game["candidate"].get("empirical_pass_exposure_by_side",{}).get(side,{})
        weights={player_key(k):v for k,v in exposure.get("weights",{}).items()}
        unknown=exposure.get("unknown_weight",1.)
        if type(unknown) not in (float,int) or not 0<=unknown<=1:
            raise ValueError("Invalid frozen unknown QB exposure")
        features=[]
        for key,(name,player) in sorted(names.items()):
            usage=weights.get(key,0.)
            if type(usage) not in (float,int) or not 0<=usage<=1:
                raise ValueError("Invalid frozen player exposure")
            features.append({
                "player":name,
                "is_actual_postgame_starter":int(key==true_key),
                "is_projected_next_starter":int(key==player_key(slot.get("player") or "")),
                "empirical_recent_pass_exposure_not_calibrated":usage,
                **_candidate_features(player)})
        if sum(x["is_actual_postgame_starter"] for x in features)!=1:
            raise ValueError("Supervised QB label is ambiguous")
        examples.append({
            "game_id":gid,"team":team,"opponent":game["away"] if side=="home" else game["home"],
            "home":game["home"],"away":game["away"],
            "kickoff_utc":game["kickoff_utc"],
            "pregame_observed_utc":shadow["observed_at_utc"],
            "pregame_run_id":str(shadow["baseline_forecast_run_id"]),
            "pregame_shadow_sha256":checksum(shadow),
            "baseline_forecast_sha256":shadow["baseline_forecast_sha256"],
            "starter_expected_source_status":slot.get("status"),
            "starter_expected_source_confidence":slot.get("confidence"),
            "unknown_pregame_pass_exposure":unknown,
            "actual_starter_player":actual,
            "actual_starter_source_url":source["source_url"],
            "actual_starter_source_sha256":source["source_payload_sha256"],
            "actual_starter_observed_utc":source["captured_at_utc"],
            "candidates":features,"not_validated_for_betting":True})
    distinct_dates={parse_time(row["kickoff_utc"]).date().isoformat() for row in examples}
    enough=(len(examples)>=MIN_LABELED_SLOTS and
            len(distinct_dates)>=MIN_DISTINCT_FOOTBALL_DATES and
            accepted_labels>0 and len(examples)/accepted_labels>=MIN_ROSTER_MATCH_FRACTION)
    return {"status":STATUS,"season":2026,"asof_utc":asof.isoformat(),
        "ready_for_calibrated_starter_training":enough,
        "minimum_labeled_slots":MIN_LABELED_SLOTS,
        "minimum_distinct_game_dates":MIN_DISTINCT_FOOTBALL_DATES,
        "minimum_roster_match_fraction":MIN_ROSTER_MATCH_FRACTION,
        "summary":{"archived_qb_shadows":len(seen_runs),
            "predecisional_eligible_team_slots":len(selected),
            "independently_accepted_postgame_labels_in_eligible_slots":accepted_labels,
            "labeled_trainable_slots":len(examples),
            "out_of_roster_verified_labels":unmatched,
            "distinct_game_dates":len(distinct_dates),
            "all_archived_verified_labels":sum(v["effective_status"]==LABEL for v in ledger["slots"].values()),
            "quarantined_labels":sum(v["effective_status"]==DANGER for v in ledger["slots"].values()),
            "skip_reasons":dict(sorted(reasons.items())),
            "postgame_manual_source_review_targets":len(review_targets)},
        "review_targets":review_targets,
        "examples":examples,
        "can_estimate_calibrated_starter_probabilities":False,
        "historical_pbp_publication_authenticated":False,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

def read_archives(archive_root=None):
    # The settlement job checks out context-state AFTER archival writes.
    # Prefer that immutable local Git tree over dozens of rate-limited REST
    # lookups. It is still SHA-checked against every archived index entry.
    root=Path(archive_root) if archive_root is not None else None
    def blob(path):
        if root is None:return store.get_blob_file(path)
        target=root/path
        if not target.is_file():raise ValueError("Missing local archived evidence: "+path)
        return target.read_bytes()
    def read_json(path):
        b=blob(path)
        if b is None:raise ValueError("Missing QB training source "+path)
        return json.loads(b)
    ci=read_json(SHADOW_INDEX);li=read_json(LABEL_INDEX)
    if (ci.get("season")!=2026 or ci.get("status")!=
        "QB_CONDITIONAL_PLAYER_EPA_FROZEN_SHADOW_RESEARCH_ONLY" or
        not isinstance(ci.get("runs"),list)):
        raise ValueError("Untrusted candidate QB forecast index")
    verify_index(li)
    shadows=[]
    for entry in ci["runs"]:
        p=entry["path"]
        if (not re.fullmatch(r"research_2026/candidate_shadow_qb/2026/\d{2}/\d{2}/run-\d+\.json\.gz",p)
            or not p.endswith("/run-"+str(entry["run_id"])+".json.gz")):
            raise ValueError("Unsafe candidate archive path")
        source_blob=blob(p)
        if source_blob is None:raise ValueError("Missing candidate QB archive")
        data=store.unpack(source_blob)
        if checksum(data)!=entry["sha256"]:
            raise ValueError("Altered immutable QB forecast SHA")
        shadows.append(data)
    # Before using a label, authenticate its original immutable source row
    # and archive path rather than trusting an edited index name.
    saved={}
    for e in li["runs"]:
        source_blob=blob(e["path"])
        if source_blob is None:raise ValueError("Missing original QB starter label archive")
        data=store.unpack(source_blob)
        if hashlib.sha256(store.encode(data)).hexdigest()!=e["sha256"]:
            raise ValueError("Tampered postgame QB starter archive")
        key=str(e["run_id"])
        if key!=str(data["run_id"]):raise ValueError("Label archive run changed")
        saved[e["path"]]={
            (str(r["game_id"]),r["team"]):r for r in data["rows"]}
    for k,slot in li["slots"].items():
        for observed in slot["observations"]:
            raw=saved[observed["path"]].get((str(slot["game_id"]),slot["team"]))
            if (raw is None or raw.get("label_status")!=observed["label_status"]
                or raw.get("starter_player")!=observed["starter_player"]
                or raw.get("source_payload_sha256")!=observed["source_payload_sha256"]
                or raw.get("source_url")!=observed["source_url"]):
                raise ValueError("Label index mutated independently of immutable source")
    return shadows,li

def run(output,registry_path,archive_root=None,review_csv=None):
    registry=json.loads(Path(registry_path).read_text(encoding="utf-8"))
    shadows,ledger=read_archives(archive_root)
    report=build(shadows,ledger,registry,dt.datetime.now(dt.timezone.utc).isoformat())
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8") as f:
        json.dump(report,f,indent=2,allow_nan=False);f.write("\n")
    if review_csv is not None:
        target=Path(review_csv);target.parent.mkdir(parents=True,exist_ok=True)
        cols=("game_id","team","opponent","kickoff_utc","reason",
              "postgame_label_status","projected_qb_not_confirmation",
              "frozen_qb_candidate_names","forecast_observed_utc","exact_school_gamebook_url","review_required")
        with target.open("x",encoding="utf-8",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=cols)
            writer.writeheader()
            for row in report["review_targets"]:
                writer.writerow({**{k:row.get(k) for k in cols},
                    "frozen_qb_candidate_names":"; ".join(row["frozen_qb_candidate_names"])})
    print(json.dumps({"status":STATUS,**report["summary"],
        "ready_for_calibrated_starter_training":report["ready_for_calibrated_starter_training"],
        "model_promoted":False}))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--archive-root",default=None)
    p.add_argument("--review-csv",default=None)
    args=p.parse_args()
    run(args.output,args.registry,args.archive_root,args.review_csv)

"""Prospective, non-promoted V03/recency/latent shadow predictions.

Only the real frozen Step3G forecast anchors timing, game identity and total.
Candidate historic features are reconstructed research data, not authenticated
historical as-of PBP. Forecast and model versions are immutable after capture.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import context_archive as store
from scripts.creative_model_features import _advance_latent, _latent_asof, build as creative_build
from scripts.home_bias_candidate import fit_candidate, predict_candidate
from scripts.model_v03 import fit_ridge, group_by_date, predict
from scripts.personnel_features import BASE_FIELDS
from scripts.personnel_forecast import (
    _check_training, _fixed_rows, checksum, t, verify as verify_baseline)
from scripts.personnel_results_archive import ROOT, _commit_material

STATUS="V03_RECENCY_LATENT_PROSPECTIVE_SHADOW_RESEARCH_ONLY"
INDEX=ROOT+"/shadow_forecast_index.json"
LATENT=("latent_strength_diff","latent_uncertainty_sum")
MODELS=("active_v03","recency_14d","latent_only","recency_plus_latent")
VERSIONS={"active_v03":"V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1",
          "recency_14d":"HOME_MARGIN_PRIOR_GAMES_RECENCY14D_CANDIDATE_V1",
          "latent_only":"V03_OPPONENT_LATENT_STATE_CANDIDATE_V1",
          "recency_plus_latent":"RECENCY14D_PLUS_OPPONENT_LATENT_CANDIDATE_V1"}
MIN_LATENT_TRAIN=90
MAX_SHADOW_DELAY_SECONDS=1200

def _eastern_date(instant):
    return t(instant).astimezone(ZoneInfo("America/New_York")).date()

def _clip_margin(margin,total):
    if type(margin) not in (float,int) or not math.isfinite(margin):
        raise ValueError("Nonfinite shadow margin")
    return round(float(max(-min(55.,total),min(min(55.,total),margin))),5)

def _training_hash(rows):
    return checksum([{"game_id":str(r["game_id"]),
        "feature_values":{name:r.get(name) for name in BASE_FIELDS},
        "home_score":r["home_score"],"away_score":r["away_score"]}
        for r in sorted(rows,key=lambda r:str(r["game_id"]))])

def _latent_features(states,home,away,date):
    h=_latent_asof(states,home,date.isoformat())
    a=_latent_asof(states,away,date.isoformat())
    if h is None or a is None or min(h["games"],a["games"])<2:
        return None
    return {"latent_strength_diff":float(h["mean"]-a["mean"]),
            "latent_uncertainty_sum":float(h["variance"]+a["variance"])}

def build_shadow(frozen,games,advanced,training_rows,observed_at_utc):
    verify_baseline(frozen)
    observed=t(observed_at_utc)
    baseline=t(frozen["forecast_observed_utc"])
    if not baseline<=observed or (observed-baseline).total_seconds()>MAX_SHADOW_DELAY_SECONDS:
        raise ValueError("Shadow must be captured promptly after original forecast")
    if frozen["model_training"]["training_game_ids_sha256"]!=checksum(sorted(str(r["game_id"]) for r in training_rows)):
        raise ValueError("Shadow training identities disagree with original")
    if frozen["model_training"]["training_features_sha256"]!=_training_hash(training_rows):
        raise ValueError("Shadow training differs from frozen V03 training data")
    if len(games)!=len(training_rows) or len({str(g["game_id"]) for g in games})!=len(games):
        raise ValueError("Missing, duplicated or reordered training outcome coverage")
    if not frozen["games"]:raise ValueError("No future forecast games")
    future=[g for g in frozen["games"] if t(g["kickoff_utc"])>observed]
    if not future:raise ValueError("Shadow prediction was produced after all kickoffs")
    cutoff=min(_eastern_date(g["kickoff_utc"]) for g in future)
    # Ignore completed same-day games, even if they were known to original V03.
    train=[r for r in training_rows if dt.date.fromisoformat(r["date"])<cutoff]
    latent_all=creative_build(games,advanced)
    if set(str(r["game_id"]) for r in latent_all)!=set(str(g["game_id"]) for g in games):
        raise ValueError("Creative history identity mismatch")
    latent_train=[r for r in latent_all if dt.date.fromisoformat(r["date"])<cutoff]
    pairs={str(r["game_id"]):r for r in latent_train}
    if len(pairs)!=len(latent_train) or set(pairs)!=set(str(r["game_id"]) for r in train):
        raise ValueError("Latent and original pregame training IDs diverge")
    for r in train:
        other=pairs[str(r["game_id"])]
        if (r["home"],r["away"],r["date"],r["home_score"],r["away_score"])!=(
            other["home"],other["away"],other["date"],other["home_score"],other["away_score"]):
            raise ValueError("Latent history source mismatch")
        for f in BASE_FIELDS:
            if r.get(f)!=other.get(f):
                raise ValueError("Reconstructed pregame baseline feature mismatch")
    if len(train)<90:
        raise ValueError("Insufficient date-exclusive original training rows")
    recency_train=[r for r in train if r["home_games_prior"]>=1 and r["away_games_prior"]>=1]
    recency_params=fit_candidate(train,BASE_FIELDS,cutoff) if len(recency_train)>=90 else None
    available_latent=[r for r in latent_train
        if r["home_games_prior"]>=1 and r["away_games_prior"]>=1
        and all(r.get(k) is not None for k in LATENT)]
    latent_params=fit_ridge(available_latent,BASE_FIELDS+LATENT) if len(available_latent)>=MIN_LATENT_TRAIN else None
    combined_params=fit_candidate(available_latent,BASE_FIELDS+LATENT,cutoff) if latent_params else None
    # Identical-training-cohort recency-only control isolates whether latent
    # variables add predictive signal beyond sample-selection differences.
    matched_recency_params=fit_candidate(available_latent,BASE_FIELDS,cutoff) if latent_params else None
    states={}
    for _,group in group_by_date([g for g in games if dt.date.fromisoformat(g["date"])<cutoff]):
        _advance_latent(states,group)
    rows=[]
    for game in future:
        day=_eastern_date(game["kickoff_utc"])
        if day<cutoff:raise ValueError("Earlier game escaped training cutoff")
        feats=game["features"]
        base_proj=game["projection"]
        total=base_proj.get("predicted_total_points")
        if total is not None and (type(total) not in (float,int) or not 0<=total<=110):
            raise ValueError("Untrusted frozen V03 total")
        extra=_latent_features(states,game["home"],game["away"],day)
        source={**{k:feats[k] for k in BASE_FIELDS},**(extra or {k:None for k in LATENT})}
        options={}
        def record(name,value,reason=None):
            options[name]={"version":VERSIONS[name],
                "predicted_home_margin":_clip_margin(value,total) if value is not None and total is not None else None,
                "predicted_total":total if value is not None else None,
                "status":"SHADOW_FROZEN_RESEARCH" if value is not None and total is not None else "PASS",
                "pass_reason":None if value is not None and total is not None else (reason or "NO_BASELINE_PROJECTION")}
        record("active_v03",base_proj["predicted_home_margin"],
               "ORIGINAL_FORECAST_NOT_FITTED")
        recency_margin=(float(predict_candidate([source],BASE_FIELDS,recency_params)[0])
                        if recency_params else None)
        record("recency_14d",recency_margin,"INSUFFICIENT_ELIGIBLE_EARLIER_GAMES")
        if extra is None:
            record("latent_only",None,"MISSING_BOTH_TEAMS_PRIOR_LATENT_STATE")
            record("recency_plus_latent",None,"MISSING_BOTH_TEAMS_PRIOR_LATENT_STATE")
        elif latent_params is None:
            record("latent_only",None,"INSUFFICIENT_PAST_LATENT_TRAINING")
            record("recency_plus_latent",None,"INSUFFICIENT_PAST_LATENT_TRAINING")
        else:
            latent_margin=float(predict([source],BASE_FIELDS+LATENT,latent_params)[0][0,0])
            combined_margin=float(predict_candidate([source],BASE_FIELDS+LATENT,combined_params)[0])
            record("latent_only",latent_margin)
            record("recency_plus_latent",combined_margin)
        control_margin=(float(predict_candidate([source],BASE_FIELDS,matched_recency_params)[0])
                        if extra is not None and matched_recency_params is not None else None)
        control={"version":"RECENCY14D_SAME_LATENT_ELIGIBLE_COHORT_CONTROL_V1",
                 "training_games":len(available_latent),
                 "status":"SHADOW_FROZEN_RESEARCH" if control_margin is not None else "PASS",
                 "predicted_home_margin":_clip_margin(control_margin,total)
                    if control_margin is not None and total is not None else None,
                 "pass_reason":None if control_margin is not None and total is not None
                    else "LATENT_TRAINING_OR_TEAM_HISTORY_INSUFFICIENT"}
        rows.append({"game_id":str(game["game_id"]),"home":game["home"],"away":game["away"],
                     "kickoff_utc":game["kickoff_utc"],"baseline_row_sha256":game["row_sha256"],
                     "lead_hours_at_shadow":round((t(game["kickoff_utc"])-observed).total_seconds()/3600,5),
                     "policy_24_to_72h_eligible":24<=(t(game["kickoff_utc"])-observed).total_seconds()/3600<=72,
                     "latent_evidence_present":extra is not None,
                     "latent_ablation_control":control,
                     "models":options})
    record={"status":STATUS,"season":2026,"run_id":str(frozen["run_id"]),
        "baseline_model":VERSIONS["active_v03"],
        "baseline_forecast_observed_utc":frozen["forecast_observed_utc"],
        "baseline_forecast_sha256":checksum(frozen),
        "shadow_observed_utc":observed.isoformat(),
        "training_date_cutoff_exclusive":cutoff.isoformat(),
        "training_games":len(train),"latent_train_games":len(available_latent),
        "source_training_features_sha256":frozen["model_training"]["training_features_sha256"],
        "model_versions":VERSIONS,
        "historical_pbp_publication_verified":False,
        "market_lines_captured":False,
        "score_totals_modified":False,
        "model_promoted":False,"safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
        "summary":{"games":len(rows),"excluded_kickoffs_since_baseline":len(frozen["games"])-len(rows),
                   "fully_comparable_games":sum(all(r["models"][n]["status"]=="SHADOW_FROZEN_RESEARCH"
                                                       for n in MODELS) for r in rows)},
        "games":rows}
    verify_shadow(record)
    return record

def verify_shadow(record):
    if (record.get("status")!=STATUS or record.get("season")!=2026
        or record.get("betting_status")!="PASS_UNVALIDATED"
        or record.get("safe_for_betting") is not False
        or record.get("model_promoted") is not False
        or record.get("historical_pbp_publication_verified") is not False
        or record.get("score_totals_modified") is not False
        or record.get("model_versions")!=VERSIONS):
        raise ValueError("Untrusted shadow prediction bundle")
    at=t(record["shadow_observed_utc"])
    if t(record["baseline_forecast_observed_utc"])>at or not record.get("games"):
        raise ValueError("Invalid shadow instant")
    seen=set()
    for row in record["games"]:
        gid=str(row["game_id"])
        if gid in seen or t(row["kickoff_utc"])<=at:
            raise ValueError("Duplicate or postkickoff shadow")
        seen.add(gid)
        if set(row["models"])!=set(MODELS) or len(row["baseline_row_sha256"])!=64:
            raise ValueError("Missing model or source identity")
        for name,v in row["models"].items():
            margin=v["predicted_home_margin"];total=v["predicted_total"]
            if v["version"]!=VERSIONS[name]:raise ValueError("Unknown model version")
            if v["status"]=="PASS":
                if margin is not None or total is not None or not v["pass_reason"]:
                    raise ValueError("Invented shadow on missing evidence")
            elif v["status"]=="SHADOW_FROZEN_RESEARCH":
                if (v["pass_reason"] is not None or
                    type(margin) not in (float,int) or type(total) not in (float,int)
                    or not math.isfinite(margin) or not 0<=total<=110 or abs(margin)>min(55,total)):
                    raise ValueError("Invalid shadow prediction")
            else:raise ValueError("Unsupported shadow status")
        ctrl=row.get("latent_ablation_control")
        if ctrl is not None:
            if (ctrl.get("version")!="RECENCY14D_SAME_LATENT_ELIGIBLE_COHORT_CONTROL_V1"
                or ctrl.get("training_games")!=record["latent_train_games"]):
                raise ValueError("Wrong latent matched-cohort control identity")
            if ctrl.get("status")=="PASS":
                if ctrl.get("predicted_home_margin") is not None or not ctrl.get("pass_reason"):
                    raise ValueError("Missing latent evidence was fabricated")
            elif ctrl.get("status")=="SHADOW_FROZEN_RESEARCH":
                m=ctrl.get("predicted_home_margin")
                if (not row["latent_evidence_present"] or
                    row["models"]["recency_plus_latent"]["status"]!="SHADOW_FROZEN_RESEARCH" or
                    type(m) not in (float,int) or not math.isfinite(m) or
                    abs(m)>min(55,row["models"]["active_v03"]["predicted_total"])):
                    raise ValueError("Invalid matched latent control")
            else:raise ValueError("Unsupported matched-cohort control")
        base_total=row["models"]["active_v03"]["predicted_total"]
        if any(v["predicted_total"] not in (None,base_total) for v in row["models"].values()):
            raise ValueError("Shadow prediction changed totals")
    if record["summary"]["games"]!=len(record["games"]):
        raise ValueError("Shadow count mismatch")
    return True

def archive(shadow):
    verify_shadow(shadow)
    if not str(shadow["run_id"]).isdigit() or shadow["run_id"]!=str(os.getenv("GITHUB_RUN_ID","")):
        raise ValueError("Shadow can only be archived by producing GitHub run")
    now=dt.datetime.now(dt.timezone.utc)
    if not 0<=(now-t(shadow["shadow_observed_utc"])).total_seconds()<1200:
        raise ValueError("Shadow archive missed live observation window")
    date=t(shadow["shadow_observed_utc"]).strftime("%Y/%m/%d")
    path=ROOT+"/shadow_forecasts/"+date+"/run-"+shadow["run_id"]+".json.gz"
    packed=store.pack(shadow)
    previous=store.get_blob_file(path)
    if previous is not None:
        if previous!=packed:raise ValueError("Immutable shadow archive conflict")
        return {"status":"ALREADY_ARCHIVED","path":path}
    old=store.get_blob_file(INDEX)
    index=json.loads(old) if old else {"status":STATUS,"season":2026,"runs":[],
                                         "betting_status":"PASS_UNVALIDATED"}
    if index.get("status")!=STATUS or index.get("season")!=2026:
        raise ValueError("Invalid shadow forecast index")
    if any(str(x["run_id"])==shadow["run_id"] for x in index["runs"]):
        raise ValueError("Duplicate archived shadow run")
    index["runs"].append({"run_id":shadow["run_id"],"path":path,
        "shadow_observed_utc":shadow["shadow_observed_utc"],
        "sha256":checksum(shadow),"baseline_forecast_sha256":shadow["baseline_forecast_sha256"],
        "games":len(shadow["games"])})
    index["runs"].sort(key=lambda x:x["shadow_observed_utc"])
    commit=_commit_material({path:packed,INDEX:store.encode(index)},shadow["run_id"])
    return {"status":"ARCHIVED_FROZEN_SHADOW","path":path,"commit_sha":commit}

def run(forecast_path,games_path,advanced_path,adv_manifest,score_manifest,output):
    frozen=json.loads(Path(forecast_path).read_text())["record"]
    games,advanced,_,_=_check_training(games_path,advanced_path,adv_manifest,
                                       score_manifest,{"captured_at_utc":frozen["source_profile_capture_utc"]})
    training=_fixed_rows(games,advanced,t(frozen["source_profile_capture_utc"]))
    shadow=build_shadow(frozen,games,advanced,training,dt.datetime.now(dt.timezone.utc).isoformat())
    archived=archive(shadow)
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf-8") as handle:
        json.dump({"record":shadow,"archive":archived},handle,indent=2,allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status":STATUS,"games":len(shadow["games"]),
                      "fully_comparable":shadow["summary"]["fully_comparable_games"],
                      "archive":archived["status"],"model_promoted":False}))
    return shadow

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for flag in ("forecast","games","advanced","advanced-manifest","score-manifest","output"):
        p.add_argument("--"+flag,required=True)
    a=p.parse_args()
    run(a.forecast,a.games,a.advanced,a.advanced_manifest,a.score_manifest,a.output)

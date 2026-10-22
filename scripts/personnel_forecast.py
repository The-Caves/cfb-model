"""v0.4 Step 3G: real *prospective research* projections, no bets or synthetic odds.

The model is trained on actual completed 2026 games. All coefficients and
features are frozen before kickoff, using the same 14-feature score/advanced
schema as the captured profiles. Historical advanced feeds are retrospectively
mutable: no calibration or independent historical publication proof is claimed.
Actual sportsbook quotes remain in the existing opt-in PRIVATE market vault.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path

from scripts.game_context import parse_time
from scripts.model_v03 import build_weekly_games, fit_ridge, load_inputs, predict
from scripts.personnel_features import BASE_FIELDS, verify_joined, sha256
from scripts.personnel_results_archive import ROOT, _commit_material
from scripts import context_archive as store
from scripts.weekly_profiles import canonical

STATUS="STEP3G_PROSPECTIVE_RESEARCH_PROJECTIONS"
INDEX=ROOT+"/forecast_index.json"
MAX_SOURCE_AGE_MINUTES=45
MIN_TRAIN=90
MODEL="V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1"
MARKET_ABSENT="NOT_OBSERVED_PRIVATE_OPT_IN_ONLY"


def t(value):
    return parse_time(value)


def checksum(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _check_training(games_csv,advanced_csv,advanced_manifest,score_manifest,cap):
    manifest=json.loads(Path(score_manifest).read_text())
    adv=json.loads(Path(advanced_manifest).read_text())
    cutoff=t(cap["captured_at_utc"])
    if (manifest.get("status")!="SUCCESS" or manifest.get("failures") or
        manifest.get("requested_start")!="2026-08-01" or
        manifest.get("scoreboard_date_timezone")!="America/New_York" or
        adv.get("season")!=2026 or
        adv.get("historical_pregame_availability_verified") is not False or
        not str(adv.get("status","")).startswith("RESEARCH_PBP_IMPORTED")):
        raise ValueError("Unverified 2026 scoreboard/advanced source")
    for item in (manifest["retrieved_at_utc"],adv["retrieved_at_utc"]):
        if t(item)>cutoff:
            raise ValueError("Training sources were not available at profile capture")
    games,advanced,parsed=load_inputs(games_csv,advanced_csv,advanced_manifest)
    for game in games:
        if t(game["kickoff_utc"])>=cutoff:
            raise ValueError("Future or uncompleted game in model-training records")
    return games,advanced,manifest,adv


def _fixed_rows(games,advanced,cutoff):
    rows=build_weekly_games(games,advanced)
    accepted=[r for r in rows if t(r["kickoff_utc"])<cutoff and
              r["betting_status"]=="PASS_UNVALIDATED"]
    if len(accepted)!=len(rows):
        raise ValueError("Non-chronological research training input")
    return accepted


def _round(x):
    return round(float(x),5)


def project(joined,training_rows,forecasted_at_utc,model_source):
    """Pure research prediction. Model metadata retained for future audit."""
    verify_joined(joined)
    decision=t(forecasted_at_utc)
    capture=t(joined["captured_at_utc"])
    if not capture<=decision or (decision-capture).total_seconds()>MAX_SOURCE_AGE_MINUTES*60:
        raise ValueError("Stale/future source capture at projection instant")
    if joined.get("season")!=2026 or joined.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Wrong season or clearance")
    if not training_rows:
        raise ValueError("No actual 2026 completed games to fit")
    seen=set()
    for r in training_rows:
        gid=str(r["game_id"])
        if gid in seen or t(r["kickoff_utc"])>=capture or (
            r.get("betting_status")!="PASS_UNVALIDATED"):
            raise ValueError("Duplicated, untrusted or future training outcome")
        seen.add(gid)
        if not isinstance(r.get("home_score"),int) or not isinstance(r.get("away_score"),int):
            raise ValueError("Malformed actual training final")
    ids=sorted(seen)
    count=len(ids)
    params=fit_ridge(training_rows,BASE_FIELDS) if count>=MIN_TRAIN else None
    fit_description={
        "model":MODEL,"min_training_games":MIN_TRAIN,
        "actual_2026_training_games":count,
        "training_game_ids_sha256":checksum(ids),
        "training_features_sha256":checksum([{
            "game_id":str(r["game_id"]),
            "feature_values":{name:r.get(name) for name in BASE_FIELDS},
            "home_score":r["home_score"],"away_score":r["away_score"]}
            for r in sorted(training_rows,key=lambda r:str(r["game_id"]))]),
        "source_hashes":model_source,
        "train_cutoff_utc":capture.isoformat(),
        "feature_schema":list(BASE_FIELDS),
        "model_fitted":bool(params),
        "fitted_parameters_sha256":checksum({
            "coefficient_matrix":params[0].tolist(),
            "train_imputation_means":params[1].tolist(),
            "train_normalization_stds":params[2].tolist(),
            "residual_sigma":params[3]}) if params else None,
        "historical_advanced_publication_verified":False,
        "probability_calibrated":False,
        "betting_status":"PASS_UNVALIDATED"}
    result=[]
    for g in joined["games"]:
        kickoff=t(g["kickoff_utc"])
        if kickoff<=decision:
            # An already-started game is neither a pregame prediction nor
            # eligible for the prospective ledger.
            continue
        lead=(kickoff-capture).total_seconds()/3600
        if params:
            predicted,sigma=predict([g["features"]],BASE_FIELDS,params)
            total=max(0.,min(110.,float(predicted[0,1])))
            # A split score cannot be negative even for an extreme fixture.
            margin=max(-min(55.,total),min(min(55.,total),float(predicted[0,0])))
            prob=0.5*(1+math.erf(margin/(sigma*math.sqrt(2))))
            projection={
                "predicted_home_margin":_round(margin),
                "predicted_total_points":_round(total),
                "research_home_win_probability":_round(prob),
                "predicted_home_points":_round((total+margin)/2),
                "predicted_away_points":_round((total-margin)/2),
                "uncertainty_sigma_margin":_round(sigma),
                "probability_calibrated":False,
                "method":"ACTUAL_FITTED_2026_RIDGE_RESEARCH_ONLY",
                "prediction_status":"UNVALIDATED_RESEARCH_PROJECTION"}
        else:
            projection={
                "predicted_home_margin":None,
                "predicted_total_points":None,
                "research_home_win_probability":None,
                "predicted_home_points":None,
                "predicted_away_points":None,
                "uncertainty_sigma_margin":None,
                "probability_calibrated":False,
                "method":"INSUFFICIENT_PRIOR_COMPLETED_TRAINING",
                "prediction_status":"PASS_INSUFFICIENT_TRAINING"}
        row={
            "game_id":str(g["game_id"]),"home":g["home"],"away":g["away"],
            "kickoff_utc":g["kickoff_utc"],
            "profile_captured_utc":joined["captured_at_utc"],
            "forecast_observed_utc":decision.isoformat(),
            "lead_hours_at_capture":_round(lead),
            "policy_24_to_72h_eligible":24<=lead<=72,
            "feature_sha256":g["record_sha256"],
            "personnel_profile_sha256":g["profile_sha256"],
            "features":g["features"],
            "reported_qb_coverage":sum(s["qb_reviewed"] for s in g["personnel_by_side"].values()),
            "verified_team_report_coverage":sum(s["report_verified"] for s in g["personnel_by_side"].values()),
            "market":{"status":MARKET_ABSENT,"actual_quote_count":0,
                      "source_snapshot_sha256":None,
                      "observed_spread":None,"observed_total":None,
                      "observed_moneyline":None,
                      "market_provider_paid_api_called":False,
                      "unverified_open_or_close":True},
            "projection":projection,
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
        row["row_sha256"]=checksum(row)
        result.append(row)
    if not result:
        raise ValueError("No remaining pregame games for prospective forecasts")
    if len({r["game_id"] for r in result})!=len(result):
        raise ValueError("Duplicate forecast game")
    record={
        "status":STATUS,"season":2026,"run_id":str(joined["run_id"]),
        "forecast_observed_utc":decision.isoformat(),
        "source_profile_capture_utc":joined["captured_at_utc"],
        "joined_profile_sha256":sha256(joined),
        "model_training":fit_description,
        "games":result,
        "summary":{
            "frozen_pregame_games":len(result),
            "eligible_24_to_72h_games":sum(x["policy_24_to_72h_eligible"] for x in result),
            "research_numeric_projections":sum(x["projection"]["predicted_home_margin"] is not None for x in result),
            "unavailable_market_quotes":len(result),
            "market_prices_written_publicly":0,
            "model_validation_passed":False},
        "market_data_privacy":"PRIVATE_OPT_IN_EXISTING_VAULT_NOT_EXPORTED",
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}
    verify(record)
    return record


def verify(record):
    if (record.get("status")!=STATUS or record.get("season")!=2026 or
        record.get("safe_for_betting") is not False or
        record.get("model_promoted") is not False or
        record.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Invalid frozen projection provenance")
    observed=t(record["forecast_observed_utc"])
    cap=t(record["source_profile_capture_utc"])
    if not cap<=observed or (observed-cap).total_seconds()>MAX_SOURCE_AGE_MINUTES*60:
        raise ValueError("Projection was not produced from live pregame source")
    model=record["model_training"]
    if model.get("model")!=MODEL or model.get("probability_calibrated") is not False or (
        model.get("historical_advanced_publication_verified") is not False or
        model.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Unsupported projection model identity")
    n=model["actual_2026_training_games"]
    if type(n) is not int or n<0 or model["model_fitted"]!=(n>=MIN_TRAIN):
        raise ValueError("Training sample or status invalid")
    if not record.get("games"):
        raise ValueError("Empty prospective forecast")
    ids=set()
    for row in record["games"]:
        gid=str(row["game_id"])
        if gid in ids:
            raise ValueError("Duplicate ESPN forecast")
        ids.add(gid)
        kickoff=t(row["kickoff_utc"])
        lead=(kickoff-cap).total_seconds()/3600
        if (kickoff<=observed or t(row["profile_captured_utc"])!=cap or
            t(row["forecast_observed_utc"])!=observed or
            abs(row["lead_hours_at_capture"]-lead)>1e-4 or
            row["policy_24_to_72h_eligible"]!=(24<=lead<=72)):
            raise ValueError("Forecast past kickoff, invalid time or lead")
        if (row["safe_for_betting"] is not False or
            row["betting_status"]!="PASS_UNVALIDATED" or
            set(row["features"])!=set(BASE_FIELDS+(
                "home_qb_reviewed","away_qb_reviewed","home_report_verified",
                "away_report_verified","availability_out_diff",
                "availability_questionable_diff","availability_limited_diff",
                "availability_qb_out_diff"))):
            raise ValueError("Invalid research feature or clearance")
        for k,v in row["features"].items():
            if v is not None and (type(v) not in (int,float) or not math.isfinite(v)):
                raise ValueError("Invalid frozen research feature")
        q=row["market"]
        if (q.get("status")!=MARKET_ABSENT or q.get("actual_quote_count")!=0
            or q.get("market_provider_paid_api_called") is not False
            or any(q.get(k) is not None for k in (
                "observed_spread","observed_total","observed_moneyline","source_snapshot_sha256"))):
            raise ValueError("Unobserved market quotes must be absent")
        projection=row["projection"]
        if projection.get("probability_calibrated") is not False:
            raise ValueError("Uncalibrated research probability falsely certified")
        if model["model_fitted"]:
            if projection.get("prediction_status")!="UNVALIDATED_RESEARCH_PROJECTION":
                raise ValueError("Frozen model missing research forecast")
            for field in ("predicted_home_margin","predicted_total_points",
                          "research_home_win_probability","uncertainty_sigma_margin"):
                value=projection.get(field)
                if type(value) not in (float,int) or not math.isfinite(value):
                    raise ValueError("Non-finite model output")
            if not 0<=projection["research_home_win_probability"]<=1:
                raise ValueError("Invalid probability")
            if any(projection.get(f) is None or projection[f]<0
                   for f in ("predicted_home_points","predicted_away_points")):
                raise ValueError("Negative or unknown implied final score")
        elif projection.get("prediction_status")!="PASS_INSUFFICIENT_TRAINING" or any(
            projection.get(k) is not None for k in ("predicted_home_margin",
                "predicted_total_points","research_home_win_probability")):
            raise ValueError("Invented prediction below training minimum")
        raw=dict(row)
        sig=raw.pop("row_sha256",None)
        if sig!=checksum(raw):
            raise ValueError("Frozen pregame forecast checksum mismatch")
    if record["summary"]!={
        "frozen_pregame_games":len(record["games"]),
        "eligible_24_to_72h_games":sum(x["policy_24_to_72h_eligible"] for x in record["games"]),
        "research_numeric_projections":sum(x["projection"]["predicted_home_margin"] is not None for x in record["games"]),
        "unavailable_market_quotes":len(record["games"]),
        "market_prices_written_publicly":0,
        "model_validation_passed":False}:
        raise ValueError("Invalid prediction ledger summary")
    return True


def archive(record):
    verify(record)
    if (not str(record["run_id"]).isdigit() or
        str(record["run_id"])!=str(os.environ.get("GITHUB_RUN_ID","")) or
        store.branch_head() is None):
        raise ValueError("GitHub run/branch required for research archive")
    captured=t(record["forecast_observed_utc"])
    if not 0<=(dt.datetime.now(dt.timezone.utc)-captured).total_seconds()<=1200:
        raise ValueError("Cannot retroactively claim a live archived forecast")
    path=(ROOT+"/forecasts/"+captured.strftime("%Y/%m/%d")+
          "/run-"+record["run_id"]+".json.gz")
    old=store.get_blob_file(path)
    packed=store.pack(record)
    if old is not None:
        if old != packed:
            raise ValueError("Refusing rewritten prospective forecast")
        return {"status":"ALREADY_ARCHIVED_EXACT_BYTES","path":path,
                "forecast_sha256":checksum(record)}
    ledger_path=ROOT+"/forecast_index.json"
    raw=store.get_blob_file(ledger_path)
    index=json.loads(raw) if raw else {"status":STATUS,"season":2026,"runs":[],
                                          "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    if index.get("status")!=STATUS or index.get("season")!=2026 or (
        index.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Invalid research forecast index")
    if any(entry["run_id"]==record["run_id"] for entry in index["runs"]):
        raise ValueError("Conflicting run ID across forecast archives")
    index["runs"].append({
        "run_id":record["run_id"],"path":path,
        "forecast_observed_utc":record["forecast_observed_utc"],
        "forecast_sha256":checksum(record),
        "pregame_games":len(record["games"]),
        "eligible_24_to_72h_games":record["summary"]["eligible_24_to_72h_games"],
        "actual_market_quotes":0})
    index["runs"].sort(key=lambda x:x["forecast_observed_utc"])
    sha=_commit_material({
        path:store.pack(record),
        ledger_path:store.encode(index)},record["run_id"])
    return {"status":"ARCHIVED_FROZEN_UNVALIDATED_RESEARCH",
            "path":path,"forecast_sha256":checksum(record),"git_commit":sha,
            "market_quotes_published":0}


def run(joined_file,games_file,advanced_file,advanced_manifest,score_manifest,out):
    joined=json.loads(Path(joined_file).read_text())
    cutoff=t(joined["captured_at_utc"])
    games,advanced,sm,am=_check_training(
        games_file,advanced_file,advanced_manifest,score_manifest,joined)
    rows=_fixed_rows(games,advanced,cutoff)
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    source={
        "scoreboard_manifest_sha256":hashlib.sha256(Path(score_manifest).read_bytes()).hexdigest(),
        "advanced_manifest_sha256":hashlib.sha256(Path(advanced_manifest).read_bytes()).hexdigest(),
        "completed_score_csv_sha256":hashlib.sha256(Path(games_file).read_bytes()).hexdigest(),
        "advanced_game_csv_sha256":hashlib.sha256(Path(advanced_file).read_bytes()).hexdigest(),
        "first_observation_of_sources":"CURRENT_GITHUB_RUN_RESEARCH_ONLY",
        "historical_pbp_publication_verified":False}
    record=project(joined,rows,now,source)
    details=archive(record)
    path=Path(out)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as stream:
        json.dump({"record":record,"archive":details},stream,indent=2,allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status":record["status"],"games":len(record["games"]),
                     "numeric_projections":record["summary"]["research_numeric_projections"],
                     "eligible":record["summary"]["eligible_24_to_72h_games"],
                     "observed_market_quotes":0,
                     "archive":details["status"],
                     "betting_status":"PASS_UNVALIDATED"}))
    return record


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--joined",required=True)
    p.add_argument("--games",required=True)
    p.add_argument("--advanced",required=True)
    p.add_argument("--advanced-manifest",required=True)
    p.add_argument("--score-manifest",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.joined,a.games,a.advanced,a.advanced_manifest,
        a.score_manifest,a.output)

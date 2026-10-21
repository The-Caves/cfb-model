"""Synthetic-safe evaluation mechanics for market-referenced probability forecasts.

A forecast must exist BEFORE the decision cutoff, declare its training cutoff,
and belong to an explicit held-out chronological fold. This script does not
fit models, verify training provenance, estimate profit, or issue picks.
"""
import math
from collections import Counter
from scripts.game_context import parse_time
from scripts.market_features import raw_implied
from scripts.market_walkforward import build_folds

def binary_metrics(observations):
    if not observations:
        return None
    model_brier=market_brier=model_log=market_log=0.0
    n=len(observations)
    for realized,probability,baseline in observations:
        clipped=max(1e-7,min(1-1e-7,probability))
        b=max(1e-7,min(1-1e-7,baseline))
        model_brier+=(probability-realized)**2
        market_brier+=(baseline-realized)**2
        model_log-=realized*math.log(clipped)+(1-realized)*math.log(1-clipped)
        market_log-=realized*math.log(b)+(1-realized)*math.log(1-b)
    return {"graded_nonpush_selections":n,
            "model_brier":round(model_brier/n,6),
            "market_baseline_brier":round(market_brier/n,6),
            "model_log_loss":round(model_log/n,6),
            "market_baseline_log_loss":round(market_log/n,6),
            "model_outperformed_market_brier_in_this_sample":
                model_brier<market_brier,
            "statistical_significance_established":False}

def evaluate_folds(features,labels,forecasts,fold_metadata):
    """Outcomes are joined only after a chronological split has been fixed."""
    if fold_metadata.get("status")!="WALK_FORWARD_SPLITS_ONLY":
        raise ValueError("Only vetted chronological splits accepted")
    if fold_metadata.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Cannot evaluate an unrecognized clearance state")
    rows={row["row_id"]:row for row in features}
    if len(rows)!=len(features):raise ValueError("Duplicate feature IDs")
    outcomes={row["row_id"]:row for row in labels}
    if len(outcomes)!=len(labels):raise ValueError("Duplicate label IDs")
    predictions={}
    for row in forecasts:
        rid=row["row_id"]
        if rid in predictions:raise ValueError("Duplicate probability forecast")
        p=row.get("selection_win_probability")
        if type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1:
            raise ValueError("Probability must be finite within [0,1]")
        if rid not in rows:raise ValueError("Forecast without pregame features")
        if not row.get("model_version"):
            raise ValueError("Model version is required for reproducibility")
        if parse_time(row["issued_at_utc"])>parse_time(rows[rid]["decision_asof_utc"]):
            raise ValueError("Forecast issued after decision cutoff")
        predictions[rid]=row
    pairs={}
    for row in features:
        key=(row["espn_game_id"],row["bookmaker"],row["market"],
             row["decision_asof_utc"])
        pairs.setdefault(key,{})[row["selection"]]=row
    used_test=set()
    reports=[]
    for fold in fold_metadata["folds"]:
        start=parse_time(fold["training_cutoff_utc"])
        report_counts=Counter()
        observations=[]
        bymarket={}
        for rid in fold["test_labeled_row_ids"]:
            if rid in used_test:raise ValueError("Test selection reused across folds")
            used_test.add(rid)
            feature=rows.get(rid)
            label=outcomes.get(rid)
            forecast=predictions.get(rid)
            if feature is None or label is None:
                raise ValueError("Fold references unavailable feature or label")
            if parse_time(label["outcome_known_at_utc"])>parse_time(fold["evaluation_asof_utc"]):
                raise ValueError("Label leaked from after fold evaluation cutoff")
            if forecast is None:
                report_counts["missing_model_probability"]+=1
                continue
            if parse_time(forecast["training_data_cutoff_utc"])>start:
                raise ValueError("Model trained on data after this fold's training cutoff")
            result=label["settlement"]
            if result=="PUSH":
                report_counts["push_excluded_from_binary_score"]+=1
                continue
            if result not in ("WIN","LOSS"):
                raise ValueError("Unrecognized evaluation settlement")
            key=(feature["espn_game_id"],feature["bookmaker"],feature["market"],
                 feature["decision_asof_utc"])
            two_sides=pairs.get(key,{})
            expected={"OVER","UNDER"} if feature["market"]=="TOTAL" else {"HOME","AWAY"}
            if set(two_sides)!=expected:
                report_counts["missing_opposing_market_price"]+=1
                continue
            if len({v["market_source_sha256"] for v in two_sides.values()})!=1 or (
                len({v["market_observed_at_utc"] for v in two_sides.values()})!=1):
                report_counts["opposing_price_from_different_snapshot"]+=1
                continue
            raw={side:raw_implied(row["american_odds"])
                 for side,row in two_sides.items()}
            baseline=raw[feature["selection"]]/sum(raw.values())
            truth=1 if result=="WIN" else 0
            record=(truth,forecast["selection_win_probability"],baseline)
            observations.append(record)
            bymarket.setdefault(feature["market"],[]).append(record)
        reports.append({
            "training_cutoff_utc":fold["training_cutoff_utc"],
            "test_end_exclusive_utc":fold["test_end_exclusive_utc"],
            "metric_status":"SYNTHETIC_OR_UNVERIFIED_FORECAST_DIAGNOSTICS_ONLY",
            "overall":binary_metrics(observations),
            "by_market":{m:binary_metrics(v) for m,v in sorted(bymarket.items())},
            "qa":dict(report_counts),
            "actual_model_training_audited":False,
            "valid_betting_recommendations":False
        })
    return {"status":"METRIC_PIPELINE_RESEARCH_ONLY",
            "fold_metrics":reports,
            "model_validated":False,
            "safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED"}

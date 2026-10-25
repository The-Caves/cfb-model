"""Isolated 2026 home-margin bias candidate; NOT the live prediction model.

Training excludes games where either team lacked an earlier-2026 game profile.
The candidate adds exponential, *past-only* recency weights (14-day half-life).
Outcomes are used only as labels from games strictly earlier than each fold.
Historical play-by-play availability is NOT authenticated: research only.
No market odds and no player injury penalties are used here.
"""
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path

import numpy as np
from scripts.model_v03 import fit_ridge, matrix, predict
from scripts.personnel_features import BASE_FIELDS

MODEL="HOME_MARGIN_PRIOR_GAMES_RECENCY14D_CANDIDATE_V1"
BASELINE="V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1"
STATUS="RETROSPECTIVE_RESEARCH_ONLY"
HALF_LIFE_DAYS=14
MIN_TRAIN=90


def eligible(row):
    return (int(row["home_games_prior"])>=1 and
            int(row["away_games_prior"])>=1)


def date_of(row):
    return dt.date.fromisoformat(row["date"])


def fit_candidate(train, fields, first_day, half_life_days=HALF_LIFE_DAYS,
                  penalty=45.0):
    """Fit only prior and dual-profile 2026 games; center weights at mean 1.

    The weighted intercept is NOT an added arbitrary home-field point value:
    it is learned from observed prior training labels at each fold.
    """
    cutoff=dt.date.fromisoformat(first_day) if isinstance(first_day,str) else first_day
    if not isinstance(cutoff,dt.date) or half_life_days<=0:
        raise ValueError("Invalid temporal training cutoff/half-life")
    accepted=[]
    ids=set()
    for row in train:
        key=str(row["game_id"])
        if key in ids:
            raise ValueError("Duplicate historical game")
        ids.add(key)
        if date_of(row)>=cutoff:
            raise ValueError("Same-day/future result in candidate training")
        if eligible(row):
            accepted.append(row)
    if len(accepted)<MIN_TRAIN:
        raise ValueError("Not enough established-prior games to fit")
    X,means,stds=matrix(accepted,fields)
    X=np.column_stack([np.ones(len(accepted)),X])
    y=np.array([float(r["home_score"])-float(r["away_score"]) for r in accepted])
    if not np.isfinite(y).all():
        raise ValueError("Nonfinite training outcomes")
    ages=np.array([(cutoff-date_of(r)).days for r in accepted],dtype=float)
    if (ages<=0).any():
        raise ValueError("Future candidate training source")
    weights=np.exp2(-ages/half_life_days)
    weights/=weights.mean()
    penalty_mat=np.eye(X.shape[1])*penalty
    penalty_mat[0,0]=0
    beta=np.linalg.solve(X.T@(weights[:,None]*X)+penalty_mat,
                         X.T@(weights*y))
    residual=y-X@beta
    sigma=float(max(7.,np.sqrt(np.average(residual**2,weights=weights))))
    return beta,means,stds,sigma


def predict_candidate(rows,fields,params):
    beta,means,stds,sigma=params
    X,_,_=matrix(rows,fields,means,stds)
    X=np.column_stack([np.ones(len(rows)),X])
    return X@beta


def load_combined(features_path,labels_path):
    with open(features_path,newline="",encoding="utf-8") as f:
        features=list(csv.DictReader(f))
    with open(labels_path,newline="",encoding="utf-8") as f:
        labels=list(csv.DictReader(f))
    if not features or len(features)!=len(labels):
        raise ValueError("Historical games/features must be paired")
    if {"home_score","away_score"} & set(features[0]):
        raise ValueError("Outcome leaked into pregame feature table")
    if len({r["game_id"] for r in features})!=len(features):
        raise ValueError("Duplicate feature IDs")
    index={r["game_id"]:r for r in labels}
    if len(index)!=len(labels) or set(index)!={r["game_id"] for r in features}:
        raise ValueError("Labels must match feature IDs exactly")
    result=[]
    for row in features:
        lab=index[row["game_id"]]
        if (row["kickoff_utc"]!=lab["kickoff_utc"] or
            row["date"]!=lab["date"] or
            row["betting_status"]!="PASS_UNVALIDATED" or
            row["feature_evidence_status"]!="RETROSPECTIVE_NOT_PUBLICATION_VERIFIED" or
            date_of(row).year!=2026):
            raise ValueError("Unmatched/retimed or nonresearch football game")
        merged=dict(row)
        # CSV writers represent absent numeric profiles as empty strings.
        # Preserve UNKNOWN as None: never manufacture zeros for week-zero EPA.
        for field in BASE_FIELDS:
            value=merged.get(field)
            if value in ("",None):
                merged[field]=None
            else:
                number=float(value)
                if not math.isfinite(number):
                    raise ValueError("Invalid numeric profile field")
                merged[field]=number
        merged["home_score"]=int(lab["home_score"])
        merged["away_score"]=int(lab["away_score"])
        result.append(merged)
    return result


def _stats(test,values):
    actual=np.array([g["home_score"]-g["away_score"] for g in test])
    predicted=np.asarray(values,dtype=float)
    if not np.isfinite(predicted).all():
        raise ValueError("Nonfinite prediction")
    n=len(test)
    return {"games":n,
        "margin_mae":round(float(np.mean(abs(predicted-actual))),4),
        "signed_home_margin_bias":round(float(np.mean(predicted-actual)),4),
        "su_correct":int(np.sum((predicted>0)==(actual>0))),
        "su_accuracy":round(float(np.mean((predicted>0)==(actual>0))),4),
        "predicted_home_winners":int(np.sum(predicted>0)),
        "home_prediction_fraction":round(float(np.mean(predicted>0)),4)}


def validate(rows, start="2026-09-26", weeks=4):
    """Three ablation cohorts, identical eligible test rows in every fold.

    Original baseline trains on ALL prior games (matches live model).
    Eligibility ablation trains on dual-prior-only games.
    Candidate additionally weights that same training sample toward recent
    dates. Test outcomes never enter a preceding fold's fit.
    """
    first=dt.date.fromisoformat(start)
    results=[]
    for i in range(weeks):
        cutoff=first+dt.timedelta(days=7*i)
        end=cutoff+dt.timedelta(days=7)
        prior=[r for r in rows if date_of(r)<cutoff]
        usable=[r for r in prior if eligible(r)]
        test=[r for r in rows if cutoff<=date_of(r)<end and eligible(r)]
        if len(usable)<MIN_TRAIN or not test:continue
        baseline=fit_ridge(prior,BASE_FIELDS)
        ablation=fit_ridge(usable,BASE_FIELDS)
        candidate=fit_candidate(prior,BASE_FIELDS,cutoff)
        predicted={
            "active_all_training_games":predict(test,BASE_FIELDS,baseline)[0][:,0],
            "dual_prior_training_only":predict(test,BASE_FIELDS,ablation)[0][:,0],
            "dual_prior_recency14d":predict_candidate(test,BASE_FIELDS,candidate)}
        fold={"train_before":cutoff.isoformat(),"test_end_exclusive":end.isoformat(),
              "all_training_games":len(prior),"eligible_training_games":len(usable),
              "test_games":len(test),
              "train_game_ids_sorted":[str(r["game_id"]) for r in prior],
              "test_game_ids_sorted":[str(r["game_id"]) for r in test],
              "model_comparison":{name:_stats(test,p) for name,p in predicted.items()},
              "candidate_fitted_intercept":round(float(candidate[0][0]),5)}
        results.append(fold)
    if not results:raise ValueError("No valid historical research folds")
    aggregate={}
    for key in ("active_all_training_games","dual_prior_training_only","dual_prior_recency14d"):
        weights=np.array([f["model_comparison"][key]["games"] for f in results],dtype=float)
        aggregate[key]={
            "games":int(np.sum(weights)),
            "margin_mae":round(float(np.average([f["model_comparison"][key]["margin_mae"] for f in results],weights=weights)),4),
            "signed_home_margin_bias":round(float(np.average([f["model_comparison"][key]["signed_home_margin_bias"] for f in results],weights=weights)),4),
            "su_correct":sum(f["model_comparison"][key]["su_correct"] for f in results),
            "predicted_home_winners":sum(f["model_comparison"][key]["predicted_home_winners"] for f in results)}
        aggregate[key]["su_accuracy"]=round(aggregate[key]["su_correct"]/aggregate[key]["games"],4)
        aggregate[key]["home_prediction_fraction"]=round(aggregate[key]["predicted_home_winners"]/aggregate[key]["games"],4)
    # IDs intentionally included within each fold for audit, never outputs
    # from a future test round in a previously frozen training set.
    return {"status":STATUS,"betting_status":"PASS_UNVALIDATED",
        "candidate_version":MODEL,"active_model":BASELINE,
        "forecast_promotion":False,"historical_feature_publication_verified":False,
        "settings":{"training_prior_games_each_side":1,"recency_half_life_days":HALF_LIFE_DAYS,
                    "ridge_penalty":45.0,"margin_only":True},
        "notes":["This is a chronological replay on retrospectively retrieved PBP, not attested historical pregame input.",
                 "Prediction totals remain from existing model, NOT improved by this margin-only candidate.",
                 "No wager-grade ATS/O-U validation. Score labels were never inserted into pregame features.",
                 "Exploratory evaluation; the October 24 audit influenced candidate design. Independent prospective validation remains required."],
        "folds":results,"aggregate":aggregate}


def run(features,labels,output):
    report=validate(load_combined(features,labels))
    path=Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"candidate":MODEL,"folds":len(report["folds"]),
        "aggregate":report["aggregate"],"betting_status":report["betting_status"]}))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--features",required=True)
    parser.add_argument("--labels",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    run(args.features,args.labels,args.output)

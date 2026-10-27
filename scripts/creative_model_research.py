"""Preregistered research comparisons for creative CFB prediction ideas.

All labels belong to completed 2026 games. Test games are never used to fit,
choose model weights, or calibrate predictive ranges. Available advanced PBP
is retrospectively mutable and lacks authenticated historical release times:
this is chronological *exploratory* research, NOT leakage-certified betting.
No player injury effect, turnovers, true drive starts, or public market wins
are asserted unless separately verified. Frozen V03 picks are not changed.
"""
import argparse
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from scripts.creative_model_features import GROUPS, build
from scripts.home_bias_candidate import fit_candidate, predict_candidate
from scripts.model_v03 import fit_ridge, load_inputs, predict
from scripts.personnel_features import BASE_FIELDS

STATUS = "CREATIVE_ENSEMBLE_CHRONOLOGICAL_RESEARCH_ONLY"
VERSION = "CREATIVE_CFB_CANDIDATE_2026_V1"
MIN_TRAIN = 90
WEEK_DAYS = 7
# Fixed before seeing 2026 holdout results. Never optimize weights on test.
ENSEMBLE_WEIGHTS = {"active_v03": .35, "home_recency": .25,
                    "all_creative": .20, "possession_mechanistic": .20}
VARIANTS = {
    "active_v03": tuple(BASE_FIELDS),
    "possession_context": tuple(BASE_FIELDS) + GROUPS["possession_context"],
    "deserved_quality_proxy": tuple(BASE_FIELDS) + GROUPS["deserved_quality"],
    "matchup_vulnerability": tuple(BASE_FIELDS) + GROUPS["matchup_vulnerability"],
    "drive_resilience": tuple(BASE_FIELDS) + GROUPS["drive_resilience"],
    "evolving_strength": tuple(BASE_FIELDS) + GROUPS["evolving_strength"],
    "all_creative": tuple(BASE_FIELDS) + tuple(
        dict.fromkeys(k for group in GROUPS.values() for k in group))
}


def _date(row):
    return dt.date.fromisoformat(row["date"])


def _eligible(row):
    return int(row["home_games_prior"])>=1 and int(row["away_games_prior"])>=1


def _clip(margin, total):
    total = max(0.,min(110.,float(total)))
    margin = max(-min(55.,total),min(min(55.,total),float(margin)))
    if not math.isfinite(margin) or not math.isfinite(total):
        raise ValueError("Nonfinite candidate output")
    return margin,total


def _variation(train, fields):
    """Skip unmeasured groups, rather than learning from all-mean imputation."""
    for field in fields:
        nums = [float(r[field]) for r in train if r.get(field) is not None]
        if len(nums)>=12 and len(set(round(n,8) for n in nums))>=2:
            return True
    return False


def _percentile(xs, p):
    values=sorted(float(x) for x in xs)
    if not values:raise ValueError("No calibration residuals")
    position=(len(values)-1)*p
    lo=int(math.floor(position));hi=int(math.ceil(position))
    return values[lo]+(values[hi]-values[lo])*(position-lo)


def _calibration(train, fields):
    """Past-only chronological residual calibration, no training residuals.

    Use earliest ~70% of prior games to fit, later ~30% to validate; never
    include heldout target week. At least 60 fit and 25 calibration games.
    """
    cutoff=max(60,math.floor(.70*len(train)))
    while cutoff<len(train) and _date(train[cutoff])==_date(train[cutoff-1]):
        cutoff+=1
    if cutoff>=len(train) or len(train)-cutoff<25:return None
    earlier,later=train[:cutoff],train[cutoff:]
    par=fit_ridge(earlier,fields)
    preds,_=predict(later,fields,par)
    errors=[]
    for row,p in zip(later,preds):
        margin,total=_clip(p[0],p[1])
        errors.append({"margin":row["home_score"]-row["away_score"]-margin,
                       "total":row["home_score"]+row["away_score"]-total,
                       "volatility":row.get("volatility_proxy")})
    # Stratify predicted high/low volatility with enough *past* calibration
    # examples. Missing signals use pooled residuals rather than invented zeros.
    valid=[float(e["volatility"]) for e in errors if e["volatility"] is not None]
    middle=_percentile(valid,.5) if len(valid)>=30 else None
    low=[e["total"] for e in errors if middle is not None and
         e["volatility"] is not None and e["volatility"]<middle]
    high=[e["total"] for e in errors if middle is not None and
          e["volatility"] is not None and e["volatility"]>=middle]
    split=len(low)>=12 and len(high)>=12
    def interval(vals):return [_percentile(vals,.10),_percentile(vals,.90)]
    return {"margin":interval([e["margin"] for e in errors]),
            "total":interval([e["total"] for e in errors]),
            "total_low":interval(low) if split else None,
            "total_high":interval(high) if split else None,
            "volatility_median":middle if split else None,
            "calibration_games":len(later),
            "method":"PAST_ONLY_TEMPORAL_SPLIT_RESIDUAL_QUANTILES",
            "prediction_interval_nominal":.80}


def _interval(score, offsets):
    return (max(0.,float(score)+offsets[0]),
            max(0.,float(score)+offsets[1]))


def _score_predictions(rows, predictions, calibration=None):
    if len(rows)!=len(predictions):
        raise ValueError("Mismatched test sample")
    outcome={"games":len(rows),"margin_abs":0.,"total_abs":0.,
             "margin_signed":0.,"home_winner_count":0,"su_correct":0,
             "margin_80_coverage":0,"total_80_coverage":0,
             "total_80_width_sum":0., "interval_games":0}
    for row,pred in zip(rows,predictions):
        margin,total=_clip(pred[0],pred[1])
        truth_m=row["home_score"]-row["away_score"]
        truth_t=row["home_score"]+row["away_score"]
        outcome["margin_abs"]+=abs(margin-truth_m)
        outcome["total_abs"]+=abs(total-truth_t)
        outcome["margin_signed"]+=margin-truth_m
        outcome["home_winner_count"]+=int(margin>0)
        outcome["su_correct"]+=int((margin>0)==(truth_m>0))
        if calibration:
            bounds=calibration["total"]
            if (calibration["volatility_median"] is not None and
                row.get("volatility_proxy") is not None):
                bounds=(calibration["total_high"] if row["volatility_proxy"]>=calibration["volatility_median"]
                        else calibration["total_low"])
            tl,tu=_interval(total,bounds)
            ml,mu=margin+calibration["margin"][0],margin+calibration["margin"][1]
            outcome["total_80_coverage"]+=int(tl<=truth_t<=tu)
            outcome["margin_80_coverage"]+=int(ml<=truth_m<=mu)
            outcome["total_80_width_sum"]+=tu-tl
            outcome["interval_games"]+=1
    n=len(rows)
    return {"games":n,"margin_mae":round(outcome["margin_abs"]/n,4) if n else None,
            "total_mae":round(outcome["total_abs"]/n,4) if n else None,
            "signed_home_bias":round(outcome["margin_signed"]/n,4) if n else None,
            "su_accuracy":round(outcome["su_correct"]/n,5) if n else None,
            "predicted_home_winner_fraction":round(outcome["home_winner_count"]/n,5) if n else None,
            "nominal_80pct_total_interval_coverage":round(outcome["total_80_coverage"]/outcome["interval_games"],5)
                if outcome["interval_games"] else None,
            "nominal_80pct_margin_interval_coverage":round(outcome["margin_80_coverage"]/outcome["interval_games"],5)
                if outcome["interval_games"] else None,
            "total_interval_mean_width":round(outcome["total_80_width_sum"]/outcome["interval_games"],4)
                if outcome["interval_games"] else None}


def _predeclared_ensemble(per_variant, test):
    out=[]
    for i,_ in enumerate(test):
        available=[(ENSEMBLE_WEIGHTS[n],per_variant[n][i]) for n in ENSEMBLE_WEIGHTS
                   if n in per_variant and per_variant[n][i] is not None]
        if not available:return None
        denom=sum(w for w,_ in available)
        out.append(tuple(sum(w*p[axis] for w,p in available)/denom for axis in (0,1)))
    return out


def _predictions(train,test,cutoff):
    variants={}
    skipped={}
    for name,fields in VARIANTS.items():
        additional=[f for f in fields if f not in BASE_FIELDS]
        if additional and not _variation(train,additional):
            skipped[name]="NOT_ENOUGH_MEASURED_PRIOR_FEATURE_VARIATION"
            continue
        fitted=fit_ridge(train,fields)
        predicted,_=predict(test,fields,fitted)
        variants[name]=[_clip(x[0],x[1]) for x in predicted]
    baseline=variants["active_v03"]
    eligible=[r for r in train if _eligible(r)]
    if len(eligible)>=MIN_TRAIN:
        params=fit_candidate(train,BASE_FIELDS,cutoff)
        m=predict_candidate(test,BASE_FIELDS,params)
        variants["home_recency"]=[_clip(y,base[1]) for y,base in zip(m,baseline)]
    else:
        skipped["home_recency"]="INSUFFICIENT_PRIOR_TWO_TEAM_PROFILES"
    # Actual prior score per drive and drive counts; return missing when
    # no two-sided drive evidence, rather than inventing possessions.
    mechanical=[]
    for row,base in zip(test,baseline):
        value=row.get("possession_score_estimate")
        mechanical.append(_clip(.65*base[0]+.35*value[0],
                                .65*base[1]+.35*value[1]) if value is not None else None)
    if all(p is not None for p in mechanical):
        variants["possession_mechanistic"]=mechanical
    else:
        skipped["possession_mechanistic"]="NOT_ALL_TEST_GAMES_HAVE_VERIFIED_PRIOR_DRIVE_COUNTS"
    ensemble=_predeclared_ensemble(variants,test)
    if ensemble is not None:
        variants["fixed_weight_ensemble"]=ensemble
    return variants,skipped


def validate(rows,start="2026-09-26",weeks=12,min_train=MIN_TRAIN):
    if not rows or len({str(r["game_id"]) for r in rows})!=len(rows):
        raise ValueError("Empty or duplicate completed games")
    if not isinstance(weeks,int) or weeks<1 or min_train<30:
        raise ValueError("Invalid validation policy")
    ordered=sorted(rows,key=lambda r:(_date(r),str(r["game_id"])))
    if any(_date(r).year!=2026 or
           any(type(r.get(key)) is not int for key in ("home_score","away_score")) or
           r.get("betting_status")!="PASS_UNVALIDATED" for r in ordered):
        raise ValueError("Missing verified season/score/research status")
    start_day=dt.date.fromisoformat(start)
    folds=[]
    scores=defaultdict(list)
    interval_results=[]
    for week in range(weeks):
        cutoff=start_day+dt.timedelta(days=7*week)
        end=cutoff+dt.timedelta(days=7)
        train=[r for r in ordered if _date(r)<cutoff]
        test=[r for r in ordered if cutoff<=_date(r)<end and _eligible(r)]
        if not test and cutoff>_date(ordered[-1]):break
        fold={"test_week_start":cutoff.isoformat(),"test_end_exclusive":end.isoformat(),
              "train_games":len(train),"test_games":len(test),
              "train_game_ids":[str(r["game_id"]) for r in train],
              "test_game_ids":[str(r["game_id"]) for r in test],
              "variants":{}}
        if len(train)<min_train or len(test)<1:
            fold["status"]="SKIPPED_INSUFFICIENT_TRAINING_OR_TEST"
            folds.append(fold);continue
        if {str(r["game_id"]) for r in train}&{str(r["game_id"]) for r in test}:
            raise ValueError("Overlapping train and test identities")
        variants,skipped=_predictions(train,test,cutoff)
        cal=_calibration(train,BASE_FIELDS)
        fold["status"]="EXPLORATORY_RESEARCH_EVALUATED"
        fold["calibration"]={"games":cal["calibration_games"],
                             "method":cal["method"]} if cal else None
        for name,guess in variants.items():
            fold["variants"][name]=_score_predictions(
                test,guess,cal if name=="active_v03" else None)
            scores[name].extend([{"game_id":r["game_id"],"date":r["date"],
                                  "actual_margin":r["home_score"]-r["away_score"],
                                  "actual_total":r["home_score"]+r["away_score"],
                                  "pred_margin":round(p[0],5),
                                  "pred_total":round(p[1],5)} for r,p in zip(test,guess)])
        for name,reason in skipped.items():
            fold["variants"][name]={"status":"SKIPPED","reason":reason}
        folds.append(fold)
    aggregate={}
    for name,recs in scores.items():
        if not recs:continue
        ma=np.mean([abs(r["pred_margin"]-r["actual_margin"]) for r in recs])
        ta=np.mean([abs(r["pred_total"]-r["actual_total"]) for r in recs])
        bias=np.mean([r["pred_margin"]-r["actual_margin"] for r in recs])
        aggregate[name]={"games":len(recs),"margin_mae":round(float(ma),4),
                         "total_mae":round(float(ta),4),"signed_home_bias":round(float(bias),4),
                         "su_accuracy":round(float(np.mean([(r["pred_margin"]>0)==(r["actual_margin"]>0)
                                                          for r in recs])),5)}
    baseline=aggregate.get("active_v03")
    for name,summary in aggregate.items():
        if baseline is not None and name!="active_v03" and summary["games"]==baseline["games"]:
            summary["paired_delta_margin_mae_vs_v03"]=round(summary["margin_mae"]-baseline["margin_mae"],4)
            summary["paired_delta_total_mae_vs_v03"]=round(summary["total_mae"]-baseline["total_mae"],4)
        elif name!="active_v03":
            summary["comparison"]="NOT_PAIRED_ALL_BASELINE_GAMES"
    return {"status":STATUS,"candidate":VERSION,"season":2026,
            "forecast_promotion":False,"model_promoted":False,
            "active_model_unchanged":True,"safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED",
            "historical_pbp_publication_verified":False,
            "no_authenticated_historical_market_odds":True,
            "feature_groups":GROUPS,"ensemble_weights_predeclared":ENSEMBLE_WEIGHTS,
            "unavailable_inputs":{"turnover_attribution":"UNVERIFIED",
                "true_drive_start_position":"NOT_IN_DRIVE_SUMMARY",
                "individual_player_replacement_values":"NOT_TRAINED_OR_VERIFIED"},
            "point_in_time_caveat":"Advanced retrospective files can include later revisions; chronology of scores is not proof of historical as-of feature availability.",
            "interval_method":"PAST_ONLY_TEMPORAL_SPLIT_RESIDUAL_QUANTILES; 80% NOMINAL, NOT YET PROSPECTIVELY CALIBRATED",
            "weeks":folds,"aggregate":aggregate},dict(scores)


def run(games,advanced,manifest,output):
    source,adv,_=load_inputs(games,advanced,manifest)
    rows=build(source,adv)
    report,predictions=validate(rows)
    dest=Path(output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():raise FileExistsError("Do not overwrite an experiment report")
    dest.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":STATUS,"model_promoted":False,
                      "groups":list(GROUPS),"weeks":len(report["weeks"]),
                      "models":report["aggregate"]},sort_keys=True))
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("games","advanced","manifest","output"):
        p.add_argument("--"+name,required=True)
    a=p.parse_args()
    run(a.games,a.advanced,a.manifest,a.output)

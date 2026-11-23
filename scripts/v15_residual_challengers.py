"""V15 scored challengers: predeclared, regularized residuals atop FROZEN V14.

Ablate three effects without ever retraining, modifying or retrospectively
correcting the V04/V14 frozen forecasts: (1) earlier-week total bias,
(2) extra source-dated game pace interaction, and (3) cautious late-margin
pass-protection/turnover interactions for close games.

These are analyses on previously studied 2026 historical sources whose
original upstream PBP publication timestamps are NOT independently verified.
No pick, moneyline, odds, or betting recommendation is produced.
"""
import math
import numpy as np

from scripts.v14_matchup_features import STATUS as MATCH_STATUS

STATUS="V15_PRIOR_FOLD_RESIDUAL_SCORE_RESEARCH_ONLY"
VARIANTS=("totals_bias","totals_pace","close_margin","combined")
N_PRIOR_MIN=55
TOTAL_INTERCEPT_L2=120.
TOTAL_PACE_L2=480.
MARGIN_INTERCEPT_L2=180.
MARGIN_FEATURE_L2=580.
TOTAL_CAP=4.
MARGIN_CAP=3.
CLOSE_LIMIT=10.


def _finite(v):
    return type(v) in (int,float) and math.isfinite(v)


def _clamp(x,lo,hi):
    return max(lo,min(hi,x))


def _base(row):
    forecast=row["forecasts"]["joint_close"]
    m,t=forecast["margin"],forecast["total"]
    if not (_finite(m) and _finite(t) and -110<m<110 and 10<t<150):
        raise ValueError("Malformed original frozen V14 score")
    return float(m),float(t)


def _features(row):
    evidence=row.get("matchup")
    if not evidence or evidence.get("ready") is not True:
        return None
    if (evidence.get("status")!=MATCH_STATUS or
        evidence.get("cutoff")!=row.get("cutoff") or
        evidence.get("historical_first_publication_authenticated") is not False):
        raise ValueError("V15 source-dated opponent profile is not authenticated")
    v=evidence.get("features")
    if not isinstance(v,dict) or not all(_finite(v.get(k)) and abs(v[k])<=2.50001
        for k in ("game_pace","pass_matchup","pressure_pass","turnover_quality")):
        raise ValueError("Unknown V14 feature semantics")
    return (float(v["game_pace"]),float(v["pass_matchup"]),
            float(v["pressure_pass"]),float(v["turnover_quality"]))


def _solve(rows,names,field):
    if len(rows)<N_PRIOR_MIN:
        return {"ready":False,"n":len(rows),"weights":[0.]*len(names)}
    x=np.array([v for v,y in rows],dtype=float)
    y=np.array([y for v,y in rows],dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("V15 fitted on nonfinite source data")
    penalties=([TOTAL_INTERCEPT_L2]+[TOTAL_PACE_L2]*(len(names)-1)
               if field=="total" else
               [MARGIN_INTERCEPT_L2]+[MARGIN_FEATURE_L2]*(len(names)-1))
    ridge=np.diag(penalties)
    w=np.linalg.solve(x.T@x+ridge,x.T@y)
    if not np.isfinite(w).all():
        raise ValueError("V15 residual ridge ill-conditioned")
    return {"ready":True,"n":len(rows),"weights":w.tolist(),
            "feature_names":names,"regularization":penalties}


def fit(prior,cutoff):
    """Train ONLY on entire prior held-out weeks; no current game outcome."""
    if not isinstance(cutoff,str) or len(cutoff)!=10 or not isinstance(prior,list):
        raise ValueError("Original historical cutoff is required")
    seen=set();total_bias=[];total_pace=[];close_margin=[]
    for row in prior:
        gid=str(row.get("game_id",""))
        if (not gid or gid in seen or
            not isinstance(row.get("date"),str) or row["date"]>=cutoff or
            not isinstance(row.get("cutoff"),str) or row["cutoff"]>=cutoff):
            raise ValueError("Duplicate or same-week/future training score")
        seen.add(gid)
        margin,total=_base(row)
        h,a=row.get("final_home"),row.get("final_away")
        if type(h) is not int or type(a) is not int or min(h,a)<0:
            raise ValueError("Cannot calibrate from unverifiable outcome")
        rt=h+a-total
        rm=h-a-margin
        total_bias.append(([1.],rt))
        vec=_features(row)
        if vec is not None:
            total_pace.append(([1.,vec[0]],rt))
            if abs(margin)<=CLOSE_LIMIT:
                close_margin.append(([1.,vec[1],vec[2],vec[3]],rm))
    return {
        "status":STATUS,"cutoff_exclusive":cutoff,
        "prior_games":len(prior),"prior_game_ids":sorted(seen),
        "models":{
            "totals_bias":_solve(total_bias,["bias"],"total"),
            "totals_pace":_solve(total_pace,["bias","game_pace"],"total"),
            "close_margin":_solve(close_margin,
                ["bias","pass_matchup","pressure_pass","turnover_quality"],"margin")},
        "model_promoted":False,"upstream_historical_first_publication_verified":False,
        "fit_only_previous_completed_weeks":True,
        "independent_future_validation_passed":False,
    }


def project(frozen,learned,variant):
    if variant not in VARIANTS or learned.get("status")!=STATUS or (
        learned.get("cutoff_exclusive")!=frozen.get("cutoff") or
        learned.get("model_promoted") is not False or
        learned.get("fit_only_previous_completed_weeks") is not True):
        raise ValueError("V15 and frozen V14 historical cutoffs disagree")
    m,t=_base(frozen)
    vec=_features(frozen)
    extra_m=extra_t=0.
    if variant in ("totals_bias","totals_pace","combined"):
        key="totals_pace" if variant in ("totals_pace","combined") else "totals_bias"
        model=learned["models"][key]
        if model["ready"] and (key=="totals_bias" or vec is not None):
            x=[1.,vec[0]] if key=="totals_pace" else [1.]
            extra_t=_clamp(sum(a*b for a,b in zip(x,model["weights"])),-TOTAL_CAP,TOTAL_CAP)
    if variant in ("close_margin","combined") and abs(m)<=CLOSE_LIMIT and vec is not None:
        model=learned["models"]["close_margin"]
        if model["ready"]:
            x=[1.,vec[1],vec[2],vec[3]]
            extra_m=_clamp(sum(a*b for a,b in zip(x,model["weights"])),-MARGIN_CAP,MARGIN_CAP)
    updated_m=m+extra_m
    updated_t=_clamp(t+extra_t,20.,110.)
    updated_m=_clamp(updated_m,-updated_t+.5,updated_t-.5)
    return {
        "status":STATUS,"variant":variant,
        "margin":round(updated_m,6),"total":round(updated_t,6),
        "home_points":round((updated_t+updated_m)/2,6),
        "away_points":round((updated_t-updated_m)/2,6),
        "v14_margin":m,"v14_total":t,
        "margin_correction":round(updated_m-m,6),
        "total_correction":round(updated_t-t,6),
        "matchup_ready":vec is not None,
        "trained_prior_games":learned["prior_games"],
        "trained_week_exclusive":frozen["cutoff"],
        "market_line_used_in_scoring":False,
        "future_games_used_in_training":False,
        "historical_source_first_publication_authenticated":False,
        "model_promoted":False,"safe_for_betting":False,
        "website_scores_replaced":False,
    }

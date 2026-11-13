"""V14: genuinely distinct close-game opponent-style *scoring* challenger.

V04 retains an independent fixed baseline. V14 learns small, strongly
regularized residual corrections from historically earlier V04 holdout
forecast ERRORS, never from the target week. Matchup features are recomputed
from strictly prior-date PBP. The target week and current bookmaker lines are
excluded from fitting both score correction and uncertainty.

V14 is NOT an independently authenticated historical predecision model:
the 2026 ESPN PBP was downloaded retrospectively. This is research only.
"""
import math
import numpy as np

from scripts.v14_matchup_features import FEATURES,STATUS as MATCHUP_STATUS

STATUS="V14_REGULARIZED_V04_MATCHUP_RESIDUAL_RESEARCH_ONLY"
MIN_TRAIN=55
PENALTY_MARGIN=160.
PENALTY_TOTAL=220.
PENALTY_INTERCEPT=65.
MAX_MARGIN_CORRECTION=6.
MAX_TOTAL_CORRECTION=6.
VARIANTS=("margin_only","total_only","joint","joint_close")


def _num(v):
    return type(v) in (int,float) and math.isfinite(v)


def _vector(match):
    if not match or not match.get("ready"):
        return None
    if match.get("status")!=MATCHUP_STATUS:
        raise ValueError("V14 feature provenance invalid")
    v=match["features"]
    if set(v)!=set(FEATURES) or any(not _num(v[k]) or abs(v[k])>2.5001 for k in FEATURES):
        raise ValueError("Unknown or unstable matchup feature")
    return [1.]+[float(v[k]) for k in FEATURES]


def _score(row):
    s=row["v04"]
    h,a,m,t=(s.get(k) for k in ("home_points","away_points","margin","total"))
    if not all(_num(x) for x in (h,a,m,t)) or abs((h-a)-m)>.06 or abs(h+a-t)>.06:
        raise ValueError("Unreconciled V04 score")
    return float(m),float(t)


def _solve(prior,field,cutoff):
    X=[];Y=[];W=[]
    for r in prior:
        if not isinstance(r,dict) or r.get("cutoff","")>=cutoff or r.get("date","")>=cutoff:
            raise ValueError("V14 cannot train on current/future-week outcomes")
        x=_vector(r.get("matchup"))
        if x is None:continue
        m,t=_score(r)
        h,a=r["final_home"],r["final_away"]
        if type(h) is not int or type(a) is not int or not (0<=h<=150 and 0<=a<=150):
            raise ValueError("Unverified final")
        X.append(x)
        Y.append(((h-a)-m) if field=="margin" else ((h+a)-t))
        W.append(1.30 if abs(m)<=10 else 1.0)
    if len(X)<MIN_TRAIN:
        return {"ready":False,"n":len(X),"weights":[0.]*(len(FEATURES)+1)}
    mat=np.asarray(X,dtype=float)
    labels=np.asarray(Y,dtype=float)
    w=np.asarray(W,dtype=float)
    # L2 shrink-to-zero on feature coefficients. Intercept has a separate
    # prior and is only a small residual bias, never another team rating.
    penalty=np.diag([PENALTY_INTERCEPT]+[
        PENALTY_MARGIN if field=="margin" else PENALTY_TOTAL]*len(FEATURES))
    b=np.linalg.solve(mat.T@(w[:,None]*mat)+penalty,mat.T@(w*labels))
    if not np.isfinite(b).all():raise ValueError("V14 numerical instability")
    return {"ready":True,"n":len(X),"weights":b.tolist(),
            "lambda_features":PENALTY_MARGIN if field=="margin" else PENALTY_TOTAL,
            "intercept_lambda":PENALTY_INTERCEPT}


def fit(prior,cutoff):
    if not isinstance(prior,list) or not isinstance(cutoff,str):
        raise ValueError("Missing dated prior V04 holdout forecasts")
    ids=set()
    for r in prior:
        gid=str(r.get("game_id",""))
        if not gid or gid in ids:
            raise ValueError("Missing/duplicate V14 historical forecast ID")
        ids.add(gid)
    models={f:_solve(prior,f,cutoff) for f in ("margin","total")}
    return {"status":STATUS,"cutoff_exclusive":cutoff,
            "n_prior_games":len(prior),"prior_game_ids":sorted(ids),
            "feature_names":list(FEATURES),
            "models":models,"historical_source_first_publication_verified":False,
            "training_target_week_excluded":True,
            "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}


def project(v04,match,model,cutoff,variant="joint_close"):
    if (variant not in VARIANTS or model.get("status")!=STATUS or
        model.get("cutoff_exclusive")!=cutoff or
        model.get("model_promoted") is not False or
        model.get("training_target_week_excluded") is not True):
        raise ValueError("V14 forecast or historical training invalid")
    m,t=_score({"v04":v04})
    x=_vector(match)
    if x and match.get("cutoff")!=cutoff:
        raise ValueError("V14 opponent profiles not from same original weekly cutoff")
    corrections={}
    for field in ("margin","total"):
        fitrow=model["models"][field]
        raw=sum(a*b for a,b in zip(x,fitrow["weights"])) if x and fitrow["ready"] else 0.
        limit=MAX_MARGIN_CORRECTION if field=="margin" else MAX_TOTAL_CORRECTION
        corrections[field]=max(-limit,min(limit,raw))
    if variant=="margin_only":corrections["total"]=0.
    if variant=="total_only":corrections["margin"]=0.
    if variant=="joint_close":
        # Avoid overwriting demonstrated V04 strong talent mismatches.
        # This is a fixed precommitted gate, not a target-line-dependent fit.
        closeness=min(1.,10./max(10.,abs(m)))
        corrections["margin"]*=closeness
        corrections["total"]*=closeness
    margin=m+corrections["margin"]
    total=max(20.,min(110.,t+corrections["total"]))
    margin=max(-total+1.,min(total-1.,margin))
    h=(total+margin)/2;a=(total-margin)/2
    return {"status":STATUS,"variant":variant,
            "home_points":round(h,6),"away_points":round(a,6),
            "margin":round(margin,6),"total":round(total,6),
            "v04_margin":m,"v04_total":t,
            "margin_adjustment":round(margin-m,6),
            "total_adjustment":round(total-t,6),
            "matchup_evidence_ready":x is not None,
            "earlier_matchup_training_games":model["models"]["margin"]["n"],
            "source_cutoff_exclusive":cutoff,
            "current_market_line_used_for_training":False,
            "historical_source_first_publication_verified":False,
            "model_promoted":False,"safe_for_betting":False}

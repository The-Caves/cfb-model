"""V04 research score model: opponent-adjusted margin AND fitted team scoring.

Both targets are estimated solely from previously completed, source-observed
2026 college football scores. Margin uses opponent-strength differences
with conservative 2.5-point nonneutral venue effect. Total is separately
fitted from two-sided opponent-specific offensive and defensive scoring
effects under regularization and past-only recency weights. Unlike the
temporary R1/V03 hybrid, NO V03 score, margin, total or market odds enters
the V04 point prediction. No QBs/injuries or prospectively validated betting
edges are inferred. Source is retrospectively retrieved and unverified at
the historic time of first publication; this is a new research candidate.
"""
import datetime as dt
import math
from collections import defaultdict

import numpy as np
from scripts.site_home_bias_guard import (
    HOME_ALLOWANCE, MARGIN_CAP, MIN_TRAINING_GAMES, _source_games, ratings)

MODEL="V04_INDEPENDENT_OPPONENT_ADJUSTED_SCORES_RESEARCH_ONLY"
STATUS="SOURCE_OBSERVED_DIRECT_TEAM_SCORE_MODEL_RESEARCH_ONLY"
TEAM_SCORE_PENALTY=12.
HOME_PRIOR_PENALTY=170.
HALF_LIFE_DAYS=28.
MAX_TOTAL=110.
MIN_TOTAL=20.
MAX_MARGIN=55.

def fit(rows,decision_utc):
    """Fit only history strictly before decision day; fail on unsafe scores."""
    from scripts.game_context import parse_time
    from zoneinfo import ZoneInfo
    at=parse_time(decision_utc)
    verified=_source_games(rows,at)
    if len(verified)<MIN_TRAINING_GAMES:
        raise ValueError("Not enough prior verified games for V04")
    names=sorted({n for home,away,_,_ in verified for n in (home,away)})
    keys={name:i for i,name in enumerate(names)}
    n=len(names)
    X=np.zeros((2*len(verified),2*n+2),dtype=float)
    Y=np.zeros(2*len(verified),dtype=float)
    W=np.zeros(2*len(verified),dtype=float)
    last_date=at.astimezone(ZoneInfo("America/New_York")).date()
    for i,((h,a,m,neutral),raw) in enumerate(zip(verified,rows)):
        hp=float(raw["home_score"]);ap=float(raw["away_score"])
        if not all(math.isfinite(v) and 0<=v<=200 for v in (hp,ap)):
            raise ValueError("Nonfinite or implausible source football score")
        # Both sides' scored points are separate supervised observations.
        # Intercept gives the as-of baseline expected points per team.
        # The venue coefficient learns only a correction to the conservative
        # 2.5-point MARGIN prior rather than 2026's biased raw +13 margin.
        site=0. if neutral else .5
        X[2*i,0]=1.;X[2*i+1,0]=1.
        X[2*i,1]=site;X[2*i+1,1]=-site
        X[2*i,2+keys[h]]=1.;X[2*i+1,2+keys[a]]=1.
        X[2*i,2+n+keys[a]]=-1.;X[2*i+1,2+n+keys[h]]=-1.
        Y[2*i]=min(70.,hp)-site*HOME_ALLOWANCE
        Y[2*i+1]=min(70.,ap)+site*HOME_ALLOWANCE
        day=dt.date.fromisoformat(raw["date"])
        age=(last_date-day).days
        if age<=0:raise ValueError("Future game included in total training")
        weight=math.exp2(-age/HALF_LIFE_DAYS)
        W[2*i]=weight;W[2*i+1]=weight
    W/=W.mean()
    penalty=np.full(2*n+2,TEAM_SCORE_PENALTY)
    penalty[0]=0.
    penalty[1]=HOME_PRIOR_PENALTY
    rhs=X.T@(W*Y)
    beta=np.linalg.solve(X.T@(W[:,None]*X)+np.diag(penalty),rhs)
    if not np.isfinite(beta).all():
        raise ValueError("Unstable opponent-scoring system")
    correction=float(np.clip(beta[1],-HOME_ALLOWANCE,4.5-HOME_ALLOWANCE))
    site_effect=HOME_ALLOWANCE+correction
    # Explicit 2-sided attack-vs-defense expected-point adjustments.
    offense={name:float(beta[2+i]) for name,i in keys.items()}
    defense={name:float(beta[2+n+i]) for name,i in keys.items()}
    return {
        "status":STATUS,"model":MODEL,"n_training_games":len(verified),
        "teams":names,"neutral_team_strength":ratings(verified),
        "scoring_intercept":float(beta[0]),"offense":offense,
        "defense":defense,"home_field_points":site_effect,
        "score_penalty":TEAM_SCORE_PENALTY,
        "home_prior_penalty":HOME_PRIOR_PENALTY,
        "recency_half_life_days":HALF_LIFE_DAYS,
        "market_used_for_fit":False,"historical_first_publication_verified":False,
        "betting_status":"PASS_UNVALIDATED",
        "model_promoted":False,
    }

def predict(model,home,away,neutral):
    """Direct coherent home/away point estimates (not mixed with V03)."""
    if model.get("status")!=STATUS or type(neutral) is not bool:
        return None
    if home==away or any(name not in model["offense"] for name in (home,away)):
        return None
    home_raw=(model["scoring_intercept"]+
        model["offense"][home]-model["defense"][away])
    away_raw=(model["scoring_intercept"]+
        model["offense"][away]-model["defense"][home])
    total=max(MIN_TOTAL,min(MAX_TOTAL,home_raw+away_raw))
    margin=(model["neutral_team_strength"][home]-
            model["neutral_team_strength"][away]+
            (0. if neutral else model["home_field_points"]))
    margin=max(-min(MAX_MARGIN,total),min(min(MAX_MARGIN,total),margin))
    points_home=(total+margin)/2
    points_away=(total-margin)/2
    if any(not math.isfinite(x) or x<0 for x in (total,margin,points_home,points_away)):
        raise ValueError("Invalid opponent-adjusted team score projection")
    return {
        "status":STATUS,"model":MODEL,
        "home_points":round(points_home,4),
        "away_points":round(points_away,4),
        "home_margin":round(margin,4),
        "total_points":round(total,4),
        "home_field_points":round(0. if neutral else model["home_field_points"],4),
        "neutral":neutral,
        "source_training_games":model["n_training_games"],
        "direct_scoring_fit_uses_v03_total":False,
        "opponent_strength_margin_model":True,
        "opponent_attack_defense_total_model":True,
        "no_market_lines_in_training":True,
        "historical_source_first_publication_verified":False,
        "model_promoted":False,
        "safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED",
    }

def walkforward(rows,cutoffs):
    """Same-day embargo, explicit matched fold samples, no in-sample grades."""
    from scripts.game_context import parse_time
    results=[]
    known={str(g["game_id"]) for g in rows}
    if len(known)!=len(rows):raise ValueError("Duplicate full-season score game ID")
    for cutoff in cutoffs:
        day=dt.date.fromisoformat(cutoff)
        past=[r for r in rows if dt.date.fromisoformat(r["date"])<day]
        future=[r for r in rows if day<=dt.date.fromisoformat(r["date"])<day+dt.timedelta(days=7)]
        if len(past)<MIN_TRAINING_GAMES or not future:continue
        at=dt.datetime.combine(day,dt.time.min,tzinfo=dt.timezone.utc)
        model=fit(past,at.isoformat())
        detail=[]
        for g in future:
            neutral=str(g["neutral"]).lower()
            if neutral not in ("true","false"):raise ValueError("Unknown venue")
            p=predict(model,g["home"],g["away"],neutral=="true")
            if p is None:continue
            detail.append({"game_id":str(g["game_id"]),"forecast_date":cutoff,
                "margin":p["home_margin"],"total":p["total_points"],
                "actual_margin":float(g["home_score"])-float(g["away_score"]),
                "actual_total":float(g["home_score"])+float(g["away_score"])})
        if detail:
            n=len(detail)
            results.append({"cutoff":cutoff,"training_games":len(past),
                "matched_games":n,
                "home_win_fraction":round(sum(r["margin"]>0 for r in detail)/n,5),
                "signed_home_margin_error":round(sum(r["margin"]-r["actual_margin"] for r in detail)/n,5),
                "margin_mae":round(sum(abs(r["margin"]-r["actual_margin"]) for r in detail)/n,5),
                "total_mae":round(sum(abs(r["total"]-r["actual_total"]) for r in detail)/n,5),
                "su_accuracy":round(sum((r["margin"]>0)==(r["actual_margin"]>0) for r in detail)/n,5),
                "predictions":detail})
    return {"status":"V04_CHRONOLOGICAL_RESEARCH_ONLY",
        "model":MODEL,"folds":results,"model_promoted":False,
        "historical_publication_verified":False,
        "no_bookmaker_market_history_used":True,
        "betting_status":"PASS_UNVALIDATED"}

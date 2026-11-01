"""V05 robust opponent-strength / recent-form score challenger (research only).

Four separately auditable ideas:
  1. recency-weighted, capped opponent-strength margin with robust loss;
  2. robust two-sided opponent offense/defense scoring, never V03 totals;
  3. strictly past-game, shrinkage-bounded team form in margin and totals;
  4. sparse-history uncertainty flags, never imagined QB/injury effects.

All supervised inputs are completed source scores from BEFORE the Eastern
football day. Never fit on a market price, score from the target game, or
a retrospectively discovered injury. Historical first-publication time
remains unverified. Model promotion requires fresh prospective evidence.
"""
import datetime as dt
import math
from collections import defaultdict
from zoneinfo import ZoneInfo

import numpy as np

from scripts.game_context import parse_time
from scripts.site_home_bias_guard import (
    HOME_ALLOWANCE, MARGIN_CAP, MIN_TRAINING_GAMES, _source_games)

MODEL="V05_ROBUST_RECENCY_FORM_SCORES_RESEARCH_ONLY"
STATUS="SOURCE_OBSERVED_V05_SHADOW_SCORES"
HALF_LIFE_DAYS=28.
RIDGE_STRENGTH=2.0
RIDGE_SCORE=12.
HOME_PRIOR=170.
HUBER_POINT=17.
HUBER_MARGIN=17.
FORM_GAMES=4
MIN_FORM_GAMES=3
MIN_RELIABLE_TEAM_GAMES=4
MAX_FORM_MARGIN=4.
MAX_FORM_TOTAL=5.
FORM_MARGIN_WEIGHT=.35
FORM_TOTAL_WEIGHT=.20
MARGIN_SCORE_BLEND=.15
MAX_MARGIN=55.
MIN_TOTAL=20.
MAX_TOTAL=110.


def _weighted_ridge(x,y,weights,penalty,robust=True,huber=HUBER_POINT):
    """Deterministic Huber IRLS over weighted ridge; cap outlier leverage."""
    if not (np.isfinite(x).all() and np.isfinite(y).all() and
            np.isfinite(weights).all() and np.all(weights>0)):
        raise ValueError("Invalid V05 numerical source")
    residual_weights=np.ones(len(y),dtype=float)
    coeff=None
    for _ in range(3 if robust else 1):
        w=weights*residual_weights
        coeff=np.linalg.solve(x.T@(w[:,None]*x)+np.diag(penalty),x.T@(w*y))
        if not np.isfinite(coeff).all():
            raise ValueError("Unstable robust opponent score fit")
        delta=np.abs(y-x@coeff)
        residual_weights=np.maximum(.25,np.minimum(1.,huber/np.maximum(1e-8,delta)))
    return coeff


def fit(rows,decision_utc):
    instant=parse_time(decision_utc)
    cutoff=instant.astimezone(ZoneInfo("America/New_York")).date()
    verified=_source_games(rows,instant)
    if len(verified)<MIN_TRAINING_GAMES:
        raise ValueError("Insufficient past V05 scores")
    names=sorted({t for h,a,_,_ in verified for t in (h,a)})
    idx={n:i for i,n in enumerate(names)}
    count=len(names)
    g=len(verified)
    xx=np.zeros((g,count))
    mm=np.zeros(g)
    weight=np.zeros(g)
    pointx=np.zeros((2*g,2*count+2))
    pointy=np.zeros(2*g)
    team_history=defaultdict(list)
    for i,((home,away,margin,neutral),row) in enumerate(zip(verified,rows)):
        # Source-derived game date is Eastern. Identical day is embargoed.
        day=dt.date.fromisoformat(row["date"])
        age=(cutoff-day).days
        if age<=0 or parse_time(row["kickoff_utc"])>=instant:
            raise ValueError("V05 future score leakage")
        hp=float(row["home_score"]);ap=float(row["away_score"])
        if not all(math.isfinite(v) and 0<=v<=200 and v.is_integer()
                   for v in (hp,ap)):
            raise ValueError("Invalid V05 final score")
        loc=0. if neutral else .5
        xx[i,idx[home]]=1.
        xx[i,idx[away]]=-1.
        mm[i]=max(-MARGIN_CAP,min(MARGIN_CAP,margin))-(0. if neutral else HOME_ALLOWANCE)
        weight[i]=math.exp2(-age/HALF_LIFE_DAYS)
        pointx[2*i,0]=pointx[2*i+1,0]=1.
        pointx[2*i,1]=loc
        pointx[2*i+1,1]=-loc
        pointx[2*i,2+idx[home]]=1.
        pointx[2*i+1,2+idx[away]]=1.
        pointx[2*i,2+count+idx[away]]=-1.
        pointx[2*i+1,2+count+idx[home]]=-1.
        pointy[2*i]=min(70.,hp)-loc*HOME_ALLOWANCE
        pointy[2*i+1]=min(70.,ap)+loc*HOME_ALLOWANCE
        team_history[home].append((day,str(row["game_id"]),i,1))
        team_history[away].append((day,str(row["game_id"]),i,-1))
    weight/=weight.mean()
    strength=_weighted_ridge(xx,mm,weight,np.full(count,RIDGE_STRENGTH),
                             huber=HUBER_MARGIN)
    scorepenalty=np.full(2*count+2,RIDGE_SCORE)
    scorepenalty[0]=0.
    scorepenalty[1]=HOME_PRIOR
    scorecoeff=_weighted_ridge(pointx,pointy,np.repeat(weight,2),
                                scorepenalty,huber=HUBER_POINT)
    site=float(np.clip(
        HOME_ALLOWANCE+scorecoeff[1],0.,4.5))
    strengths={name:float(strength[idx[name]]) for name in names}
    offense={name:float(scorecoeff[2+idx[name]]) for name in names}
    defense={name:float(scorecoeff[2+count+idx[name]]) for name in names}
    baseline=float(scorecoeff[0])

    # All residuals here are past source scores only. They describe model
    # form, not an as-known-at-older-game-time out-of-sample forecast.
    team_form={}
    for name,history in team_history.items():
        latest=sorted(history,key=lambda item:(item[0],item[1]))[-FORM_GAMES:]
        if len(latest)<MIN_FORM_GAMES:
            team_form[name]={"margin_shift":0.,"total_shift":0.,
                "games_used":len(latest),"activated":False}
            continue
        differences=[]
        totals=[]
        for day,gid,i,sign in latest:
            h,a,observed,neutral=verified[i]
            expected=(strengths[h]-strengths[a]+
                      (0. if neutral else HOME_ALLOWANCE))
            margin_error=sign*(max(-MARGIN_CAP,min(MARGIN_CAP,observed))-expected)
            raw_h=baseline+offense[h]-defense[a]
            raw_a=baseline+offense[a]-defense[h]
            true_total=float(rows[i]["home_score"])+float(rows[i]["away_score"])
            residual_total=max(-40.,min(40.,true_total-(raw_h+raw_a)))
            differences.append(margin_error)
            totals.append(residual_total)
        # Each team has at least three previous scores. Shrink against a
        # notional five-game prior; cap adjustments so a blowout cannot
        # determine a new spread single-handedly.
        shrink=len(latest)/(len(latest)+5.)
        m=max(-MAX_FORM_MARGIN,min(MAX_FORM_MARGIN,
             FORM_MARGIN_WEIGHT*shrink*sum(differences)/len(differences)))
        t=max(-MAX_FORM_TOTAL,min(MAX_FORM_TOTAL,
             FORM_TOTAL_WEIGHT*shrink*sum(totals)/len(totals)))
        team_form[name]={"margin_shift":m,"total_shift":t,
                         "games_used":len(latest),"activated":True}
    games_count={name:len(h) for name,h in team_history.items()}
    margin_sigma=float(np.sqrt(np.average(
        (mm-xx@strength)**2,weights=weight)))
    total_sigma=float(np.sqrt(np.average(
        (pointy-pointx@scorecoeff)**2,weights=np.repeat(weight,2))))
    return {
        "status":STATUS,"model":MODEL,"asof_utc":instant.isoformat(),
        "source_training_games":g,"teams":names,
        "strength":strengths,"offense":offense,"defense":defense,
        "baseline_team_points":baseline,"home_field_points":site,
        "team_form":team_form,"team_games":games_count,
        "residual_margin_scale_in_sample":round(margin_sigma,4),
        "residual_team_points_scale_in_sample":round(total_sigma,4),
        "robust_loss":"HUBER_IRLS_3_PASSES",
        "blowout_margin_cap":MARGIN_CAP,
        "recency_half_life_days":HALF_LIFE_DAYS,
        "form_minimum_games":MIN_FORM_GAMES,
        "market_used_for_fit":False,
        "player_availability_effect_inferred":False,
        "historical_source_first_publication_verified":False,
        "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}


def predict(model,home,away,neutral,variant="v05_full"):
    """All variants use the same past-only fit; no market or QB guesses."""
    if not isinstance(model,dict) or model.get("status")!=STATUS or
        model.get("model")!=MODEL or type(neutral) is not bool:
        return None
    if variant not in ("v05_full","v05_no_form","v05_no_margin_form",
                      "v05_no_total_form"):
        raise ValueError("Unregistered V05 ablation")
    if home==away or home not in model["strength"] or away not in model["strength"]:
        return None
    score_h=(model["baseline_team_points"]+
             model["offense"][home]-model["defense"][away])
    score_a=(model["baseline_team_points"]+
             model["offense"][away]-model["defense"][home])
    venue=0. if neutral else model["home_field_points"]
    strength_margin=(model["strength"][home]-model["strength"][away]+venue)
    score_margin=(score_h-score_a+venue)
    margin=(1.-MARGIN_SCORE_BLEND)*strength_margin+MARGIN_SCORE_BLEND*score_margin
    total=score_h+score_a
    hm=model["team_form"][home]
    am=model["team_form"][away]
    if variant in ("v05_full","v05_no_total_form"):
        margin+=hm["margin_shift"]-am["margin_shift"]
    if variant in ("v05_full","v05_no_margin_form"):
        total+=hm["total_shift"]+am["total_shift"]
    total=max(MIN_TOTAL,min(MAX_TOTAL,total))
    margin=max(-min(MAX_MARGIN,total),min(min(MAX_MARGIN,total),margin))
    ph=(total+margin)/2.
    pa=(total-margin)/2.
    if not all(math.isfinite(x) and x>=0 for x in (total,ph,pa)):
        raise ValueError("Nonfinite V05 outcome")
    samples=min(model["team_games"][home],model["team_games"][away])
    return {
        "status":STATUS,"model":MODEL,"variant":variant,
        "home_points":round(ph,4),"away_points":round(pa,4),
        "home_margin":round(margin,4),"total_points":round(total,4),
        "neutral":neutral,"home_field_points":round(venue,4),
        "source_training_games":model["source_training_games"],
        "lesser_team_history_games":samples,
        "thin_history_warning":samples<MIN_RELIABLE_TEAM_GAMES,
        "home_form_games":hm["games_used"],"away_form_games":am["games_used"],
        "form_margin_adjustment":round(
            hm["margin_shift"]-am["margin_shift"],4)
            if variant in ("v05_full","v05_no_total_form") else 0.,
        "form_total_adjustment":round(
            hm["total_shift"]+am["total_shift"],4)
            if variant in ("v05_full","v05_no_margin_form") else 0.,
        "score_variants_not_retuned_on_holdout":True,
        "independent_robust_score_fit":True,
        "no_market_lines_in_training":True,
        "no_v03_forecast_reuse":True,"no_qb_or_injury_inference":True,
        "uncertainty_not_calibrated":True,
        "historical_source_first_publication_verified":False,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

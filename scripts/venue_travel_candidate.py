"""2026 venue-separated opponent ratings, home-field and travel ablations.

Research only. This intentionally does NOT add an extra home bonus to the
existing V03 ridge; it estimates neutral strength from actual prior outcomes
and a regularized venue intercept in a separate candidate.

For travel, one must supply dated, source-identified game-level geographic
observations. Missing mileage, zone, direction or body clock is NOT zero, and
the model refuses to learn a travel coefficient from inferred score margins.
Retrospective 2026 PBP and archived venue data are not historical pregame
publication authenticated.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
import numpy as np

STATUS="VENUE_SEPARATED_HOME_TRAVEL_RESEARCH_ONLY"
VERSION="2026_OPPONENT_NEUTRAL_STRENGTH_HOME_ADVANTAGE_V1"
PRIOR_HOME_POINTS=2.5
HOME_RANGE=(0.,4.5)
HALF_LIFE_DAYS=21.
# Each school has only a handful of 2026 games. Large penalties collapse
# ratings toward zero so an otherwise reasonable +2.5 venue effect wins every
# prediction. An exploratory, predeclared stronger team-signal fit is tested
# here; it is NOT an independently validated production tuning.
TEAM_PENALTY=6.
HOME_PRIOR_PENALTY=160.
TRAVEL_PENALTY=120.
TRAVEL_KEYS=("away_minus_home_travel_1000mi","away_minus_home_abs_shift",
             "away_eastward_hours","away_body_clock_early_hours",
             "home_minus_away_rest_days")
MIN_GAMES=90
MIN_TRAVEL_GAMES=80
VENUE_SOURCE="VERIFIED_CITY_CENTROID_FROM_ESPN_GAME_VENUE"
def when(x):
    return dt.date.fromisoformat(x) if isinstance(x,str) else x

def _finite(x):
    if isinstance(x,bool) or x is None:return False
    try:return math.isfinite(float(x))
    except (ValueError,TypeError):return False

def travel_inputs(game):
    """Optional game-context inputs. Return None rather than treating absent as 0."""
    if game.get("venue_location_quality")!="CITY_CENTROID_NOT_STADIUM_COORDINATE":
        return None
    if game.get("travel_source")!="INFERRED_PRIOR_HOME_CITY_TO_GEOCODED_VENUE_CITY":
        return None
    nums={}
    for key in ("home_approx_straight_line_miles","away_approx_straight_line_miles",
                "home_timezone_shift_hours","away_timezone_shift_hours",
                "home_days_since_last_game","away_days_since_last_game",
                "away_body_clock_kickoff_hour"):
        val=game.get(key)
        if not _finite(val):return None
        nums[key]=float(val)
    if (any(nums[k]<0 for k in ("home_approx_straight_line_miles",
                               "away_approx_straight_line_miles",
                               "home_days_since_last_game","away_days_since_last_game"))
        or max(nums["away_approx_straight_line_miles"],nums["home_approx_straight_line_miles"])>6000
        or max(abs(nums["away_timezone_shift_hours"]),abs(nums["home_timezone_shift_hours"]))>7
        or not 0<=nums["away_body_clock_kickoff_hour"]<=24):
        raise ValueError("Travel input outside plausible geographic range")
    east=max(0.,nums["away_timezone_shift_hours"])
    result={
        "away_minus_home_travel_1000mi":
            (nums["away_approx_straight_line_miles"]-nums["home_approx_straight_line_miles"])/1000,
        "away_minus_home_abs_shift":
            abs(nums["away_timezone_shift_hours"])-abs(nums["home_timezone_shift_hours"]),
        "away_eastward_hours":east,
        "away_body_clock_early_hours":max(0.,12-nums["away_body_clock_kickoff_hour"]),
        "home_minus_away_rest_days":
            max(-7.,min(7.,nums["home_days_since_last_game"]-nums["away_days_since_last_game"]))}
    return result

def _records(rows,cutoff):
    day=when(cutoff)
    out=[];seen=set()
    for row in rows:
        d=when(row["date"])
        if d>=day:raise ValueError("Same-day or future result entered venue fit")
        gid=str(row["game_id"])
        if gid in seen:raise ValueError("Duplicate historical game")
        seen.add(gid)
        if row["home"]==row["away"]:raise ValueError("Same team on both sides")
        if (type(row.get("home_score")) not in (int,float) or
            type(row.get("away_score")) not in (int,float)):
            raise ValueError("Missing or nonnumeric verified final")
        if not _finite(row["home_score"]) or not _finite(row["away_score"]):
            raise ValueError("Nonfinite final")
        out.append(row)
    return out

def _weighted_fit(rows,cutoff,include_travel=False):
    if len(rows)<MIN_GAMES:raise ValueError("Insufficient past 2026 games")
    teams=sorted({r["home"] for r in rows}|{r["away"] for r in rows})
    ids={x:i for i,x in enumerate(teams)}
    width=len(teams)+1+(len(TRAVEL_KEYS) if include_travel else 0)
    X=np.zeros((len(rows),width))
    y=np.empty(len(rows))
    weights=np.empty(len(rows))
    travel_count=0
    for i,r in enumerate(rows):
        X[i,ids[r["home"]]]=1.
        X[i,ids[r["away"]]]=-1.
        X[i,len(teams)]=0. if r.get("neutral") is True else 1.
        y[i]=float(r["home_score"])-float(r["away_score"])-PRIOR_HOME_POINTS*X[i,len(teams)]
        age=(when(cutoff)-when(r["date"])).days
        weights[i]=math.exp2(-age/HALF_LIFE_DAYS)
        if include_travel:
            vals=r.get("audited_travel_features")
            if vals is None:raise ValueError("Incomplete historical travel training cohort")
            if r.get("travel_evidence_status")!=VENUE_SOURCE:
                raise ValueError("Unaudited travel cannot be used for training")
            if not all(_finite(vals.get(k)) for k in TRAVEL_KEYS):
                raise ValueError("Missing measured historical travel")
            X[i,len(teams)+1:]=[float(vals[k]) for k in TRAVEL_KEYS]
            travel_count+=1
    weights/=weights.mean()
    reg=np.zeros(width)
    reg[:len(teams)]=TEAM_PENALTY
    reg[len(teams)]=HOME_PRIOR_PENALTY
    if include_travel:reg[len(teams)+1:]=TRAVEL_PENALTY
    beta=np.linalg.solve(X.T@(weights[:,None]*X)+np.diag(reg),
                         X.T@(weights*y))
    home=float(np.clip(PRIOR_HOME_POINTS+beta[len(teams)],*HOME_RANGE))
    # Refitting team ratings and travel on the effective clamped home coefficient
    # prevents extreme intercepts from being hidden in the residual ratings.
    X_reduced=np.delete(X,len(teams),axis=1)
    y_reduced=np.array([float(r["home_score"])-float(r["away_score"])-
             home*(0. if r.get("neutral") is True else 1.) for r in rows])
    reduced_reg=np.delete(reg,len(teams))
    beta_reduced=np.linalg.solve(
        X_reduced.T@(weights[:,None]*X_reduced)+np.diag(reduced_reg),
        X_reduced.T@(weights*y_reduced))
    strengths=beta_reduced[:len(teams)]
    travel_params=beta_reduced[len(teams):] if include_travel else None
    return {"teams":{k:float(strengths[i]) for k,i in ids.items()},
            "home_field_points":home,"travel_coefficients":{
                k:float(v) for k,v in zip(TRAVEL_KEYS,travel_params)}
                if include_travel else None,
            "training_games":len(rows),"travel_training_games":travel_count,
            "model_version":VERSION+("_TRAVEL_ABLATION" if include_travel else ""),
            "status":STATUS,"betting_status":"PASS_UNVALIDATED",
            "historical_publication_authenticated":False}

def fit(rows,cutoff,travel=False):
    historical=_records(rows,cutoff)
    if travel:
        complete=[r for r in historical
                  if r.get("travel_evidence_status")==VENUE_SOURCE and
                  r.get("audited_travel_features") is not None]
        if len(complete)<MIN_TRAVEL_GAMES:
            return {"status":"PASS_INSUFFICIENT_HISTORICAL_TRAVEL",
                    "travel_training_games":len(complete),
                    "model_version":VERSION+"_TRAVEL_ABLATION",
                    "betting_status":"PASS_UNVALIDATED"}
        return _weighted_fit(complete,cutoff,include_travel=True)
    return _weighted_fit(historical,cutoff)

def _eligible_trip(game):
    vals=game.get("audited_travel_features")
    if game.get("travel_evidence_status")==VENUE_SOURCE and vals is not None:
        if not all(_finite(vals.get(k)) for k in TRAVEL_KEYS):
            raise ValueError("Incomplete audited game travel")
        return {k:float(vals[k]) for k in TRAVEL_KEYS}
    return travel_inputs(game)

def predict(model,game,travel=False):
    if model.get("status")!=STATUS:return None
    home,away=game["home"],game["away"]
    if home==away or home not in model["teams"] or away not in model["teams"]:
        return None
    is_neutral=game.get("neutral")
    if type(is_neutral) is not bool:return None
    neutral_margin=model["teams"][home]-model["teams"][away]
    h=0. if is_neutral else model["home_field_points"]
    impact=0.
    if travel:
        if model.get("travel_coefficients") is None:return None
        source=_eligible_trip(game)
        if source is None:return None
        impact=sum(model["travel_coefficients"][k]*source[k] for k in TRAVEL_KEYS)
    return {"predicted_home_margin":round(neutral_margin+h+impact,5),
            "neutral_strength_difference":round(neutral_margin,5),
            "home_field_points":h,"travel_adjustment":round(impact,5),
            "travel_evidence_observed":travel and source is not None,
            "model_version":model["model_version"],"status":STATUS,
            "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}

def compare(rows,cutoffs):
    """Strict date-exclusive folds and exact matched-game baseline comparisons.

    Travel fit intentionally FAILS CLOSED when no historically audited venue
    rows exist; no prospective venue value is backfilled into a past game.
    """
    results=[]
    for day in cutoffs:
        cutoff=when(day);end=cutoff+dt.timedelta(days=7)
        past=[r for r in rows if when(r["date"])<cutoff]
        test=[r for r in rows if cutoff<=when(r["date"])<end]
        if len(past)<MIN_GAMES or not test:continue
        fitted=fit(past,cutoff)
        travel_fit=fit(past,cutoff,travel=True)
        candidates={"venue_neutral_rating":[],"venue_plus_travel":[]}
        for r in test:
            actual=float(r["home_score"])-float(r["away_score"])
            regular=predict(fitted,r)
            if regular is not None:
                candidates["venue_neutral_rating"].append(
                    {"game_id":str(r["game_id"]),"pred":regular["predicted_home_margin"],
                     "actual":actual})
            if travel_fit.get("status")==STATUS:
                trip=predict(travel_fit,r,travel=True)
                if trip is not None:
                    candidates["venue_plus_travel"].append(
                        {"game_id":str(r["game_id"]),"pred":trip["predicted_home_margin"],
                         "actual":actual})
        stats={}
        for name,items in candidates.items():
            stats[name]={"games":len(items),"margin_mae":
                round(sum(abs(x["pred"]-x["actual"]) for x in items)/len(items),5)
                if items else None,"signed_bias":
                round(sum(x["pred"]-x["actual"] for x in items)/len(items),5)
                if items else None,"home_pick_fraction":
                round(sum(x["pred"]>0 for x in items)/len(items),5) if items else None,
                "game_ids":[x["game_id"] for x in items]}
        results.append({"cutoff":cutoff.isoformat(),"past_games":len(past),
                        "home_field_estimate":fitted["home_field_points"],
                        "travel_training_status":travel_fit["status"],
                        "models":stats})
    return {"status":STATUS,"season":2026,"model_promoted":False,
            "betting_status":"PASS_UNVALIDATED",
            "historical_pbp_publication_authenticated":False,
            "estimated_home_field_prior_points":PRIOR_HOME_POINTS,
            "folds":results}
def paired_comparison(games,advanced,cutoffs):
    """Research ablation: V03, recency and neutral-field rating on identical IDs."""
    from scripts.model_v03 import build_weekly_games,fit_ridge,predict as ridge_predict
    from scripts.home_bias_candidate import fit_candidate,predict_candidate
    from scripts.personnel_features import BASE_FIELDS
    weekly=build_weekly_games(games,advanced)
    known={str(r["game_id"]):r for r in games}
    enriched={str(r["game_id"]):r for r in weekly}
    if set(known)!=set(enriched):raise ValueError("Baseline ID mismatch")
    folds=[]
    for d in cutoffs:
        first=when(d);end=first+dt.timedelta(days=7)
        before=[r for r in weekly if when(r["date"])<first]
        complete=[r for r in before if r["home_games_prior"]>=1 and r["away_games_prior"]>=1]
        future=[r for r in weekly if first<=when(r["date"])<end
                and r["home_games_prior"]>=1 and r["away_games_prior"]>=1]
        if not future or len(complete)<MIN_GAMES:continue
        classic=fit_ridge(before,BASE_FIELDS)
        recency=fit_candidate(before,BASE_FIELDS,first)
        neutral=fit([known[str(r["game_id"])] for r in complete],first)
        travel_fit=fit([known[str(r["game_id"])] for r in complete],first,travel=True)
        baseline=ridge_predict(future,BASE_FIELDS,classic)[0][:,0]
        recent=predict_candidate(future,BASE_FIELDS,recency)
        rows=[]
        for i,r in enumerate(future):
            g=known[str(r["game_id"])]
            rating=predict(neutral,g)
            if rating is None:continue
            # Every candidate is evaluated on precisely the same games.
            rows.append({"game_id":str(r["game_id"]),
                "date":r["date"],"actual":float(r["home_score"]-r["away_score"]),
                "v03":float(baseline[i]),"recency":float(recent[i]),
                "neutral_rating":rating["predicted_home_margin"],
                "neutral_rating_component":rating["neutral_strength_difference"],
                "venue_adjustment":rating["home_field_points"]})
            if travel_fit.get("status")==STATUS:
                travel_prediction=predict(travel_fit,g,travel=True)
                if travel_prediction is not None:
                    rows[-1]["travel_prediction"]=travel_prediction["predicted_home_margin"]
        if not rows:continue
        metrics={}
        for k in ("v03","recency","neutral_rating"):
            n=len(rows);truth=[x["actual"] for x in rows]
            margin=[x[k] for x in rows]
            metrics[k]={"games":n,
               "margin_mae":round(sum(abs(y-a) for y,a in zip(margin,truth))/n,5),
               "signed_home_bias":round(sum(y-a for y,a in zip(margin,truth))/n,5),
               "su_accuracy":round(sum((y>0)==(a>0) for y,a in zip(margin,truth))/n,5),
               "home_pick_fraction":round(sum(y>0 for y in margin)/n,5)}
        travel_pairs=[r for r in rows if "travel_prediction" in r]
        travel_metrics={"games":len(travel_pairs),"available":len(travel_pairs)>0,
            "training_status":travel_fit["status"],
            "train_games":travel_fit.get("travel_training_games",0)}
        if travel_pairs:
            travel_metrics.update({
                "travel_model_mae":round(sum(abs(r["travel_prediction"]-r["actual"])
                              for r in travel_pairs)/len(travel_pairs),5),
                "same_game_neutral_rating_mae":round(sum(abs(r["neutral_rating"]-r["actual"])
                              for r in travel_pairs)/len(travel_pairs),5),
                "same_game_v03_mae":round(sum(abs(r["v03"]-r["actual"])
                              for r in travel_pairs)/len(travel_pairs),5)})
        folds.append({"cutoff":first.isoformat(),
            "travel_paired":travel_metrics,
            "training_games_all_v03":len(before),
            "training_games_dual_profile":len(complete),
            "home_field_points":round(neutral["home_field_points"],5),
            "metrics":metrics,"same_game_details":rows})
    aggregate={}
    for k in ("v03","recency","neutral_rating"):
        game_rows=[g for f in folds for g in f["same_game_details"]]
        if not game_rows:continue
        n=len(game_rows)
        aggregate[k]={"games":n,
            "margin_mae":round(sum(abs(r[k]-r["actual"]) for r in game_rows)/n,5),
            "signed_home_bias":round(sum(r[k]-r["actual"] for r in game_rows)/n,5),
            "su_accuracy":round(sum((r[k]>0)==(r["actual"]>0) for r in game_rows)/n,5),
            "home_pick_fraction":round(sum(r[k]>0 for r in game_rows)/n,5)}
    return {"status":STATUS,"research_only":True,"model_promoted":False,
        "betting_status":"PASS_UNVALIDATED",
        "historical_pbp_publication_authenticated":False,
        "no_historical_venue_timezones_attested":True,
        "travel_impact_trained":False,
        "scoring_system":"NEUTRAL_TEAM_RATINGS_PLUS_REGULARIZED_HOME_FIELD",
        "folds":folds,"aggregate":aggregate}

def run_paired(games_csv,advanced_csv,manifest,output,travel_history=None):
    from scripts.model_v03 import load_inputs
    games,advanced,_=load_inputs(games_csv,advanced_csv,manifest)
    cleaned=[]
    for g in games:
        v=str(g["neutral"]).strip().lower()
        if v not in ("true","false"):raise ValueError("Unknown neutral-site designation")
        cleaned.append({**g,"neutral":v=="true",
            "home_score":int(g["home_score"]),"away_score":int(g["away_score"])})
    games=cleaned
    if travel_history:
        historic=json.loads(Path(travel_history).read_text())
        if (historic.get("status")!="RETROSPECTIVE_2026_VENUE_TRAVEL_GEOGRAPHY_NOT_ASOF_ATTESTED"
            or historic.get("historical_location_published_before_games") is not False
            or historic.get("betting_status")!="PASS_UNVALIDATED"):
            raise ValueError("Untrusted historical travel metadata")
        idx={}
        for row in historic["rows"]:
            gid=str(row["game_id"])
            if gid in idx:raise ValueError("Duplicate historical travel slot")
            idx[gid]=row
        for g in games:
            extra=idx.get(str(g["game_id"]))
            if extra is None:continue
            if (g["home"],g["away"],g["date"],g["kickoff_utc"])!=(
                extra["home"],extra["away"],extra["date"],extra["kickoff_utc"]):
                raise ValueError("Historical travel/game identity mismatch")
            g["audited_travel_features"]=extra["audited_travel_features"]
            g["travel_evidence_status"]=extra["travel_evidence_status"]
    report=paired_comparison(games,advanced,
        [dt.date(2026,9,26)+dt.timedelta(days=7*i) for i in range(7)])
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":STATUS,"aggregate":report["aggregate"],
         "folds":len(report["folds"]),"model_promoted":False}))
    return report

def run(games_csv,output):
    import csv
    with open(games_csv,newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    cleaned=[]
    for r in rows:
        cleaned.append({**r,"home_score":int(r["home_score"]),
             "away_score":int(r["away_score"]),
             "neutral":str(r["neutral"]).lower()=="true"})
    report=compare(cleaned,
      [dt.date(2026,9,26)+dt.timedelta(days=7*i) for i in range(7)])
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":report["status"],
        "folds":len(report["folds"]),
        "games":sum(f["models"]["venue_neutral_rating"]["games"] for f in report["folds"]),
        "travel_ablation_heldout_games":
            sum(f["models"]["venue_plus_travel"]["games"] for f in report["folds"]),
        "model_promoted":False}))
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True);p.add_argument("--output",required=True)
    p.add_argument("--advanced");p.add_argument("--manifest")
    p.add_argument("--travel-history")
    a=p.parse_args()
    if bool(a.advanced)!=bool(a.manifest):p.error("Advanced + manifest are required together")
    if a.advanced:run_paired(a.games,a.advanced,a.manifest,a.output,a.travel_history)
    else:run(a.games,a.output)

"""V12R2 learned drive hazards: penalized likelihood, strictly historical data.

Stage 1 learns P(reach red zone | starting zone, offense, defense, dated
strength). Stage 2 learns conditional TD -> FG -> turnover hazards separately
for drives that did/did not reach the red zone. The ridge coefficients are
fitted from actual prior-week observed drives, not prescribed matchup boosts.

To learn V04-strength / dated-EPA coefficients, each training example uses
ONLY that game's original archived earlier-week V04 scoring projection and
dated scouting profile, never actual game outcomes as a model feature.
Games not present in the frozen V11 archive contribute league/team/zone
features but not fabricated V04/EPA scores.

This is retrospective research until upstream original 2026 first-publication
timestamps can be independently authenticated. No model promotion.
"""
import datetime as dt
import math
from collections import defaultdict

from scripts.v10_possession_sim import OUTCOMES, _zone, _drive_outcome, clamp

STATUS = "V12R2_CHRONOLOGICAL_RIDGE_REDZONE_DRIVE_HAZARDS_RESEARCH_ONLY"
TASKS = ("visit", "rz_td", "rz_fg", "rz_to", "nonrz_td", "nonrz_fg", "nonrz_to")
MIN_EXPOSURE = 16
ITERATIONS = 18
# Predeclared fixed effective prior exposures, not selected on held-out games.
PENALTIES = {"zone":10.0, "offense":35.0, "defense":35.0,
             "v04":35.0, "epa":45.0}
BASE_PRIOR = {"visit":.30, "rz_td":.55, "rz_fg":.35,
              "rz_to":.12, "nonrz_td":.035, "nonrz_fg":.11,
              "nonrz_to":.15}


def _logit(p):
    p = clamp(p, 1.e-5, 1-1.e-5)
    return math.log(p/(1-p))


def _sigmoid(x):
    if x >= 0:
        return 1/(1+math.exp(-x))
    e = math.exp(x)
    return e/(1+e)


def _predict(fitted,features):
    if not fitted["ready"]:
        return fitted["fallback"]
    z = fitted["intercept"]
    for key,value in features:
        z += fitted["weights"].get(key,0.)*value
    return clamp(_sigmoid(z),.002,.998)


def _penalty(feature):
    if feature.startswith("zone:"):return PENALTIES["zone"]
    if feature.startswith("offense:"):return PENALTIES["offense"]
    if feature.startswith("defense:"):return PENALTIES["defense"]
    if feature=="v04-score":return PENALTIES["v04"]
    if feature=="dated-epa":return PENALTIES["epa"]
    raise ValueError("Unregistered learned coefficient "+feature)


def _ridge_logit(rows,task):
    """Damped diagonal-Newton updates on Bernoulli log likelihood + L2.

    The same predeclared regularization is applied at every forecasting fold;
    no hyperparameter is chosen using target-game scores or future weeks.
    """
    n = len(rows)
    positives = sum(y for _,y in rows)
    prior = BASE_PRIOR[task]
    center = (positives + 12*prior)/(n+12)
    if n < MIN_EXPOSURE or positives==0 or positives==n:
        return {"ready":False,"fallback":center,"n":n,"positives":positives,
                "weights":{},"intercept":_logit(center)}
    intercept = _logit(center)
    weights = {}
    for features,_ in rows:
        for key,value in features:
            if value and key not in weights:weights[key]=0.
    # Adjust intercept separately and constrain coordinate steps. This avoids
    # unstable unpenalized sparse-team effects from quasi-separation.
    for _ in range(ITERATIONS):
        grad0=0.;hess0=.001
        gradient=defaultdict(float);hessian=defaultdict(float)
        for features,y in rows:
            p = _sigmoid(intercept+sum(weights[k]*v for k,v in features))
            err = y-p
            curvature = max(.002,p*(1-p))
            grad0 += err
            hess0 += curvature
            for key,value in features:
                gradient[key] += value*err
                hessian[key] += curvature*value*value
        intercept += clamp(.30*grad0/hess0,-.30,.30)
        intercept=clamp(intercept,-6.,6.)
        for key in weights:
            reg = _penalty(key)
            step=(gradient[key]-reg*weights[key])/(hessian[key]+reg)
            weights[key]=clamp(weights[key]+clamp(.35*step,-.25,.25),-2.5,2.5)
    return {"ready":True,"fallback":center,"n":n,
            "positives":positives,"intercept":intercept,"weights":weights,
            "iterations":ITERATIONS,"regularization":PENALTIES.copy()}


def _asof_features(row,side):
    """Training metadata is the historical prior game forecast, not hindsight."""
    data=row.get("v04",{})
    raw=data.get("home_points" if side=="home" else "away_points")
    if not isinstance(raw,(int,float)) or not math.isfinite(raw) or raw<0:
        return None,None
    strength=clamp(math.log((raw+7.)/31.),-1.5,1.5)
    scout=row.get("source_provenance",{}).get("weekly_recent_form",{})
    own=scout.get(side) or {}
    other=scout.get("away" if side=="home" else "home") or {}
    a,b=own.get("epa_off_adj"),other.get("epa_def_adj")
    if (isinstance(a,(int,float)) and math.isfinite(a) and
        isinstance(b,(int,float)) and math.isfinite(b)):
        return strength,clamp((a+b)*.5,-1.5,1.5)
    return strength,None


def _features(zone,offense,defense,strength=None,epa=None):
    row=[("zone:"+zone,1.),("offense:"+offense,1.),("defense:"+defense,1.)]
    if strength is not None:row.append(("v04-score",strength))
    if epa is not None:row.append(("dated-epa",epa))
    return tuple(row)


def _tasks(reached,event):
    """All labels only use reconciled source drive result and red-zone trip."""
    if event not in OUTCOMES:raise ValueError("Unknown drive result")
    labels=[]
    if reached:
        labels.append(("rz_td",int(event=="TD")))
        if event!="TD":
            labels.append(("rz_fg",int(event=="FG")))
        if event not in ("TD","FG"):
            labels.append(("rz_to",int(event=="TURNOVER")))
    else:
        labels.append(("nonrz_td",int(event=="TD")))
        if event!="TD":
            labels.append(("nonrz_fg",int(event=="FG")))
        if event not in ("TD","FG"):
            labels.append(("nonrz_to",int(event=="TURNOVER")))
    return labels


def train(source_games,frozen_archive,cutoff):
    """Strict original V04 weekly embargo: g.date < cutoff for EVERY label.

    Historical archive forecast for game G must itself have an earlier cutoff
    and the identical game date, matchup and ID. No metadata is invented.
    """
    day=dt.date.fromisoformat(cutoff)
    if day.year!=2026 or not isinstance(source_games,list):
        raise ValueError("Invalid source or 2026 weekly cutoff")
    archive={}
    for old in frozen_archive:
        gid=str(old["game_id"])
        if gid in archive:raise ValueError("Duplicate historical V04 forecast game")
        if not (old["cutoff"]<=old["date"]<
                (dt.date.fromisoformat(old["cutoff"])+dt.timedelta(days=7)).isoformat()):
            raise ValueError("Historical V04 forecast crosses football week")
        archive[gid]=old
    data={name:[] for name in TASKS}
    used=set();with_score=0;with_epa=0
    observed=[]
    for game in source_games:
        if game["date"]>=cutoff:continue
        if str(game["game_id"]) in used:raise ValueError("Duplicate earlier drive game")
        used.add(str(game["game_id"]))
        prev=archive.get(str(game["game_id"]))
        if prev is not None:
            if (prev["date"]!=game["date"] or prev["home"]!=game["home"]
                or prev["away"]!=game["away"] or prev["cutoff"]>game["date"]
                or prev["date"]>=cutoff):
                raise ValueError("Leaky or mismatched historical V04 metadata")
        counts={"home":0,"away":0}
        for d in game["drives"]:
            side=d["side"]
            if side not in ("home","away") or d["team"]!=game[side]:
                raise ValueError("Drive ownership failed source audit")
            opp=game["away" if side=="home" else "home"]
            counts[side]+=1
            zone=_zone(d["start_yards_to_goal"])
            if d["start_yards_to_goal"]<=20 and not d["red_zone_visited"]:
                raise ValueError("Drive starting in red zone cannot lack red zone visit")
            sc,epa=_asof_features(prev,side) if prev else (None,None)
            if sc is not None:with_score+=1
            if epa is not None:with_epa+=1
            x=_features(zone,d["team"],opp,sc,epa)
            reached=bool(d["red_zone_visited"])
            outcome=_drive_outcome(d)
            # Reaching RZ is deterministic for drives that started inside it.
            if zone!="red_zone":data["visit"].append((x,int(reached)))
            for name,label in _tasks(reached,outcome):
                data[name].append((x,label))
        observed.append({"game_id":str(game["game_id"]),"date":game["date"],
                         "home":game["home"],"away":game["away"],
                         "home_drives":counts["home"],"away_drives":counts["away"]})
    if len(observed)<35 or sum(len(g["drives"]) for g in source_games if g["date"]<cutoff)<200:
        return {"ready":False,"reason":"INSUFFICIENT_PRIOR_SOURCE_EXPOSURE",
                "games":len(observed),"cutoff":cutoff}
    fitted={name:_ridge_logit(data[name],name) for name in TASKS}
    return {"ready":True,"status":STATUS,"cutoff":cutoff,"source_games":len(observed),
            "prior_game_ids":sorted(used),"models":fitted,
            "observed_pace":observed,
            "feature_coverage":{"drives_with_original_v04":with_score,
                                "drives_with_dated_epa":with_epa,
                                "training_drives":sum(x["home_drives"]+x["away_drives"]
                                                      for x in observed)},
            "hyperparameters_fixed_pre_outcome":True,"model_promoted":False,
            "historical_source_first_publication_verified":False}


def probabilities(fit,side,zone,offense,opponent,v04_prior,dated_profile):
    if fit.get("status")!=STATUS or not fit.get("ready"):
        raise ValueError("Missing strictly historical ridge fit")
    if (side not in ("home","away") or
        zone not in ("own_deep","own_half","midfield","opponent_half","red_zone")):
        raise ValueError("Invalid drive position")
    own=dated_profile["teams"][side]["weekly_recent_form"]
    opp=dated_profile["teams"]["away" if side=="home" else "home"]["weekly_recent_form"]
    oa,od=own.get("epa_off_adj"),opp.get("epa_def_adj")
    epa=(clamp((oa+od)*.5,-1.5,1.5) if
         isinstance(oa,(int,float)) and isinstance(od,(int,float))
         and math.isfinite(oa) and math.isfinite(od) else None)
    pts=v04_prior["home_points" if side=="home" else "away_points"]
    strength=clamp(math.log((pts+7.)/31.),-1.5,1.5)
    features=_features(zone,offense,opponent,strength,epa)
    raw = fit["models"]
    visit=1. if zone=="red_zone" else _predict(raw["visit"],features)
    distributions={}
    for reached,prefix in ((True,"rz"),(False,"nonrz")):
        p_td=_predict(raw[prefix+"_td"],features)
        p_fg=_predict(raw[prefix+"_fg"],features)
        p_to=_predict(raw[prefix+"_to"],features)
        distributions[reached]={
            "TD":p_td,
            "FG":(1-p_td)*p_fg,
            "TURNOVER":(1-p_td)*(1-p_fg)*p_to,
            "EMPTY":(1-p_td)*(1-p_fg)*(1-p_to)}
        if abs(sum(distributions[reached].values())-1)>1e-9:
            raise AssertionError("Unnormalized trained score hazards")
    return {"reach_probability":visit,"conditional":distributions,
            "source_zone_drives":fit["feature_coverage"]["training_drives"],
            "historical_learned_probabilities":True}


def pace_profile(hazards,home,away):
    """Opponent-aware game possessions, with observed-only variance.

    Source pace is from game counts strictly before weekly cutoff. Avoid the
    old fixed {-2,-1,0,1,2} jitter. Sparse team evidence -> league prior.
    """
    if not hazards.get("ready"):raise ValueError("Missing pace fit")
    games=hazards["observed_pace"]
    home_counts=[g["home_drives"] if g["home"]==home else g["away_drives"]
                 for g in games if home in (g["home"],g["away"])]
    away_counts=[g["home_drives"] if g["home"]==away else g["away_drives"]
                 for g in games if away in (g["home"],g["away"])]
    league=[(g["home_drives"]+g["away_drives"])/2 for g in games]
    baseline=sum(league)/len(league)
    # An observed team's historical drives/game is both its pace/possession
    # opportunity and the pace an opposing defense has faced; no fictional
    # possessions are added. Shrink low-n teams to the league.
    def smooth(xs):
        return (sum(xs)+4*baseline)/(len(xs)+4)
    target=(smooth(home_counts)+smooth(away_counts))/2
    errors=[x-baseline for x in league]
    return {"expected_possessions_each":clamp(target,7.,18.),
            "historical_deviations":errors,"league_mean":baseline,
            "home_observed_games":len(home_counts),
            "away_observed_games":len(away_counts),
            "source_cutoff":hazards["cutoff"],
            "distribution_source":"EARLIER_REAL_GAME_POSSESSION_COUNTS"}

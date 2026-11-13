"""V14 spread/total probabilities from earlier OUT-OF-FOLD V14 score errors.

No bookmaker line is used to train scoring or uncertainty. Separate historical
ATS, OU probabilities and PASS/volume gates; no calibrated wagering EV claims.
"""
import math
from scripts.v13_v04_probabilities import crps

STATUS="V14_ATS_TOTAL_OOS_CALIBRATION_RESEARCH_ONLY"
PRIOR_PSEUDO_GAMES=80.0
MIN_PROSPECTIVE_PRICE_GAMES=100
MIN_MODEL_EDGE_POINTS=5.0
PUSH_EPS=1.e-8


def _finite(x):
    return type(x) in (float,int) and math.isfinite(x)


def fit(prior_rows,cutoff,prior_margin_sd=16.5,prior_total_sd=17.0):
    if not isinstance(prior_rows,list) or not isinstance(cutoff,str):
        raise ValueError("Original weekly cutoff and OOS records required")
    if not all(_finite(x) and 8<=x<=30 for x in
               (prior_margin_sd,prior_total_sd)):
        raise ValueError("Bad V13 historical uncertainty prior")
    ids=set();merrs=[];terrs=[];weeks=set()
    for row in prior_rows:
        gid=str(row.get("game_id",""))
        if not gid or gid in ids:raise ValueError("Duplicate prior OOS game")
        ids.add(gid)
        if (row.get("cutoff","")>=cutoff or row.get("date","")>=cutoff or
            row.get("source_first_publication_authenticated") is not False):
            raise ValueError("Same-week or unauthenticated source cannot enter V14 calibration")
        pred=row.get("v14_forecast")
        if (not isinstance(pred,dict) or pred.get("model_promoted") is not False or
            pred.get("source_cutoff_exclusive")!=row["cutoff"]):
            raise ValueError("V14 residual not from its earlier held-out week")
        hm,ta=pred.get("margin"),pred.get("total")
        h,a=row.get("final_home"),row.get("final_away")
        if not all(_finite(x) for x in (hm,ta)) or type(h) is not int or type(a) is not int:
            raise ValueError("Unverified prior score")
        merrs.append(h-a-hm);terrs.append(h+a-ta)
        weeks.add(row["cutoff"])
    n=len(merrs)
    # Fixed, conservative error prior prevents sparse calibration from
    # producing implausibly tight intervals.
    sm=math.sqrt((PRIOR_PSEUDO_GAMES*prior_margin_sd**2+
        sum(x*x for x in merrs))/(PRIOR_PSEUDO_GAMES+n))
    st=math.sqrt((PRIOR_PSEUDO_GAMES*prior_total_sd**2+
        sum(x*x for x in terrs))/(PRIOR_PSEUDO_GAMES+n))
    return {"status":STATUS,"cutoff":cutoff,"earlier_oos_games":n,
        "earlier_oos_weeks":len(weeks),
        "margin_sd":max(9.,min(30.,sm)),
        "total_sd":max(9.,min(30.,st)),
        "market_lines_used_in_calibration":False,
        "historical_first_publication_authenticated":False,
        "model_promoted":False}


def _cdf(x):
    return .5*math.erfc(-x/math.sqrt(2))


def predict(forecast,calibration,market=None):
    if (forecast.get("model_promoted") is not False or
        calibration.get("status")!=STATUS or
        forecast.get("source_cutoff_exclusive")!=calibration.get("cutoff") or
        calibration.get("market_lines_used_in_calibration") is not False):
        raise ValueError("Inconsistent earlier-week market calibration")
    m,t=forecast["margin"],forecast["total"]
    sm,st=calibration["margin_sd"],calibration["total_sd"]
    sp=line=None
    if market is not None:
        if not isinstance(market,dict):raise ValueError("Bookmaker quote required")
        sp=market.get("home_spread")
        line=market.get("total")
        if sp is not None and (not _finite(sp) or abs(sp)>80):raise ValueError("Bad spread")
        if line is not None and (not _finite(line) or not 0<line<160):raise ValueError("Bad total")
    win=_cdf(m/sm)
    cover=_cdf((m+sp)/sm) if sp is not None else None
    over=_cdf((t-line)/st) if line is not None else None
    # Research pass gates are conservative and not evidence of +EV.
    ats_side=(("HOME" if m+sp>0 else "AWAY") if
              sp is not None and abs(m+sp)>=MIN_MODEL_EDGE_POINTS else "PASS")
    ou_side=(("OVER" if t>line else "UNDER") if
              line is not None and abs(t-line)>=MIN_MODEL_EDGE_POINTS else "PASS")
    return {"status":STATUS,"home_win_probability":win,
        "home_cover_probability":cover,"over_probability":over,
        "margin_sd":sm,"total_sd":st,
        "margin_p10":m-1.2815515655446004*sm,
        "margin_p90":m+1.2815515655446004*sm,
        "total_p10":t-1.2815515655446004*st,
        "total_p90":t+1.2815515655446004*st,
        "ats_research_side":ats_side,"totals_research_side":ou_side,
        "ats_research_selection_not_betting_ev":True,
        "source_market_quote_present":sp is not None or line is not None,
        "model_promoted":False,"betting_status":"PASS_UNVALIDATED",
        "safe_for_betting":False}


def brier(observations):
    if not observations:return {"n":0,"brier":None,"log_loss":None,"ece":None}
    n=len(observations);val=0.;log=0.;bins={}
    for p,label in observations:
        if not _finite(p) or not 0<=p<=1 or label not in (0,1):
            raise ValueError("Bad calibrated score label")
        val+=(p-label)**2
        p2=min(1-1e-9,max(1e-9,p))
        log-=label*math.log(p2)+(1-label)*math.log(1-p2)
        key=min(9,int(p*10));bins.setdefault(key,[]).append((p,label))
    ece=sum(len(group)/n*abs(sum(p for p,y in group)/len(group)-
        sum(y for p,y in group)/len(group))
        for group in bins.values())
    return {"n":n,"brier":round(val/n,6),"log_loss":round(log/n,6),
        "ece":round(ece,6)}

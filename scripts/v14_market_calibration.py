"""V14 independent ATS and total calibration, from previously settled weeks.

No point model fits sportsbook odds. A distinct low-dimensional Platt-style
adjustment learns probability RELIABILITY from observed prior-game quotes and
labels only, strongly penalized toward identity. No quoted market line, no
cover/over probability. No implied expected value without authenticated prices.
"""
import math

STATUS="V14_PREVIOUS_WEEKS_ATS_TOTAL_PROBABILITY_CALIBRATION"
MIN_QUOTES=30
PENALTY_BIAS=75.
PENALTY_SLOPE=140.
PASS_THRESHOLD=.58


def cdf(z):
    return .5*math.erfc(-z/math.sqrt(2.))


def _logit(p):
    p=max(1e-6,min(1.-1e-6,p))
    return math.log(p/(1.-p))


def _sigmoid(z):
    if z>=0:return 1./(1.+math.exp(-z))
    x=math.exp(z)
    return x/(1.+x)


def _finite(v):
    return type(v) in (int,float) and math.isfinite(v)


def raw_probability(mean,sd,line,kind):
    if not all(_finite(x) for x in (mean,sd,line)) or not 5<=sd<=35:
        raise ValueError("V14 invalid line or predictive uncertainty")
    if kind=="ats":
        return cdf((mean+line)/sd)
    if kind=="total":
        return cdf((mean-line)/sd)
    if kind=="winner":
        return cdf(mean/sd)
    raise ValueError("Unknown calibrated probability type")


def _fit_label(rows,kind,cutoff):
    pts=[]
    for g in rows:
        if not g.get("cutoff") or g["cutoff"]>=cutoff or g["date"]>=cutoff:
            raise ValueError("Future/same-week bookmaker outcome training leakage")
        quote=g["market"].get("home_spread" if kind=="ats" else "total")
        if quote is None:continue
        if not _finite(quote):
            raise ValueError("Invalid historical bookmaker observation")
        if not g["market"].get("provider"):
            raise ValueError("Unattributed historical bookmaker quote")
        margin=g["final_home"]-g["final_away"]
        total=g["final_home"]+g["final_away"]
        y=(margin+quote) if kind=="ats" else (total-quote)
        if y==0:continue  # pushes excluded; never counted as wins
        base=g["predictions"]["prior_variance"]
        pred=base["margin_mean"] if kind=="ats" else base["total_mean"]
        sd=base["margin_sd"] if kind=="ats" else base["total_sd"]
        raw=raw_probability(pred,sd,quote,kind)
        pts.append((_logit(raw),int(y>0)))
    if len(pts)<MIN_QUOTES:
        return {"ready":False,"n":len(pts),"bias":0.,"slope":1.}
    bias=0.;delta=0.
    # Two parameters, fixed ridge prior toward identity (bias=0,slope=1).
    # Penalized Newton, no lookahead or target-game optimization.
    for _ in range(16):
        g0=-PENALTY_BIAS*bias
        g1=-PENALTY_SLOPE*delta
        h00=PENALTY_BIAS
        h11=PENALTY_SLOPE
        h01=0.
        for x,y in pts:
            p=_sigmoid(bias+(1+delta)*x)
            v=p*(1-p)
            g0+=y-p;g1+=x*(y-p)
            h00+=v;h11+=x*x*v;h01+=x*v
        det=h00*h11-h01*h01
        if det<=0:raise ValueError("V14 reliability system not positive definite")
        a=(h11*g0-h01*g1)/det
        b=(h00*g1-h01*g0)/det
        bias=max(-.7,min(.7,bias+max(-.15,min(.15,a))))
        delta=max(-.40,min(.40,delta+max(-.12,min(.12,b))))
    return {"ready":True,"n":len(pts),"bias":round(bias,8),
            "slope":round(1+delta,8),"fixed_bias_penalty":PENALTY_BIAS,
            "fixed_slope_penalty":PENALTY_SLOPE}


def fit(prior,cutoff):
    if not isinstance(prior,list) or not isinstance(cutoff,str):
        raise ValueError("V14 missing earlier-book calibration data")
    return {"status":STATUS,"cutoff_exclusive":cutoff,
            "ats":_fit_label(prior,"ats",cutoff),
            "total":_fit_label(prior,"total",cutoff),
            "training_market_not_used_for_scores":True,
            "source_first_publication_authenticated":False,
            "model_promoted":False}


def project(mean_margin,mean_total,sd_margin,sd_total,market,calibration,cutoff):
    if (calibration.get("status")!=STATUS or
        calibration.get("cutoff_exclusive")!=cutoff or
        calibration.get("model_promoted") is not False):
        raise ValueError("V14 calibration from incorrect week")
    result={"home_win":raw_probability(mean_margin,sd_margin,0.,"winner"),
            "home_cover_raw":None,"home_cover_calibrated":None,
            "over_raw":None,"over_calibrated":None,
            "home_cover_choice":"PASS","total_choice":"PASS",
            "confidence_threshold":PASS_THRESHOLD,
            "reliability_requires_future_validation":True,
            "model_promoted":False,"safe_for_betting":False}
    if market is None:return result
    if not isinstance(market,dict):raise ValueError("Market must be observed map")
    for kind,key,mean,sd in (
        ("ats","home_spread",mean_margin,sd_margin),
        ("total","total",mean_total,sd_total)):
        line=market.get(key)
        if line is None:continue
        if not market.get("provider"):
            raise ValueError("No authenticated bookmaker source attribution")
        raw=raw_probability(mean,sd,line,kind)
        fitted=calibration[kind]
        cal=_sigmoid(fitted["bias"]+fitted["slope"]*_logit(raw))
        pre="home_cover" if kind=="ats" else "over"
        result[pre+"_raw"]=round(raw,7)
        result[pre+"_calibrated"]=round(cal,7)
        if kind=="ats":
            result["home_cover_choice"]=(
                "HOME" if cal>=PASS_THRESHOLD else
                "AWAY" if cal<=1-PASS_THRESHOLD else "PASS")
        else:
            result["total_choice"]=(
                "OVER" if cal>=PASS_THRESHOLD else
                "UNDER" if cal<=1-PASS_THRESHOLD else "PASS")
    return result

"""V13: coherent V04-centered predictive distributions, source-gated research.

The new model does NOT replace V04 team/matchup score strengths with fabricated
possessions. It adds probabilistic margin and total forecasts using only prior
held-out V04 errors, with a conservative predeclared league error prior. A
separate 10%-possession and bias-correction research ablation is never an
automatic promotion. Historical source-publication time remains unauthenticated
for the retrospective 2026 cohort; prospective use requires frozen receipts.

Gaussian residual tails approximate scores, not exact scoreline frequencies,
and normal probabilities are NOT bookmaker value or profitable bets.
"""
import math

STATUS="V13_V04_ANCHORED_PROBABILITIES_RESEARCH_ONLY"
BASE_MARGIN_SD=16.5
BASE_TOTAL_SD=17.0
BASE_EFFECTIVE_GAMES=70.0
BIAS_PRIOR_GAMES=60.0
MIN_SD=8.0
MAX_SD=30.0
Z80=1.2815515655446004
VARIANTS=("fixed","prior_variance","v11_width","prior_bias","blend10")
V04_MODEL="V04_INDEPENDENT_OPPONENT_ADJUSTED_SCORES_RESEARCH_ONLY"
V04_STATUS="SOURCE_OBSERVED_DIRECT_TEAM_SCORE_MODEL_RESEARCH_ONLY"


def _finite(x):
    return type(x) in (float,int) and math.isfinite(x)


def scores(row,site=False):
    """Validate canonical V04 scores, without reading results or future games."""
    if not isinstance(row,dict):
        raise ValueError("Missing source-bound V04 score")
    if site and (row.get("model")!=V04_MODEL or row.get("status")!=V04_STATUS
        or row.get("model_promoted") is not False
        or row.get("direct_scoring_fit_uses_v03_total") is not False
        or row.get("no_market_lines_in_training") is not True):
        raise ValueError("Untrusted current V04 independent score provenance")
    h=row.get("home_points")
    a=row.get("away_points")
    m=row.get("home_margin",row.get("margin"))
    t=row.get("total_points",row.get("total"))
    if (not all(_finite(v) for v in (h,a,m,t))
        or not (0<=h<=130 and 0<=a<=130 and 0<=t<=160)
        or abs(h-a-m)>.06 or abs(h+a-t)>.06):
        raise ValueError("Invalid or incoherent original V04 projection")
    return {"home_points":float(h),"away_points":float(a),
            "margin":float(m),"total":float(t)}


def _cdf(z):
    return .5*math.erfc(-z/math.sqrt(2))


def _pdf(z):
    return math.exp(-.5*z*z)/math.sqrt(2*math.pi)


def crps(observed,mean,sd):
    """Exact CRPS for a normal predictive distribution at a real score."""
    if not all(_finite(x) for x in (observed,mean,sd)) or sd<=0:
        raise ValueError("Invalid continuous predictive score")
    z=(observed-mean)/sd
    return sd*(z*(2*_cdf(z)-1)+2*_pdf(z)-1/math.sqrt(math.pi))


def fit_uncertainty(prior,cutoff):
    """Use previous COMPLETE OUT-OF-SAMPLE forecast weeks, never same-week labels.

    Input rows must have canonical saved V04 source scores and real finals.
    This checks game-date chronology, NOT historical first-publication; an
    independent source-time gate is necessary for production eligibility.
    """
    if not isinstance(cutoff,str) or len(cutoff)!=10:
        raise ValueError("Original weekly cutoff required")
    if not isinstance(prior,list):
        raise ValueError("Earlier holdouts must be a list")
    seen=set();rm=[];rt=[];weeks=set()
    for g in prior:
        if not isinstance(g,dict) or not str(g.get("game_id","")):
            raise ValueError("Historical V04 game identity missing")
        gid=str(g["game_id"])
        if gid in seen:raise ValueError("Duplicate historical V04 holdout")
        seen.add(gid)
        w=g.get("cutoff")
        if not isinstance(w,str) or w>=cutoff or len(w)!=10:
            raise ValueError("Same-week or future result cannot calibrate V13")
        if not isinstance(g.get("date"),str) or g["date"]>=cutoff:
            raise ValueError("Uncompleted or same-day historical game")
        v=scores(g.get("v04"))
        h=g.get("final_home");a=g.get("final_away")
        if type(h) is not int or type(a) is not int or not (0<=h<=150 and 0<=a<=150):
            raise ValueError("Historical final score not independently verified")
        rm.append((h-a)-v["margin"])
        rt.append((h+a)-v["total"])
        weeks.add(w)
    n=len(rm)
    # Effective league priors avoid unstable small-week optimizers and
    # are defined before seeing the 2026 held-out target scores.
    sigma_m=math.sqrt((BASE_EFFECTIVE_GAMES*BASE_MARGIN_SD**2+
                      sum(v*v for v in rm))/(BASE_EFFECTIVE_GAMES+n))
    sigma_t=math.sqrt((BASE_EFFECTIVE_GAMES*BASE_TOTAL_SD**2+
                      sum(v*v for v in rt))/(BASE_EFFECTIVE_GAMES+n))
    bm=max(-3.,min(3.,sum(rm)/(BIAS_PRIOR_GAMES+n)))
    bt=max(-3.,min(3.,sum(rt)/(BIAS_PRIOR_GAMES+n)))
    return {"status":STATUS,"cutoff_exclusive":cutoff,"earlier_games":n,
            "earlier_weeks":len(weeks),"prior_game_ids":sorted(seen),
            "margin_sd":max(MIN_SD,min(MAX_SD,sigma_m)),
            "total_sd":max(MIN_SD,min(MAX_SD,sigma_t)),
            "margin_bias_correction":bm,"total_bias_correction":bt,
            "scored_history_first_publication_verified":False,
            "past_oos_games_only":True,"promoted":False}


def predict(v04,calibration,cutoff,variant="prior_variance",
            earlier_v11_pace=None,market=None,site=False):
    """Produce V04-scored win, margin, total and probability bands.

    Critical: the main V13 variant NEVER adjusts V04 mean scores.
    V11 odds/lines are not needed for the primary probability overlay.
    """
    if variant not in VARIANTS:
        raise ValueError("Unknown V13 research variant")
    v=scores(v04,site=site)
    if (not isinstance(calibration,dict) or calibration.get("status")!=STATUS
        or calibration.get("cutoff_exclusive")!=cutoff
        or calibration.get("past_oos_games_only") is not True
        or calibration.get("promoted") is not False):
        raise ValueError("V13 calibration is not from earlier source-aligned games")
    sm=BASE_MARGIN_SD if variant=="fixed" else calibration["margin_sd"]
    st=BASE_TOTAL_SD if variant=="fixed" else calibration["total_sd"]
    mm=v["margin"];mt=v["total"]
    if variant=="prior_bias":
        mm+=calibration["margin_bias_correction"]
        mt+=calibration["total_bias_correction"]
    if variant in ("blend10","v11_width"):
        if (not isinstance(earlier_v11_pace,dict) or
            earlier_v11_pace.get("cutoff")!=cutoff or
            earlier_v11_pace.get("game_id") in (None,"")):
            raise ValueError("V11 component lacks original weekly source identity")
        if variant=="blend10":
            if not all(_finite(earlier_v11_pace.get(k)) for k in ("margin","total")):
                raise ValueError("Unverified V11 pace score")
            mm=.90*mm+.10*earlier_v11_pace["margin"]
            mt=.90*mt+.10*earlier_v11_pace["total"]
        else:
            if not all(_finite(earlier_v11_pace.get(k)) for k in ("margin_width","total_width")):
                raise ValueError("Unverified held-out V11 probability interval")
            sm=max(MIN_SD,min(MAX_SD,earlier_v11_pace["margin_width"]/(2*Z80)))
            st=max(MIN_SD,min(MAX_SD,earlier_v11_pace["total_width"]/(2*Z80)))
    if not (MIN_SD<=sm<=MAX_SD and MIN_SD<=st<=MAX_SD):
        raise ValueError("Malformed predictive uncertainty")
    p_home=_cdf(mm/sm)
    p_ats=p_over=None
    if market is not None:
        if not isinstance(market,dict):
            raise ValueError("No independently observed market quote")
        sp=market.get("home_spread")
        tot=market.get("total")
        if _finite(sp) and abs(sp)<=80:
            p_ats=_cdf((mm+sp)/sm)
        if _finite(tot) and 1<=tot<=150:
            p_over=_cdf((mt-tot)/st)
    return {
        "status":STATUS,"variant":variant,
        "scoring_foundation":"UNCHANGED_V04" if variant in
            ("fixed","prior_variance","v11_width") else "V04_EXPERIMENTAL_ADJUSTMENT",
        "v04_mean_scores_unchanged":variant in ("fixed","prior_variance","v11_width"),
        "home_points_mean":round((mt+mm)/2,5),
        "away_points_mean":round((mt-mm)/2,5),
        "margin_mean":round(mm,5),"total_mean":round(mt,5),
        "margin_sd":round(sm,6),"total_sd":round(st,6),
        "home_win_probability":round(p_home,7),
        "home_cover_probability":round(p_ats,7) if p_ats is not None else None,
        "over_probability":round(p_over,7) if p_over is not None else None,
        "margin_p10":round(mm-Z80*sm,4),"margin_p90":round(mm+Z80*sm,4),
        "total_p10":round(mt-Z80*st,4),"total_p90":round(mt+Z80*st,4),
        "calibration_earlier_games":calibration["earlier_games"],
        "calibration_earlier_weeks":calibration["earlier_weeks"],
        "calibration_cutoff_exclusive":cutoff,
        "historical_source_publication_authenticated":False,
        "model_promoted":False,"safe_for_betting":False,
        "calibration_prospectively_proven":False,
        "betting_status":"PASS_UNVALIDATED"}

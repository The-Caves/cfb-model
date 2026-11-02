"""Out-of-sample V05 interval diagnostics from *earlier* holdout weeks only.

This diagnostic is not probabilistic certainty or an ATS win probability.
Historic score-feed release times cannot yet be independently reconstructed.
"""
import math

STATUS="V05_PAST_HOLDOUT_ABSOLUTE_RESIDUAL_INTERVAL_RESEARCH_ONLY"
MIN_CALIBRATION_GAMES=35
MIN_CALIBRATION_WEEKS=2
NOMINAL_COVERAGE=.80


def _value(x):
    return type(x) in (int,float) and math.isfinite(x)


def fit(prior,cutoff,variant="v05_full"):
    """Only earlier-week OOS predictions, never same-week labels or fit residuals."""
    if not isinstance(prior,list):
        raise ValueError("Calibration prior must be a list")
    dates=set()
    ids=set()
    errors_m=[]
    errors_t=[]
    for row in prior:
        date=row["cutoff"]
        if not isinstance(date,str) or date>=cutoff:
            raise ValueError("Contemporaneous or future calibration result")
        gid=str(row["game_id"])
        if gid in ids:
            raise ValueError("Duplicate calibration game")
        ids.add(gid)
        dates.add(date)
        target_m=row.get("actual_margin")
        target_t=row.get("actual_total")
        pred_m=row.get(variant+"_margin")
        pred_t=row.get(variant+"_total")
        if not all(_value(z) for z in (target_m,target_t,pred_m,pred_t)):
            raise ValueError("Untrusted calibration residual")
        errors_m.append(abs(target_m-pred_m))
        errors_t.append(abs(target_t-pred_t))
    n=len(prior)
    if n<MIN_CALIBRATION_GAMES or len(dates)<MIN_CALIBRATION_WEEKS:
        return None
    # Higher discrete quantile is intentionally conservative with ties.
    def conformal(vals):
        ordered=sorted(vals)
        index=min(n-1,math.ceil((n+1)*NOMINAL_COVERAGE)-1)
        return float(ordered[index])
    return {"status":STATUS,"calibrated_from_games":n,
            "calibrated_from_weeks":len(dates),
            "nominal_coverage":NOMINAL_COVERAGE,
            "margin_radius":round(conformal(errors_m),5),
            "total_radius":round(conformal(errors_t),5),
            "calibration_cutoff_exclusive":cutoff,
            "calendar_time_exchangeability_unverified":True,
            "only_prior_oos_errors":True,"safe_for_betting":False}


def evaluate(rows,calibration,variant="v05_full"):
    if calibration is None:
        return {"calibrated_games":0,"margin_coverage":None,
                "total_coverage":None,"mean_margin_width":None,
                "mean_total_width":None}
    m=calibration["margin_radius"]
    t=calibration["total_radius"]
    for r in rows:
        if r["cutoff"]<calibration["calibration_cutoff_exclusive"]:
            raise ValueError("Calibration evaluated on previously known outcomes")
    n=len(rows)
    if not n:return {"calibrated_games":0,"margin_coverage":None,
                      "total_coverage":None,"mean_margin_width":None,
                      "mean_total_width":None}
    hits_m=sum(abs(r[variant+"_margin"]-r["actual_margin"])<=m for r in rows)
    hits_t=sum(abs(r[variant+"_total"]-r["actual_total"])<=t for r in rows)
    return {"calibrated_games":n,"margin_coverage":round(hits_m/n,5),
            "total_coverage":round(hits_t/n,5),
            "mean_margin_width":round(2*m,4),
            "mean_total_width":round(2*t,4)}

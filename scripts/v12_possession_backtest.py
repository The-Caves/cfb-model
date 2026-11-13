"""V12 same-cohort backtest versus frozen V04 and V11, research only.

Uses V11 original weekly dates, real-drive ledger and as-of reconstructed V04
scores. Hypothetical ATS/O-U directions require actual archived pregame quotes.
Retrospective source first-publication timing is NOT independently authenticated.
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from scripts.possession_drive_ingest import STATUS as DRIVE_STATUS
from scripts.v10_possession_backtest import _metric
from scripts.v10_possession_sim import advanced_index, fit
from scripts.v11_dated_profile_bridge import bridge
from scripts.v11_dated_profile_backtest import STATUS as V11_STATUS
from scripts.v12_possession_sim import STATUS, fit_v12, simulate

REPORT="V12_SAME_WEEKLY_CUTOFF_OPPONENT_RZ_TURNOVER_PAIRED_RESEARCH_ONLY"
VERSIONS=("v04","v11_dated_opponent_epa","v12_opponent_rz_turnover")


def _crps(draws,observed):
    """Exact empirical CRPS: mean error minus half within-draw distance."""
    if not draws:raise ValueError("Empty Monte Carlo sample")
    ordered=sorted(draws)
    n=len(ordered)
    err=sum(abs(x-observed) for x in ordered)/n
    spread=sum((2*i-n+1)*x for i,x in enumerate(ordered))/(n*n)
    return max(0.,err-spread)


def _reliability(items,groups=10):
    """Brier, log loss and grouped reliability; no fictional line observations."""
    if not items:return {"n":0,"brier":None,"log_loss":None,"ece":None,"bins":[]}
    bins=[]
    for i in range(groups):
        sub=[(p,y) for p,y in items if min(groups-1,int(p*groups))==i]
        if sub:
            bins.append({"lo":i/groups,"hi":(i+1)/groups,
                         "n":len(sub),
                         "forecast":round(sum(p for p,y in sub)/len(sub),5),
                         "observed":round(sum(y for p,y in sub)/len(sub),5)})
    brier=sum((p-y)**2 for p,y in items)/len(items)
    ll=-sum(y*math.log(max(1e-8,min(1-1e-8,p)))+
            (1-y)*math.log(max(1e-8,min(1-1e-8,1-p)))
            for p,y in items)/len(items)
    ece=sum(b["n"]*abs(b["forecast"]-b["observed"]) for b in bins)/len(items)
    return {"n":len(items),"brier":round(brier,6),
            "log_loss":round(ll,6),"ece":round(ece,6),"bins":bins}


def _distribution_grade(rows):
    if not rows:return {"games":0}
    summary={}
    for name,metric,key in (("margin","margin","final_margin"),
                            ("total","total","final_total")):
        scores=[r["calibration"][name] for r in rows]
        summary[name]={
            "games":len(rows),
            "crps":round(sum(s["crps"] for s in scores)/len(scores),5),
            "empirical_p10_p90_coverage":round(
                sum(s["within_80pct_interval"] for s in scores)/len(scores),5),
            "mean_p10_p90_width":round(
                sum(s["width"] for s in scores)/len(scores),4)}
    winner=[(r["probabilities"]["home_win"],
             int(r["final_home"]>r["final_away"])) for r in rows
             if r["final_home"]!=r["final_away"]]
    ats=[(r["probabilities"]["home_cover"],
          int(r["final_home"]-r["final_away"]+r["market"]["home_spread"]>0))
         for r in rows if r["probabilities"]["home_cover"] is not None
         and r["final_home"]-r["final_away"]+r["market"]["home_spread"]!=0]
    ou=[(r["probabilities"]["over"],
         int(r["final_home"]+r["final_away"]>r["market"]["total"]))
        for r in rows if r["probabilities"]["over"] is not None
        and r["final_home"]+r["final_away"]!=r["market"]["total"]]
    summary["winner"]=_reliability(winner)
    summary["ats_home_cover"]=_reliability(ats)
    summary["total_over"]=_reliability(ou)
    return summary


def evaluate(archive,source,advanced,profiles,trials=2000,min_past=35):
    if (archive.get("status")!=V11_STATUS or archive.get("model_promoted") is not False
        or archive.get("historical_source_first_publication_verified") is not False
        or len(archive.get("games",[]))!=archive.get("matched_games") or
        not archive["games"] or
        source.get("status")!=DRIVE_STATUS or
        source.get("historical_pregame_publication_times_verified") is not False or
        source.get("games_accepted")!=387 or
        len(source.get("games",[]))!=387):
        raise ValueError("Historical source cohort not the frozen V11 same-week cohort")
    seen=set();rows=[];skips=Counter()
    if set(profiles["profiles"])!={str(g["game_id"]) for g in archive["games"]}:
        raise ValueError("V12 dated profile target mismatch")
    for old in archive["games"]:
        gid=str(old["game_id"])
        if gid in seen:raise ValueError("Duplicate target")
        seen.add(gid)
        cutoff=old["cutoff"]
        target={"game_id":gid,"date":cutoff,"home":old["home"],"away":old["away"]}
        prior=old["v04"]
        v04={"source":"EARLIER_FOLD_V04","game_id":gid,
             "asof_cutoff":cutoff,"home_points":prior["home_points"],
             "away_points":prior["away_points"]}
        model=fit(source["games"],advanced,target,min_games=min_past)
        if not model["ready"]:
            skips[model["reason"]]+=1
            continue
        context=fit_v12(model,source["games"],v04,profiles["profiles"][gid])
        seed=int(hashlib.sha256(("v11|"+gid).encode()).hexdigest()[:16],16)
        result=simulate(context,trials=trials,seed=seed)
        m=old["final_home"]-old["final_away"]
        total=old["final_home"]+old["final_away"]
        margin=result.pop("margin_draws")
        sums=result.pop("total_draws")
        probs={"home_win":result["home_win_probability"],"home_cover":None,
               "over":None}
        sp=old["market"].get("home_spread")
        line=old["market"].get("total")
        if sp is not None:
            probs["home_cover"]=sum(x+sp>0 for x in margin)/len(margin)
        if line is not None:
            probs["over"]=sum(x>line for x in sums)/len(sums)
        cal={}
        for key,draws,actual in (("margin",margin,m),("total",sums,total)):
            values=sorted(draws)
            lo=values[int((len(values)-1)*.1)]
            hi=values[int((len(values)-1)*.9)]
            cal[key]={"crps":_crps(draws,actual),
                      "within_80pct_interval":int(lo<=actual<=hi),
                      "width":hi-lo,"p10":lo,"p90":hi}
        row={k:old[k] for k in
             ("game_id","home","away","date","cutoff","kickoff_utc",
              "final_home","final_away","market")}
        row["v04"]=old["v04"]
        row["simulations"]={
            "v11_dated_opponent_epa":old["simulations"]["v11_dated_opponent_epa"],
            "v12_opponent_rz_turnover":{
                "margin":result["home_margin_mean"],
                "total":result["total_mean"],
                "home_points":result["home_points_mean"],
                "away_points":result["away_points_mean"],
                "home_win_probability":result["home_win_probability"]}}
        row["distribution_summary"]={k:v for k,v in result.items()
                                      if k not in ("sample_possessions",)}
        row["probabilities"]=probs
        row["calibration"]=cal
        row["provenance"]={
            "cutoff_date_exclusive":cutoff,"original_v04_game_id":gid,
            "verified_prior_drives":model["prior_drives"],
            "weekly_profile_game_ids":{
                side:profiles["profiles"][gid]["teams"][side]["prior_game_ids"]
                for side in ("home","away")},
            "historical_source_first_publication_verified":False,
            "qb_injury_weather_effects_applied":False,
        }
        rows.append(row)
    weekly={}
    for date in sorted({g["cutoff"] for g in rows}):
        subset=[g for g in rows if g["cutoff"]==date]
        weekly[date]={"games":len(subset),
                      "models":{k:_metric(subset,k) for k in VERSIONS},
                      "v12_calibration":_distribution_grade(subset)}
    return {"status":REPORT,"season":2026,"matched_games":len(rows),
            "prior_v11_games":len(archive["games"]),"excluded":dict(skips),
            "models":{k:_metric(rows,k) for k in VERSIONS},
            "v12_distribution_calibration":_distribution_grade(rows),
            "weekly":weekly,"games":rows,
            "observed_pregame_lines_only":True,
            "historical_source_first_publication_verified":False,
            "availability_effects_activated":False,
            "model_promoted":False,"promotion_eligible":False,
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
            "limitations":[
              "Retrospective ESPN first-publication timestamps not independently verified",
              "QB, injury and weather effects do not apply without point-in-time records",
              "Single-season, sparse quotes; experimental hazard weights not prospectively fitted",
              "Spread/total probabilities are hypothetical research distributions, not placed picks",
              "Do not promote V12 before out-of-sample independent and prospective evidence",
            ]}


def run(v11,drives,games,advanced,manifest,output,trials=2000):
    old=json.loads(Path(v11).read_text())
    source=json.loads(Path(drives).read_text())
    target=[{"game_id":str(r["game_id"]),"home":r["home"],
             "away":r["away"],"cutoff":r["cutoff"],
             "home_points":r["v04"]["home_points"],
             "away_points":r["v04"]["away_points"]} for r in old["games"]]
    dated=bridge(games,advanced,manifest,target)
    result=evaluate(old,source,advanced_index(advanced),dated,trials=trials)
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:result[k] for k in
        ("status","matched_games","excluded","models","v12_distribution_calibration",
         "promotion_eligible")},sort_keys=True))
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    for name in ("v11","drives","games","advanced","manifest","output"):
        parser.add_argument("--"+name,required=True)
    parser.add_argument("--trials",type=int,default=2000)
    a=parser.parse_args()
    run(a.v11,a.drives,a.games,a.advanced,a.manifest,a.output,trials=a.trials)

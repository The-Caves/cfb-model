"""V13 direct V04 score plus calibrated probabilities: paired retrospective audit.

Consumes ONLY the immutable 377-game V12R3 research archive. Historical score
labels are restricted to completed *previous evaluated cutoff weeks*; model
selection from this historically re-examined 2026 season is NOT independent.

Zero synthetic bookmaker lines. No historical player/weather/QB data or live
site action. This is not an argument for promotion based on this cohort alone.
"""
import argparse
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.v13_v04_probabilities import (
    STATUS as PREDICT_STATUS, VARIANTS, fit_uncertainty, predict, crps
)

STATUS="V13_DIRECT_V04_PROBABILITY_PAIRED_CHRONOLOGICAL_RESEARCH_ONLY"
ARCHIVE="V12R3_MATCHED_V04_V11_OPPONENT_PACE_FIELD_REDZONE_RESEARCH_ONLY"
Z80=1.2815515655446004


def _reliability(items):
    if not items:return {"n":0,"brier":None,"log_loss":None,"ece":None}
    n=len(items);bins=defaultdict(list)
    for p,y in items:
        if not (0<=p<=1 and y in (0,1)):
            raise ValueError("Invalid probability calibration label")
        bins[min(9,int(p*10))].append((p,y))
    brier=sum((p-y)**2 for p,y in items)/n
    logloss=-sum(y*math.log(max(1e-9,min(1-1e-9,p)))+
                 (1-y)*math.log(max(1e-9,min(1-1e-9,1-p)))
                 for p,y in items)/n
    ece=sum(len(v)/n*abs(sum(p for p,y in v)/len(v)-
                            sum(y for p,y in v)/len(v)) for v in bins.values())
    return {"n":n,"brier":round(brier,6),"log_loss":round(logloss,6),
            "ece":round(ece,6),
            "bins":[{"n":len(v),"forecast_mean":round(sum(p for p,y in v)/len(v),5),
                     "observed_rate":round(sum(y for p,y in v)/len(v),5),
                     "bin":k} for k,v in sorted(bins.items())]}


def _grade(rows,version):
    if not rows:return {"n":0}
    md=td=cm=ct=0.;su=ats=ou=0;ats_n=ou_n=0
    cov_m=cov_t=0
    w=[];pats=[];pou=[]
    for r in rows:
        model=r["predictions"][version]
        m=r["final_home"]-r["final_away"]
        total=r["final_home"]+r["final_away"]
        md+=abs(model["margin_mean"]-m)
        td+=abs(model["total_mean"]-total)
        cm+=crps(m,model["margin_mean"],model["margin_sd"])
        ct+=crps(total,model["total_mean"],model["total_sd"])
        cov_m+=model["margin_p10"]<=m<=model["margin_p90"]
        cov_t+=model["total_p10"]<=total<=model["total_p90"]
        if m!=0:
            su+=(model["margin_mean"]>0)==(m>0)
            w.append((model["home_win_probability"],int(m>0)))
        sp=r["market"]["home_spread"]
        line=r["market"]["total"]
        if sp is not None and m+sp!=0:
            ats_n+=1
            ats+=(model["margin_mean"]+sp>0)==(m+sp>0)
            pats.append((model["home_cover_probability"],int(m+sp>0)))
        if line is not None and total!=line:
            ou_n+=1
            ou+=(model["total_mean"]>line)==(total>line)
            pou.append((model["over_probability"],int(total>line)))
    n=len(rows)
    return {"n":n,"winner_correct":su,"margin_mae":round(md/n,5),
            "total_mae":round(td/n,5),"margin_crps":round(cm/n,6),
            "total_crps":round(ct/n,6),
            "margin_80pct_coverage":round(cov_m/n,5),
            "total_80pct_coverage":round(cov_t/n,5),
            "winner":_reliability(w),"ats_home_cover":_reliability(pats),
            "total_over":_reliability(pou),
            "ats_directions":{"n":ats_n,"correct":ats},
            "ou_directions":{"n":ou_n,"correct":ou}}


def evaluate(archive):
    if (not isinstance(archive,dict) or archive.get("status")!=ARCHIVE or
        archive.get("matched_games")!=377 or archive.get("original_weeks")!=7 or
        archive.get("model_promoted") is not False or
        archive.get("historical_source_first_publication_verified") is not False or
        len(archive.get("games",[]))!=377):
        raise ValueError("V13 requires unchanged originally executed V12R3 matched cohort")
    weeks=defaultdict(list);seen=set()
    for g in archive["games"]:
        gid=str(g["game_id"])
        if gid in seen:raise ValueError("Duplicate source-matched heldout game")
        seen.add(gid)
        day=dt.date.fromisoformat(g["date"])
        first=dt.date.fromisoformat(g["cutoff"])
        if (not first<=day<first+dt.timedelta(days=7) or
            g.get("r3_source",{}).get("cutoff_date_exclusive")!=g["cutoff"] or
            g.get("r3_source",{}).get("first_publication_verified") is not False):
            raise ValueError("Untrusted original football-week game source")
        weeks[g["cutoff"]].append(g)
    result=[];prior=[]
    for week in sorted(weeks):
        calibration=fit_uncertainty(prior,week)
        # Freeze one variance/bias estimate BEFORE any games in this week.
        for g in sorted(weeks[week],key=lambda x:str(x["game_id"])):
            orig=g["v04"]
            pace=g["simulations"]["v11_learned_pace_only"]
            if (g["provenance"]["cutoff_date_exclusive"]!=week or
                g["provenance"]["historical_source_first_publication_verified"] is not False or
                g["provenance"]["qb_injury_weather_effects_applied"] is not False):
                raise ValueError("Original V11-derived history not source/date reconciled")
            prior_v11={
                "cutoff":week,"game_id":str(g["game_id"]),
                "margin":pace["margin"],"total":pace["total"],
                "margin_width":g["v11_learned_pace_only_calibration"]["margin"]["width"],
                "total_width":g["v11_learned_pace_only_calibration"]["total"]["width"]}
            market=g["market"]
            predictions={kind:predict(orig,calibration,week,kind,prior_v11,market)
                         for kind in VARIANTS}
            result.append({
                "game_id":str(g["game_id"]),"home":g["home"],"away":g["away"],
                "date":g["date"],"cutoff":week,
                "kickoff_utc":g["kickoff_utc"],
                "v04":g["v04"],"market":market,
                "final_home":g["final_home"],"final_away":g["final_away"],
                "calibration_prior_games":calibration["earlier_games"],
                "calibration_prior_weeks":calibration["earlier_weeks"],
                "calibration_prior_ids_sha256":_sha(calibration["prior_game_ids"]),
                "predictions":predictions,
                "source_first_publication_verified":False,
            })
        # ONLY after an entire held-out week is done may the archived
        # score labels enter calibration for the following week.
        prior.extend(weeks[week])
    report={"status":STATUS,"original_cohort_games":len(result),
            "original_weeks":len(weeks),"model_variants":list(VARIANTS),
            "evaluation":{"overall":{v:_grade(result,v) for v in VARIANTS},
                          "weekly":{week:{"games":len(weeks[week]),
                              "metrics":{v:_grade([r for r in result if r["cutoff"]==week],v)
                                         for v in VARIANTS}}
                               for week in sorted(weeks)}},
            "games":result,
            "original_v04_score_preserved":True,
            "forecast_training_labels_earlier_week_only":True,
            "historical_first_publication_authenticated":False,
            "model_promoted":False,"website_model_published":False,
            "independent_prospective_improvement_proven":False,
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
            "warnings":[
                "Entire 2026 source has been previously examined and is not independent",
                "Historical ESPN first-publication times remain unauthenticated",
                "Fixed sigma and shrinkage weights were examined retrospectively",
                "Normal approximation is not a possession-level discrete-football model",
                "Book prices sampled on 156/154 cases, not verified closing odds",
                "Do not promote a score replacement from this historical comparison"]}
    return report


def _sha(items):
    import hashlib
    return hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()


def run(previous,output):
    with Path(previous).open() as handle:old=json.load(handle)
    report=evaluate(old)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({
        "status":STATUS,"n":report["original_cohort_games"],
        "original_weeks":report["original_weeks"],
        "metrics":{k:{x:v for x,v in m.items() if x!="bins"}
                   for k,m in report["evaluation"]["overall"].items()},
        "promoted":False},sort_keys=True))
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--previous",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    run(args.previous,args.output)

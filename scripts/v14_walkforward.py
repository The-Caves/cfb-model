"""V14 V04-relative chronological close-game, ATS and total score audit.

Frozen 377-game V13 archive is reused exactly. Each opponent matchup history
is reconstructed from games < its own ORIGINAL score forecast week. Fit
regularized V14 corrections from PREVIOUS held-out weeks only. Separately fit
spread and totals error distributions from PREVIOUS V14 held-out forecasts.

This retrospective source has NO authenticated PBP first-publication timestamps,
so the result can reject bad ideas, but cannot certify a sportsbook edge.
"""
import argparse
import csv
import datetime as dt
import json
import math
from collections import Counter,defaultdict
from pathlib import Path

from scripts.v14_matchup_features import load_inputs,profile,matchup
from scripts.v14_residual_challenger import STATUS as SCORE, VARIANTS,fit as fit_score,project
from scripts.v14_ats_totals_calibration import fit as fit_cal,predict as prob,brier
from scripts.v13_v04_probabilities import crps

STATUS="V14_MATCHED_V04_V13_V11_WEEKLY_CLOSE_ATS_TOTAL_RESEARCH_ONLY"
BASELINE="v13"
ALL_VARIANTS=(BASELINE,)+VARIANTS


def _metrics(rows,version):
    n=len(rows)
    if not n:return {"n":0}
    wins=toterr=marginerr=crpsm=crpst=cm=ct=0
    w=[];ats=[];ou=[];ads=ods=0;atn=otn=0
    for r in rows:
        p=r["forecasts"][version]
        m=r["final_home"]-r["final_away"]
        t=r["final_home"]+r["final_away"]
        mm,tt=p["margin"],p["total"]
        marginerr+=abs(m-mm);toterr+=abs(t-tt)
        sm,st=p["margin_sd"],p["total_sd"]
        crpsm+=crps(m,mm,sm);crpst+=crps(t,tt,st)
        cm+=mm-1.2815515655446004*sm<=m<=mm+1.2815515655446004*sm
        ct+=tt-1.2815515655446004*st<=t<=tt+1.2815515655446004*st
        if m!=0:
            wins+=int((mm>0)==(m>0))
            w.append((p["home_win_probability"],int(m>0)))
        spread=r["market"].get("home_spread")
        line=r["market"].get("total")
        if spread is not None and abs(m+spread)>1e-7:
            ads+=int((mm+spread>0)==(m+spread>0));atn+=1
            ats.append((p["home_cover_probability"],int(m+spread>0)))
        if line is not None and abs(t-line)>1e-7:
            ods+=int((tt>line)==(t>line));otn+=1
            ou.append((p["over_probability"],int(t>line)))
    return {"n":n,"winner_correct":wins,"winner_eligible":len(w),
        "margin_mae":round(marginerr/n,5),"total_mae":round(toterr/n,5),
        "margin_crps":round(crpsm/n,6),"total_crps":round(crpst/n,6),
        "margin_80pct_coverage":round(cm/n,5),"total_80pct_coverage":round(ct/n,5),
        "winner_probability":brier(w),"ats_probability":brier(ats),
        "over_probability":brier(ou),
        "ats_direction":{"correct":ads,"n":atn},
        "ou_direction":{"correct":ods,"n":otn}}


def evaluate(archive,advanced,turnovers):
    if (archive.get("status")!="V13_DIRECT_V04_PROBABILITY_PAIRED_CHRONOLOGICAL_RESEARCH_ONLY" or
        archive.get("original_cohort_games")!=377 or
        archive.get("original_weeks")!=7 or
        archive.get("historical_first_publication_authenticated") is not False or
        archive.get("model_promoted") is not False or
        len(archive.get("games",[]))!=377):
        raise ValueError("V14 must reuse original 377 frozen V04/V13 game cohort")
    source=load_inputs(advanced,turnovers)
    byweek=defaultdict(list);ids=set()
    for row in archive["games"]:
        gid=str(row["game_id"])
        if not gid or gid in ids:raise ValueError("Duplicate original V04 game")
        ids.add(gid)
        cut=dt.date.fromisoformat(row["cutoff"])
        day=dt.date.fromisoformat(row["date"])
        if not cut<=day<cut+dt.timedelta(days=7) or row.get("source_first_publication_verified") is not False:
            raise ValueError("Target outside frozen V04 forecast week")
        byweek[row["cutoff"]].append(row)
    full=[];trainrows=[];prior_v14={v:[] for v in VARIANTS}
    evidence=Counter()
    for cutoff in sorted(byweek):
        frozen=profile(source,cutoff)
        learned=fit_score(trainrows,cutoff)
        calibrations={v:fit_cal(prior_v14[v],cutoff)
                      for v in VARIANTS}
        fresh=[]
        for row in sorted(byweek[cutoff],key=lambda g:str(g["game_id"])):
            matched=matchup(frozen,row["home"],row["away"])
            if matched["ready"]:
                for team in ("home","away"):
                    if any(source["advanced"][(gid,
                        row[team])]["date"]>=cutoff
                        for gid in matched[team+"_prior_ids"]):
                        raise ValueError("V14 feature contains target/current-week PBP")
                evidence["matched"]+=1
            else:evidence[matched["reason"]]+=1
            base=row["predictions"]["prior_variance"]
            v04=row["v04"]
            forecasts={BASELINE:{
                "margin":base["margin_mean"],"total":base["total_mean"],
                "margin_sd":base["margin_sd"],"total_sd":base["total_sd"],
                "home_win_probability":base["home_win_probability"],
                "home_cover_probability":base["home_cover_probability"],
                "over_probability":base["over_probability"]}}
            v14_preds={}
            for name in VARIANTS:
                candidate=project(v04,matched,learned,cutoff,name)
                cal=calibrations[name]
                props=prob(candidate,cal,row["market"])
                forecasts[name]={
                    "margin":candidate["margin"],"total":candidate["total"],
                    "margin_sd":props["margin_sd"],"total_sd":props["total_sd"],
                    "home_win_probability":props["home_win_probability"],
                    "home_cover_probability":props["home_cover_probability"],
                    "over_probability":props["over_probability"]}
                v14_preds[name]=candidate
            out={
                "game_id":str(row["game_id"]),"home":row["home"],"away":row["away"],
                "date":row["date"],"cutoff":cutoff,
                "v04":v04,"market":row["market"],
                "final_home":row["final_home"],"final_away":row["final_away"],
                "matchup":matched,"training_games":learned["models"]["margin"]["n"],
                "matchup_feature_ready":matched["ready"],
                "forecasts":forecasts,
                "historical_first_publication_verified":False}
            full.append(out);fresh.append((out,v14_preds))
        # Extend ALL labels only after the entire week's forecasts are frozen.
        for row,v14 in fresh:
            trainrows.append({"game_id":row["game_id"],"cutoff":cutoff,
                "date":row["date"],"v04":row["v04"],"matchup":row["matchup"],
                "final_home":row["final_home"],"final_away":row["final_away"]})
            for name in VARIANTS:
                prior_v14[name].append({
                    "game_id":row["game_id"],"cutoff":cutoff,"date":row["date"],
                    "v14_forecast":v14[name],
                    "final_home":row["final_home"],"final_away":row["final_away"],
                    "source_first_publication_authenticated":False})
    # Prevent a silent change in original V04 baseline evaluation.
    ref=archive["evaluation"]["overall"]["prior_variance"]
    official=_metrics(full,BASELINE)
    if (official["n"]!=377 or official["winner_correct"]!=ref["winner_correct"] or
        abs(official["margin_mae"]-ref["margin_mae"])>.001 or
        abs(official["total_mae"]-ref["total_mae"])>.001 or
        abs(official["margin_crps"]-ref["margin_crps"])>.001 or
        abs(official["total_crps"]-ref["total_crps"])>.001):
        raise ValueError("Historic V04/V13 scores drifted; reject comparison")
    sections={
        "overall":full,
        "v04_close_under_3":[r for r in full if abs(r["v04"]["margin"])<=3],
        "v04_close_under_7":[r for r in full if abs(r["v04"]["margin"])<=7],
        "v04_close_under_10":[r for r in full if abs(r["v04"]["margin"])<=10],
        "market_close_3_5":[r for r in full if r["market"].get("home_spread") is not None
                             and abs(r["market"]["home_spread"])<=3.5],
    }
    return {"status":STATUS,"matched_games":len(full),"weeks":len(byweek),
        "evidence_coverage":dict(evidence),
        "metrics":{k:{variant:_metrics(rows,variant) for variant in ALL_VARIANTS}
                   for k,rows in sections.items()},
        "weekly":{cutoff:{variant:_metrics(
            [x for x in full if x["cutoff"]==cutoff],variant)
            for variant in ALL_VARIANTS} for cutoff in sorted(byweek)},
        "games":full,
        "model_promoted":False,"website_score_model_changed":False,
        "historical_source_first_publication_authenticated":False,
        "independent_prospective_validation_completed":False,
        "market_timing_authenticated":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
        "limitations":[
            "377 source-frozen games repeatedly examined during V04-V13 development",
            "Original ESPN PBP and turnover source first-publication timestamps unavailable",
            "Only 156 spread and 154 total archived research quotes, not necessarily opening/closing",
            "Player outcome and bookmaker prop coverage evaluated separately, not inferred",
            "V14 model development cannot be promoted solely on these retrospective results"]}


def run(v13,advanced,turnovers,output):
    with open(v13) as f:archive=json.load(f)
    with open(advanced) as f:rows=list(csv.DictReader(f))
    with open(turnovers) as f:box=json.load(f)
    out=evaluate(archive,rows,box)
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":STATUS,"matched_games":out["matched_games"],
        "weeks":out["weeks"],"evidence_coverage":out["evidence_coverage"],
        "metrics":out["metrics"],
        "model_promoted":False},sort_keys=True))
    return out

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    for opt in ("v13","advanced","turnovers","output"):
        ap.add_argument("--"+opt,required=True)
    args=ap.parse_args()
    run(args.v13,args.advanced,args.turnovers,args.output)

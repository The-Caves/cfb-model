"""V15 fully paired chronological 377-game retrospective ablation.

Replays EXACT frozen V04 and V14 from prior research; adds only earlier-week
trained V15 residual corrections. Each V15 variant gets its own uncertainty
fit using PRIOR out-of-fold predictions, never target-game labels or lines.
This previously examined 2026 cohort is NOT independent future validation.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.v14_ats_totals_calibration import fit as fit_cal,predict as score_probs,brier
from scripts.v13_v04_probabilities import crps
from scripts.v15_residual_challengers import STATUS as SCORE_STATUS,VARIANTS,fit,project

STATUS="V15_SOURCE_FROZEN_PRIOR_WEEK_TOTALS_CLOSE_RESEARCH_ONLY"
ORIGINAL="V14_MATCHED_V04_V13_V11_WEEKLY_CLOSE_ATS_TOTAL_RESEARCH_ONLY"
VERSIONS=("v04","v14_joint_close")+VARIANTS
Z80=1.2815515655446004


def _metrics(rows,name):
    n=len(rows)
    if not n:return {"n":0}
    err_m=err_t=cm=ct=0.
    wc=wn=atsc=atsn=ouc=oun=cover_m=cover_t=0
    win=[];ats=[];ou=[]
    for row in rows:
        p=row["predictions"][name]
        m=row["final_home"]-row["final_away"]
        t=row["final_home"]+row["final_away"]
        mm,tt=p["margin"],p["total"]
        sm,st=p["margin_sd"],p["total_sd"]
        err_m+=abs(m-mm);err_t+=abs(t-tt)
        cm+=crps(m,mm,sm);ct+=crps(t,tt,st)
        cover_m+=int(abs(m-mm)<=Z80*sm)
        cover_t+=int(abs(t-tt)<=Z80*st)
        if m:
            wn+=1;wc+=int((m>0)==(mm>0))
            win.append((p["home_win_probability"],int(m>0)))
        sp=row["market"].get("home_spread")
        line=row["market"].get("total")
        if sp is not None and abs(m+sp)>1e-8:
            atsn+=1;atsc+=int((mm+sp>0)==(m+sp>0))
            if p["home_cover_probability"] is not None:
                ats.append((p["home_cover_probability"],int(m+sp>0)))
        if line is not None and abs(t-line)>1e-8:
            oun+=1;ouc+=int((tt>line)==(t>line))
            if p["over_probability"] is not None:
                ou.append((p["over_probability"],int(t>line)))
    return {"n":n,"winners_correct":wc,"winner_games":wn,
            "margin_mae":round(err_m/n,5),"total_mae":round(err_t/n,5),
            "margin_crps":round(cm/n,6),"total_crps":round(ct/n,6),
            "margin_80pct_coverage":round(cover_m/n,5),
            "total_80pct_coverage":round(cover_t/n,5),
            "ats_correct":atsc,"ats_n":atsn,"ou_correct":ouc,"ou_n":oun,
            "winner_probability":brier(win),"ats_probability":brier(ats),
            "over_probability":brier(ou)}


def evaluate(archive):
    if (archive.get("status")!=ORIGINAL or archive.get("matched_games")!=377 or
        archive.get("weeks")!=7 or archive.get("model_promoted") is not False or
        archive.get("historical_source_first_publication_authenticated") is not False or
        len(archive.get("games",[]))!=377):
        raise ValueError("V15 requires unchanged V14 matched source-frozen cohort")
    byweek=defaultdict(list);ids=set()
    for r in archive["games"]:
        gid=str(r["game_id"])
        if not gid or gid in ids or r.get("historical_first_publication_verified") is not False:
            raise ValueError("Duplicate or source-time-invalid historical game")
        ids.add(gid)
        if not (r["cutoff"]<=r["date"]<r["cutoff"][:8]+"99"):
            raise ValueError("Historical fixture before original cutoff")
        if (not r.get("matchup_feature_ready") and r.get("matchup",{}).get("ready")):
            raise ValueError("Original frozen V14 source gate mismatched")
        byweek[r["cutoff"]].append(r)
    rows=[];prior=[];prior_variants={k:[] for k in VARIANTS};audit={}
    for cutoff in sorted(byweek):
        learned=fit(prior,cutoff)
        cal={k:fit_cal(prior_variants[k],cutoff) for k in VARIANTS}
        audit[cutoff]={
            "prior_full_week_games":len(prior),
            "total_bias_fit":learned["models"]["totals_bias"]["n"],
            "total_pace_fit":learned["models"]["totals_pace"]["n"],
            "close_margin_fit":learned["models"]["close_margin"]["n"],
            "training_all_prior_weeks_only":True}
        frozen_week=[]
        for source in sorted(byweek[cutoff],key=lambda x:str(x["game_id"])):
            base=source["forecasts"]["v13"]
            v14=source["forecasts"]["joint_close"]
            # These predictions are the original archive, not reconstructed.
            forecasts={"v04":base,"v14_joint_close":v14}
            grade={name:{
                "margin":f["margin"],"total":f["total"],
                "margin_sd":f["margin_sd"],"total_sd":f["total_sd"],
                "home_win_probability":f["home_win_probability"],
                "home_cover_probability":f["home_cover_probability"],
                "over_probability":f["over_probability"]}
                for name,f in forecasts.items()}
            variants={}
            for name in VARIANTS:
                p=project(source,learned,name)
                if (p["trained_week_exclusive"]!=cutoff or
                    p["future_games_used_in_training"] is not False or
                    p["model_promoted"] is not False):
                    raise ValueError("A V15 forecast uses future results")
                q=score_probs({"margin":p["margin"],"total":p["total"],
                               "model_promoted":False,
                               "source_cutoff_exclusive":cutoff},
                               cal[name],source["market"])
                grade[name]={
                    "margin":p["margin"],"total":p["total"],
                    "margin_sd":q["margin_sd"],"total_sd":q["total_sd"],
                    "home_win_probability":q["home_win_probability"],
                    "home_cover_probability":q["home_cover_probability"],
                    "over_probability":q["over_probability"]}
                variants[name]=p
            row={
                "game_id":str(source["game_id"]),"home":source["home"],"away":source["away"],
                "date":source["date"],"cutoff":cutoff,
                "market":source["market"],
                "final_home":source["final_home"],"final_away":source["final_away"],
                "matchup":source["matchup"],
                "v04":source["v04"],
                "forecasts":source["forecasts"], # immutable scored prior source
                "predictions":grade,
                "v15_ablation":variants,
                "training_count_before_week":learned["prior_games"],
                "historical_first_publication_authenticated":False}
            frozen_week.append(row)
            rows.append(row)
        # End-of-week ledger additions, no same-week training.
        prior.extend(frozen_week)
        for row in frozen_week:
            for name in VARIANTS:
                p=row["v15_ablation"][name]
                prior_variants[name].append({
                    "game_id":row["game_id"],"cutoff":cutoff,"date":row["date"],
                    "final_home":row["final_home"],"final_away":row["final_away"],
                    "source_first_publication_authenticated":False,
                    "v14_forecast":{
                        "margin":p["margin"],"total":p["total"],
                        "model_promoted":False,"source_cutoff_exclusive":cutoff}})
    n=len(rows)
    if n!=377:raise ValueError("Frozen V14 cohort count drifted")
    official=archive["metrics"]["overall"]
    base=_metrics(rows,"v04");v14=_metrics(rows,"v14_joint_close")
    for name,reference in (("v04",official["v13"]),
                           ("v14_joint_close",official["joint_close"])):
        computed=base if name=="v04" else v14
        for field,newname in (("margin_mae","margin_mae"),
                              ("total_mae","total_mae"),
                              ("margin_crps","margin_crps"),
                              ("total_crps","total_crps")):
            if abs(computed[field]-reference[newname])>.002:
                raise ValueError("Original V04/V14 forecast or grades drifted "+name)
        if computed["winners_correct"]!=reference["winner_correct"]:
            raise ValueError("Original winner directions drifted "+name)
    cuts={
        "all":rows,
        "v04_close_le3":[r for r in rows if abs(r["v04"]["margin"])<=3],
        "v04_close_le7":[r for r in rows if abs(r["v04"]["margin"])<=7],
        "v04_close_le10":[r for r in rows if abs(r["v04"]["margin"])<=10],
        "market_close_le3_5":[r for r in rows if
             r["market"].get("home_spread") is not None and
             abs(r["market"]["home_spread"])<=3.5],
    }
    return {"status":STATUS,"games":rows,"matched_games":len(rows),
            "original_cutoffs":sorted(byweek),"frozen_baselines_intact":True,
            "models":{v:_metrics(rows,v) for v in VERSIONS},
            "segments":{k:{v:_metrics(arr,v) for v in VERSIONS} for k,arr in cuts.items()},
            "weekly":{k:{v:_metrics([r for r in rows if r["cutoff"]==k],v)
                         for v in VERSIONS} for k in sorted(byweek)},
            "training_audit":audit,
            "historical_upstream_first_publication_authenticated":False,
            "models_promoted":False,"website_scoring_changed":False,
            "independent_unseen_test_passed":False,"safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED",
            "limitations":[
               "Repeatedly inspected 2026 cohort; NOT an independent future model competition",
               "ESPN PBP source original first-publication timestamps unavailable",
               "Spread/totals samples contain only authentic originally archived sparse quotes",
               "No current market is used to fit V15 scoring",
               "No promotion or profitable expected value claim is supported"]}


def run(source,output):
    original=json.loads(Path(source).read_text())
    report=evaluate(original)
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:report[k] for k in
        ("status","matched_games","models","training_audit",
         "frozen_baselines_intact","models_promoted")},sort_keys=True))
    return report


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    run(args.source,args.output)

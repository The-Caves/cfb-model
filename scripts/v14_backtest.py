"""V14 strict chronological same-377-game challenger evaluation.

Fits source-dated matchup features from frozen 2026 completed-game ledgers,
then fits residual scores / independent ATS-total reliability only on earlier
held-out V04 weeks. Whole forecast weeks share a single frozen trained state.
No site predictions or actual sportsbook picks are changed.

2026 PBP historical first-publication remains unauthenticated; 2026 data have
already been examined by previous model searches. NO independent promotion.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.v14_matchup_features import load_inputs,profile,matchup
from scripts.v14_residual_challenger import fit as fit_score,project,VARIANTS
from scripts.v14_market_calibration import fit as fit_market,project as price_prob
from scripts.v13_v04_probabilities import crps
from scripts.v13_v04_backtest import STATUS as V13_STATUS

STATUS="V14_CLOSE_MATCHUP_ATS_TOTAL_CHRONOLOGICAL_RESEARCH_ONLY"
N_EXPECTED=377


def _metric(rows,version):
    n=len(rows)
    if not n:return {"n":0}
    metric={"n":n,"winner_correct":0,"winner_n":0,
            "ats_correct":0,"ats_n":0,"total_correct":0,"total_n":0,
            "ats_signals":0,"ats_signal_correct":0,
            "total_signals":0,"total_signal_correct":0,
            "ats_brier_sum":0.,"total_brier_sum":0.,"win_brier_sum":0.,
            "margin_error":0.,"total_error":0.,
            "margin_crps_sum":0.,"total_crps_sum":0.,
            "total_80pct_hits":0,"matchup_ready":0}
    for g in rows:
        p=g["v14"][version]
        act_m=g["final_home"]-g["final_away"]
        act_t=g["final_home"]+g["final_away"]
        m=p["margin"];total=p["total"]
        metric["margin_error"]+=abs(act_m-m)
        metric["total_error"]+=abs(act_t-total)
        sd_m=g["sd_margin"];sd_t=g["sd_total"]
        metric["margin_crps_sum"]+=crps(act_m,m,sd_m)
        metric["total_crps_sum"]+=crps(act_t,total,sd_t)
        metric["total_80pct_hits"]+=abs(act_t-total)<=1.2815515655446004*sd_t
        metric["matchup_ready"]+=p["matchup_evidence_ready"]
        if act_m:
            metric["winner_n"]+=1
            metric["winner_correct"]+=(m>0)==(act_m>0)
            metric["win_brier_sum"]+=(p["probabilities"]["home_win"]-int(act_m>0))**2
        quote=g["market"]
        sp=quote.get("home_spread")
        if sp is not None and act_m+sp!=0:
            metric["ats_n"]+=1
            metric["ats_correct"]+=(m+sp>0)==(act_m+sp>0)
            q=p["probabilities"]["home_cover_calibrated"]
            if q is None:raise ValueError("Missing matched ATS probability")
            metric["ats_brier_sum"]+=(q-int(act_m+sp>0))**2
            choice=p["probabilities"]["home_cover_choice"]
            if choice!="PASS":
                metric["ats_signals"]+=1
                metric["ats_signal_correct"]+=(
                    (choice=="HOME")==(act_m+sp>0))
        line=quote.get("total")
        if line is not None and act_t!=line:
            metric["total_n"]+=1
            metric["total_correct"]+=(total>line)==(act_t>line)
            q=p["probabilities"]["over_calibrated"]
            if q is None:raise ValueError("Missing matched total probability")
            metric["total_brier_sum"]+=(q-int(act_t>line))**2
            choice=p["probabilities"]["total_choice"]
            if choice!="PASS":
                metric["total_signals"]+=1
                metric["total_signal_correct"]+=((
                    choice=="OVER")== (act_t>line))
    def mean(key,denom):
        return round(metric[key]/denom,6) if denom else None
    return {"n":n,"matchup_ready":metric["matchup_ready"],
            "winner_correct":metric["winner_correct"],
            "winner_n":metric["winner_n"],
            "margin_mae":mean("margin_error",n),"total_mae":mean("total_error",n),
            "margin_crps":mean("margin_crps_sum",n),
            "total_crps":mean("total_crps_sum",n),
            "total_80pct_coverage":mean("total_80pct_hits",n),
            "winner_brier":mean("win_brier_sum",metric["winner_n"]),
            "ats_correct":metric["ats_correct"],"ats_n":metric["ats_n"],
            "ats_brier":mean("ats_brier_sum",metric["ats_n"]),
            "over_correct":metric["total_correct"],"over_n":metric["total_n"],
            "over_brier":mean("total_brier_sum",metric["total_n"]),
            "ats_signals":metric["ats_signals"],
            "ats_signal_correct":metric["ats_signal_correct"],
            "total_signals":metric["total_signals"],
            "total_signal_correct":metric["total_signal_correct"]}


def evaluate(frozen,source):
    if (frozen.get("status")!=V13_STATUS or
        frozen.get("original_cohort_games")!=N_EXPECTED or
        frozen.get("original_weeks")!=7 or
        frozen.get("model_promoted") is not False or
        frozen.get("historical_first_publication_authenticated") is not False or
        len(frozen.get("games",[]))!=N_EXPECTED):
        raise ValueError("V14 requires original unchanged V13 forecast cohort")
    if source.get("historical_first_publication_authenticated") is not False:
        raise ValueError("V14 retrospective provider timestamps not authenticated")
    byweek=defaultdict(list);seen=set()
    for g in frozen["games"]:
        gid=str(g["game_id"])
        if gid in seen:raise ValueError("V14 duplicate frozen game")
        seen.add(gid)
        byweek[g["cutoff"]].append(g)
    rows=[];prior=[];fit_summary={}
    for week in sorted(byweek):
        dated=profile(source,week)
        score_fit=fit_score(prior,week)
        book_fit=fit_market(prior,week)
        fit_summary[week]={
            "test_games":len(byweek[week]),
            "earlier_week_games":len(prior),
            "matchup_training_rows":score_fit["models"]["margin"]["n"],
            "ats_calibration_training_quotes":book_fit["ats"]["n"],
            "total_calibration_training_quotes":book_fit["total"]["n"],
            "only_prior_week_labels_used":True}
        completed=[]
        for g in byweek[week]:
            if g["date"]<week or g["source_first_publication_verified"] is not False:
                raise ValueError("Target source time or cutoff unreliable")
            match=matchup(dated,g["home"],g["away"])
            if match.get("ready") and (
                g["game_id"] in (match["home_prior_ids"]+match["away_prior_ids"])):
                raise ValueError("Target game used in historical feature")
            sd_m=g["predictions"]["prior_variance"]["margin_sd"]
            sd_t=g["predictions"]["prior_variance"]["total_sd"]
            assert 8<=sd_m<=30 and 8<=sd_t<=30
            projections={}
            for version in VARIANTS:
                p=project(g["v04"],match,score_fit,week,variant=version)
                p["probabilities"]=price_prob(
                    p["margin"],p["total"],sd_m,sd_t,g["market"],book_fit,week)
                projections[version]=p
            # V13 original scores with independent V14 market-calibration
            # isolate, permitting any reliability gain to be measured
            # separately from the matchup-score changes.
            baseline=project(g["v04"],None,score_fit,week,variant="joint_close")
            baseline["probabilities"]=price_prob(
                baseline["margin"],baseline["total"],sd_m,sd_t,g["market"],book_fit,week)
            projections["v13_calibration_only"]=baseline
            record={
                "game_id":str(g["game_id"]),"home":g["home"],"away":g["away"],
                "date":g["date"],"cutoff":week,
                "final_home":g["final_home"],"final_away":g["final_away"],
                "v04":g["v04"],"market":g["market"],
                "predictions":{"prior_variance":g["predictions"]["prior_variance"]},
                "sd_margin":sd_m,"sd_total":sd_t,
                "matchup":match,"v14":projections,
                "source_publication_authenticated":False}
            rows.append(record);completed.append(record)
        # Each prior fold uses only source profiles as of its own forecast
        # week: never retroactively recompute past-team form using 2026 year-end.
        prior.extend(completed)
    if len(rows)!=N_EXPECTED:raise ValueError("V14 matched cohort changed")
    versions=("v13_calibration_only",)+VARIANTS
    grade=lambda subset:{v:_metric(subset,v) for v in versions}
    def slice_game(g):
        return abs(g["v04"]["margin"])
    segments={
        "v04_close_le3":lambda x:slice_game(x)<=3,
        "v04_close_3to7":lambda x:3<slice_game(x)<=7,
        "v04_close_7to10":lambda x:7<slice_game(x)<=10,
        "v04_strong_gt10":lambda x:slice_game(x)>10,
        "market_close_le3_5":lambda x:x["market"].get("home_spread") is not None
             and abs(x["market"]["home_spread"])<=3.5}
    return {"status":STATUS,"season":2026,"cohort_games":len(rows),
            "cutoffs":sorted(byweek),
            "metrics":grade(rows),
            "weekly":{w:grade([g for g in rows if g["cutoff"]==w]) for w in sorted(byweek)},
            "segments":{k:grade([g for g in rows if filterfn(g)])
                        for k,filterfn in segments.items()},
            "training_audit":fit_summary,
            "games":rows,"model_promoted":False,"website_scoring_changed":False,
            "first_publication_authenticated":False,
            "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
            "independent_unseen_test_passed":False,
            "warnings":[
                "Historically retrieved 2026 PBP/turnovers lack authenticated original source publication",
                "Previously inspected 377-game cohort; selected improvements not independent validation",
                "Bookmaker lines and prices missing for most games; no verified ROI",
                "QB/injury/weather data not interpolated or inferred",
                "No player prop odds are generated from team points or box scores"]}


def run(v13,advanced,turnovers,output):
    archive=json.loads(Path(v13).read_text())
    with open(advanced,newline="") as fh:raw=list(csv.DictReader(fh))
    to=json.loads(Path(turnovers).read_text())
    result=evaluate(archive,load_inputs(raw,to))
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":STATUS,"games":result["cohort_games"],
        "metrics":result["metrics"],"segments":{
            name:{variant:{"n":m["n"],"winner_correct":m["winner_correct"],
                "margin_mae":m["margin_mae"],"total_mae":m["total_mae"],
                "ats_brier":m["ats_brier"],"over_brier":m["over_brier"]}
               for variant,m in grade.items()}
            for name,grade in result["segments"].items()},
        "model_promoted":False},sort_keys=True))
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--v13",required=True)
    parser.add_argument("--advanced",required=True)
    parser.add_argument("--turnovers",required=True)
    parser.add_argument("--output",required=True)
    a=parser.parse_args()
    run(a.v13,a.advanced,a.turnovers,a.output)

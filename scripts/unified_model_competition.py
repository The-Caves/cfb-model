"""Unify already-archived, same-frozen-game V03 / research challenger grades.

The source grade modules own forecast/final provenance and archival checks.
We verify cross-report baseline identity, compare each candidate on its own
exact game cohort, and keep ATS / O-U market statistics on a separate cohort.
This must NEVER become retrospective selection or automatic promotion.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

STATUS="UNIFIED_PROSPECTIVE_MODEL_COMPETITION_RESEARCH_ONLY"
SHADOW_STATUS="SHADOW_PROSPECTIVE_PAIRED_GRADING_RESEARCH_ONLY"
CANDIDATE_STATUS="QB_VENUE_TRAVEL_PROSPECTIVE_PAIRED_GRADE_RESEARCH_ONLY"
MARKET_STATUS="CUMULATIVE_PROSPECTIVE_PERFORMANCE_RESEARCH_ONLY"


def number(value):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError("Non-finite observed or forecast margin")
    return float(value)


def _trust(source,status):
    if (source.get("status")!=status or source.get("betting_status")!="PASS_UNVALIDATED"
        or source.get("safe_for_betting") is not False
        or source.get("model_promoted") is not False):
        raise ValueError("Untrusted archived model grade")
    if not isinstance(source.get("per_game"),list):
        raise ValueError("Missing grade records")


def _same(a,b):
    return math.isclose(a,b,abs_tol=.0002,rel_tol=0)


def evaluate(shadow,candidates,market=None,min_pairs=30):
    if type(min_pairs) is not int or min_pairs<2:
        raise ValueError("Invalid minimum paired sample")
    _trust(shadow,SHADOW_STATUS)
    _trust(candidates,CANDIDATE_STATUS)
    if shadow.get("season")!=2026 or candidates.get("season")!=2026:
        raise ValueError("Wrong football season")
    slots={}
    metrics=defaultdict(list)

    def accept(game_id,run,home,away,actual,baseline,predictions):
        key=str(game_id)
        if not key or not str(run).isdigit() or not home or not away or home==away:
            raise ValueError("Ambiguous frozen fixture identity")
        base=number(baseline)
        truth=number(actual)
        prior=slots.get(key)
        identity=(str(run),home,away)
        if prior is not None and (
            identity!=prior["identity"] or not _same(base,prior["baseline"])
            or not _same(truth,prior["actual"])):
            raise ValueError("Cross-source baseline or final does not match same frozen game")
        if prior is None:
            slots[key]={"identity":identity,"baseline":base,"actual":truth}
        for name,pred in predictions.items():
            if (key,name) in already:
                raise ValueError("Duplicate candidate forecast in paired grade")
            already.add((key,name))
            prediction=number(pred)
            metrics[name].append({"game_id":key,"run_id":str(run),
                                  "candidate_abs_error":abs(prediction-truth),
                                  "baseline_abs_error":abs(base-truth),
                                  "candidate_signed_error":prediction-truth,
                                  "baseline_signed_error":base-truth,
                                  "candidate_winner_correct":int((prediction>0)==(truth>0))
                                      if prediction and truth else None,
                                  "baseline_winner_correct":int((base>0)==(truth>0))
                                      if base and truth else None})
    already=set()
    for row in shadow["per_game"]:
        ref=row.get("models",{}).get("active_v03")
        if not isinstance(ref,dict):
            raise ValueError("Shadow missing selected V03 benchmark")
        pred=ref.get("predicted_margin")
        if pred is None or not _same(abs(number(pred)-number(row["actual_margin"])),
                                      number(ref["margin_abs_error"])):
            raise ValueError("Original V03 shadow error disagreement")
        variants={}
        for name,entry in row["models"].items():
            if name=="active_v03":continue
            margin=number(entry["predicted_margin"])
            if not _same(abs(margin-number(row["actual_margin"])),number(entry["margin_abs_error"])):
                raise ValueError("Shadow error mismatch")
            variants["shadow:"+name]=margin
        if variants:
            accept(row["game_id"],row["shadow_run_id"],row["home"],row["away"],
                   row["actual_margin"],pred,variants)

    for row in candidates["per_game"]:
        base=number(row["baseline_v03_margin"])
        actual=number(row["actual_home_margin"])
        if not _same(abs(base-actual),number(row["baseline_v03_abs_error"])):
            raise ValueError("Candidate report does not match original V03 error")
        variants={}
        for name,entry in row["model_results"].items():
            prediction=number(entry["prediction"])
            if not _same(abs(prediction-actual),number(entry["abs_error"])):
                raise ValueError("Candidate reported margin error mismatch")
            variants["personnel:"+name]=prediction
        if variants:
            accept(row["game_id"],row["run_id"],row["home"],row["away"],
                   actual,base,variants)

    report={}
    for name,records in sorted(metrics.items()):
        n=len(records)
        def avg(key):
            return round(sum(r[key] for r in records)/n,5)
        c=avg("candidate_abs_error");b=avg("baseline_abs_error")
        su=[r for r in records if r["candidate_winner_correct"] is not None]
        su_base=[r for r in records if r["baseline_winner_correct"] is not None]
        report[name]={
            "status":"ENOUGH_PAIRED_GAMES_FOR_INDEPENDENT_REVIEW" if n>=min_pairs
                     else "INSUFFICIENT_PAIRED_PROSPECTIVE_GAMES",
            "paired_games":n,"game_ids":sorted(r["game_id"] for r in records),
            "candidate_margin_mae":c,"same_cohort_v03_margin_mae":b,
            "paired_delta_margin_mae":round(c-b,5),
            "candidate_signed_margin_bias":avg("candidate_signed_error"),
            "baseline_signed_margin_bias":avg("baseline_signed_error"),
            "candidate_su_accuracy":round(sum(r["candidate_winner_correct"] for r in su)/len(su),5)
                if su else None,
            "baseline_su_accuracy":round(sum(r["baseline_winner_correct"] for r in su_base)/len(su_base),5)
                if su_base else None,
            "promotion_eligible":False,
        }
    market_separate=None
    if market is not None:
        if (market.get("status")!=MARKET_STATUS or market.get("betting_status")!="PASS_UNVALIDATED"
            or market.get("safe_for_betting") is not False
            or market.get("model_validated") is not False
            or market.get("profitability_calculated") is not False):
            raise ValueError("Invalid market benchmark evidence")
        market_separate={"summary":market["summary"],"benchmarks":market["benchmarks"],
                         "same_cohort_as_margin_challenger_grade":False,
                         "cross_market_comparison_eligible":False}
    return {
        "status":STATUS,"season":2026,
        "reference":"V03_FROZEN_SELECTED_24_TO_72H_PREKICKOFF",
        "unique_compared_games":len(slots),"challenger_count":len(report),
        "minimum_review_pairs":min_pairs,
        "challengers":report,
        "market_stats_separate_cohort":market_separate,
        "no_cross_model_ranking_different_cohorts":True,
        "promotion_gates_not_satisfied":"INDEPENDENT_CALIBRATION_SOURCE_AUTHENTICATION_MARKET_COHORT_REVIEW",
        "automatic_model_promotion":False,"model_promoted":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
    }


def run(shadow_path,candidate_path,output_path,market_path=None,min_pairs=30):
    shadow=json.loads(Path(shadow_path).read_text(encoding="utf-8"))
    candidate=json.loads(Path(candidate_path).read_text(encoding="utf-8"))
    market=json.loads(Path(market_path).read_text(encoding="utf-8")) if market_path else None
    result=evaluate(shadow,candidate,market,min_pairs=min_pairs)
    output=Path(output_path);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({"status":STATUS,"unique_games":result["unique_compared_games"],
                      "challengers":{k:v["paired_games"] for k,v in result["challengers"].items()},
                      "model_promoted":False}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--shadow",required=True);p.add_argument("--candidates",required=True)
    p.add_argument("--market");p.add_argument("--output",required=True)
    p.add_argument("--min-pairs",type=int,default=30)
    a=p.parse_args()
    run(a.shadow,a.candidates,a.output,a.market,a.min_pairs)

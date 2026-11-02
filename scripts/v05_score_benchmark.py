"""Paired chronological V04 vs V05 and fixed ablations; no auto-promotion.

All candidate predictions share identical held-out ESPN game IDs. No line,
injury, future result, current-season full-sample parameters, or post-kickoff
source is used as a prediction input. 2026 historical first-publication
timestamps remain unauthenticated; these folds are exploratory.
"""
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path

from scripts.v04_direct_scores import fit as fit_v04, predict as predict_v04
from scripts.v05_robust_scores import fit as fit_v05, predict as predict_v05

STATUS="V05_PAIRED_WEEKLY_CHRONOLOGICAL_RESEARCH_ONLY"
VARIANTS=("v04","v05_full","v05_no_form",
          "v05_no_margin_form","v05_no_total_form")


def _stats(rows,variant):
    if not rows:
        return {"games":0,"margin_mae":None,"total_mae":None,
                "su_accuracy":None,"predicted_home_fraction":None,
                "margin_bias":None,"total_bias":None,
                "large_margin_miss_rate":None}
    n=len(rows)
    error_margin=[r[variant+"_margin"]-r["actual_margin"] for r in rows]
    error_total=[r[variant+"_total"]-r["actual_total"] for r in rows]
    return {"games":n,
      "margin_mae":round(sum(abs(e) for e in error_margin)/n,4),
      "total_mae":round(sum(abs(e) for e in error_total)/n,4),
      "margin_bias":round(sum(error_margin)/n,4),
      "total_bias":round(sum(error_total)/n,4),
      "su_accuracy":round(sum(
          (r[variant+"_margin"]>0)==(r["actual_margin"]>0)
          for r in rows)/n,5),
      "predicted_home_fraction":round(sum(r[variant+"_margin"]>0 for r in rows)/n,5),
      "large_margin_miss_rate":round(sum(abs(e)>=21 for e in error_margin)/n,5),
      "favorite_upset_recall":None}


def evaluate(games,start="2026-09-26",weeks=20):
    if not isinstance(games,list) or not games:
        raise ValueError("No actual scoreboard rows")
    ids=[str(g["game_id"]) for g in games]
    if len(ids)!=len(set(ids)):
        raise ValueError("Duplicate source game identity")
    if not isinstance(weeks,int) or not 1<=weeks<=30:
        raise ValueError("Invalid research fold count")
    for g in games:
        date=dt.date.fromisoformat(g["date"])
        if date.year!=2026:
            raise ValueError("Wrong scoreboard season")
        if g["neutral"] not in ("True","False"):
            raise ValueError("Unconfirmed neutral venue")
        if g["home"]==g["away"] or not g["home"] or not g["away"]:
            raise ValueError("Invalid game opponents")
        for key in ("home_score","away_score"):
            v=float(g[key])
            if not math.isfinite(v) or not v.is_integer() or not 0<=v<=200:
                raise ValueError("Unverified finished score")
    first=dt.date.fromisoformat(start)
    all_rows=[];folds=[]
    for week in range(weeks):
        begin=first+dt.timedelta(days=7*week)
        end=begin+dt.timedelta(days=7)
        train=[r for r in games if dt.date.fromisoformat(r["date"])<begin]
        test=[r for r in games if begin<=dt.date.fromisoformat(r["date"])<end]
        if not test or len(train)<90:
            continue
        if set(str(r["game_id"]) for r in train)&set(str(r["game_id"]) for r in test):
            raise ValueError("Non-disjoint model contest")
        # Eastern football-day embargo. All models fit from EXACT same rows.
        when=dt.datetime.combine(begin,dt.time(hour=15),tzinfo=dt.timezone.utc).isoformat()
        v04=fit_v04(train,when)
        v05=fit_v05(train,when)
        sample=[]
        for game in test:
            neutral=game["neutral"]=="True"
            a=predict_v04(v04,game["home"],game["away"],neutral)
            full=predict_v05(v05,game["home"],game["away"],neutral)
            if a is None or full is None:
                continue
            row={"game_id":str(game["game_id"]),"cutoff":begin.isoformat(),
                 "home":game["home"],"away":game["away"],
                 "actual_margin":float(game["home_score"])-float(game["away_score"]),
                 "actual_total":float(game["home_score"])+float(game["away_score"]),
                 "v05_thin_history":full["thin_history_warning"]}
            outputs={"v04":a,"v05_full":full}
            for name in VARIANTS[2:]:
                outputs[name]=predict_v05(
                    v05,game["home"],game["away"],neutral,variant=name)
            if any(x is None for x in outputs.values()):
                raise ValueError("Ablation missing on V05 matched sample")
            for name,item in outputs.items():
                row[name+"_margin"]=item["home_margin"]
                row[name+"_total"]=item["total_points"]
            sample.append(row)
        if not sample:
            continue
        all_rows.extend(sample)
        folds.append({
            "week_start":begin.isoformat(),
            "training_games":len(train),
            "matched_games":len(sample),
            "game_ids":[x["game_id"] for x in sample],
            "models":{name:_stats(sample,name) for name in VARIANTS}
        })
    if len(all_rows)!=len({r["game_id"] for r in all_rows}):
        raise ValueError("Same holdout graded twice")
    overall={name:_stats(all_rows,name) for name in VARIANTS}
    for name in VARIANTS[1:]:
        a=overall[name];b=overall["v04"]
        a["paired_delta_margin_mae_vs_v04"]=(
            round(a["margin_mae"]-b["margin_mae"],4) if all_rows else None)
        a["paired_delta_total_mae_vs_v04"]=(
            round(a["total_mae"]-b["total_mae"],4) if all_rows else None)
        a["weeks_lower_margin_mae"]=sum(
            f["models"][name]["margin_mae"]<f["models"]["v04"]["margin_mae"]
            for f in folds)
        a["weeks_lower_total_mae"]=sum(
            f["models"][name]["total_mae"]<f["models"]["v04"]["total_mae"]
            for f in folds)
    # No results-based live promotion, even if exploratory folds look good.
    return {
        "status":STATUS,"season":2026,"matched_games":len(all_rows),
        "n_folds":len(folds),"models":overall,"folds":folds,
        "predictions":all_rows,
        "score_model_promoted":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
        "historical_source_first_publication_verified":False,
        "historical_market_lines_used":False,
        "same_team_and_game_ids_for_all_models":True,
        "fixed_ablation_variants":list(VARIANTS),
        "no_automatic_model_selection":True,
        "no_prospective_promotion_approved":True,
        "note":"Retrospective 2026 scores may have been revised since kickoff. These paired folds do not establish a live ATS/O-U advantage."
    }


def run(games_csv,output):
    with open(games_csv,newline="",encoding="utf-8-sig") as fh:
        rows=list(csv.DictReader(fh))
    results=evaluate(rows)
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(results,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in results.items() if k not in ("folds","predictions")}))
    return results


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.games,a.output)

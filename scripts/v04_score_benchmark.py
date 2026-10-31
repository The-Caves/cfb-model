"""Same-game and strict earlier-week score comparison: V03, R1, direct V04.

No reference sportsbook market lines are available for the historical folds.
This is chronological research, not verified original historic publication
timing, and the model does not auto-promote based on these results.
"""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import numpy as np

from scripts.model_v03 import load_inputs,build_weekly_games,fit_ridge,predict as v03predict
from scripts.personnel_features import BASE_FIELDS
from scripts.site_home_bias_guard import _source_games,ratings,HOME_ALLOWANCE
from scripts.v04_direct_scores import fit,predict,MODEL

STATUS="V04_DIRECT_SCORE_PAIRED_WALKFORWARD_RESEARCH_ONLY"

def evaluate(games,advanced,start="2026-09-26",days=7):
    if not isinstance(games,list) or len({str(g["game_id"]) for g in games})!=len(games):
        raise ValueError("Missing/duplicate original ESPN games")
    weekly=build_weekly_games(games,advanced)
    if set(str(r["game_id"]) for r in weekly)!=set(str(g["game_id"]) for g in games):
        raise ValueError("Historical features have an unmatched training game")
    folds=[];all_rows=[]
    first=dt.date.fromisoformat(start)
    last=max(dt.date.fromisoformat(r["date"]) for r in games)
    for n in range(22):
        cutoff=first+dt.timedelta(days=days*n)
        if cutoff>last:break
        prior=[r for r in games if dt.date.fromisoformat(r["date"])<cutoff]
        prior_features=[r for r in weekly if dt.date.fromisoformat(r["date"])<cutoff]
        final=[r for r in weekly if cutoff<=dt.date.fromisoformat(r["date"])<
               cutoff+dt.timedelta(days=days)]
        if len(prior)<90 or not final:continue
        instant=dt.datetime.combine(cutoff,dt.time(hour=12),tzinfo=dt.timezone.utc).isoformat()
        our_model=fit(prior,instant)
        r1_strength=ratings(_source_games(prior,dt.datetime.fromisoformat(instant)))
        v03=fit_ridge(prior_features,BASE_FIELDS)
        v03_s,_=v03predict(final,BASE_FIELDS,v03)
        fold_rows=[]
        for row,score in zip(final,v03_s):
            actual=(float(row["home_score"])-float(row["away_score"]),
                    float(row["home_score"])+float(row["away_score"]))
            v03_margin=float(np.clip(score[0],-55.,55.))
            v03_total=float(np.clip(score[1],0.,110.))
            gid=str(row["game_id"])
            orig=next(g for g in games if str(g["game_id"])==gid)
            neutral=str(orig["neutral"]).lower()
            if neutral not in ("true","false"):raise ValueError("Unknown historic neutral venue")
            neutral=neutral=="true"
            v04=predict(our_model,row["home"],row["away"],neutral)
            if v04 is None or row["home"] not in r1_strength or row["away"] not in r1_strength:
                continue
            r1margin=r1_strength[row["home"]]-r1_strength[row["away"]]+(
                0 if neutral else HOME_ALLOWANCE)
            item={"game_id":gid,"cutoff":cutoff.isoformat(),
                "actual_margin":actual[0],"actual_total":actual[1],
                "v03_margin":v03_margin,"v03_total":v03_total,
                "r1_margin":r1margin,"v04_margin":v04["home_margin"],
                "v04_total":v04["total_points"],
                "v04_home_points":v04["home_points"],
                "v04_away_points":v04["away_points"]}
            fold_rows.append(item)
        if not fold_rows:continue
        folds.append({"first_test_day":cutoff.isoformat(),"past_games":len(prior),
           "matched_games":len(fold_rows),
           "game_ids":[r["game_id"] for r in fold_rows]})
        all_rows.extend(fold_rows)
    if len({r["game_id"] for r in all_rows})!=len(all_rows):
        raise ValueError("Holdout game used twice")
    n=len(all_rows)
    models={}
    for name in ("v03","r1","v04"):
        field="v03_margin" if name=="v03" else "r1_margin" if name=="r1" else "v04_margin"
        stats={
            "games":n,
            "margin_mae":round(sum(abs(x[field]-x["actual_margin"]) for x in all_rows)/n,5) if n else None,
            "mean_signed_home_margin_error":round(sum(x[field]-x["actual_margin"] for x in all_rows)/n,5) if n else None,
            "home_win_selection_fraction":round(sum(x[field]>0 for x in all_rows)/n,5) if n else None,
            "straight_up_accuracy":round(sum((x[field]>0)==(x["actual_margin"]>0) for x in all_rows)/n,5) if n else None
        }
        if name!="r1":
            stats["total_mae"]=round(sum(abs(x[name+"_total"]-x["actual_total"]) for x in all_rows)/n,5) if n else None
        models[name]=stats
    # Research screening is not prospective promotion, no matter the result.
    screening=(n>=120 and len(folds)>=3 and
         models["v04"]["margin_mae"]<=models["v03"]["margin_mae"]*.98 and
         models["v04"]["total_mae"]<=models["v03"]["total_mae"]*1.02 and
         models["v04"]["home_win_selection_fraction"]<.80)
    return {"status":STATUS,"season":2026,"model":MODEL,
      "matched_games":n,"n_folds":len(folds),"models":models,
      "research_screening_passed":bool(screening),
      "prospective_promotion_approved":False,
      "historical_original_pbp_publication_authenticated":False,
      "historical_market_quotes_used":False,"no_hindsight_model_selection":True,
      "model_promoted":False,"safe_for_betting":False,
      "betting_status":"PASS_UNVALIDATED",
      "folds":folds,"predictions":all_rows}

def run(games,advanced,advanced_manifest,output):
    historical,adv,_=load_inputs(games,advanced,advanced_manifest)
    result=evaluate(historical,adv)
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("folds","predictions")}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True);p.add_argument("--advanced",required=True)
    p.add_argument("--advanced-manifest",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.games,a.advanced,a.advanced_manifest,a.output)

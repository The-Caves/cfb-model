"""Experimental matchup features, reconstructed strictly from earlier 2026 games.

Turnover_vec is present in provider PBP but not validated as giveaway/takeaway;
therefore turnover features are explicitly withheld until semantics are audited.
"""
import argparse, csv, json
from collections import defaultdict
from pathlib import Path
from scripts.model_v03 import (FEATURES, load_inputs, build_weekly_games,
                              game_stats, group_by_date, rate, fit_ridge, predict,
                              timestamp)
from scripts.feature_consistency_audit import metrics
import datetime as dt
import math
import numpy as np

GROUPS = {
 "line_front": ["sack_allowed_matchup", "pressure_allowed_form"],
 "redzone_fourth": ["redzone_success_form", "fourth_success_form"],
 "trajectory": ["margin_trajectory_form", "epa_trajectory_form"],
}
# Never infer turnover possession or credit from an undocumented provider vector.
UNAVAILABLE = {"turnovers": "turnover_vec semantics not verified; giveaway/takeaway attribution withheld"}
def avg(xs):
    return sum(xs)/len(xs) if xs else None
def delta(a,b):
    return a-b if a is not None and b is not None else None
def recent(history,field,n):
    return avg([v[field] for v in history[-n:] if v.get(field) is not None])
def features_for(history_home, history_away):
    def form(field,n=5):
        return delta(recent(history_home,field,n),recent(history_away,field,n))
    def trajectory(field):
        def side(history):
            if len(history)<4:return None
            last=recent(history,field,2)
            old=avg([v[field] for v in history[-5:-2] if v.get(field) is not None])
            return delta(last,old)
        return delta(side(history_home),side(history_away))
    # Offensive sack rate allowed, paired against opposing defensive sacks generated.
    h_sack=recent(history_home,"sack_allowed",5)
    a_sack=recent(history_away,"sack_allowed",5)
    h_generated=recent(history_home,"sack_generated",5)
    a_generated=recent(history_away,"sack_generated",5)
    return {
      "sack_allowed_matchup": delta(
          avg([x for x in (h_sack,a_generated) if x is not None]),
          avg([x for x in (a_sack,h_generated) if x is not None])),
      "pressure_allowed_form": form("pressure_allowed"),
      "redzone_success_form": form("redzone_success"),
      "fourth_success_form": form("fourth_success"),
      "margin_trajectory_form": trajectory("margin"),
      "epa_trajectory_form": trajectory("epa_off"),
    }

def augment(games,advanced):
    baseline={r["game_id"]:r for r in build_weekly_games(games,advanced)}
    history=defaultdict(list)
    for _,group in group_by_date(games):
        for g in group:
            home,away=g["home"],g["away"]
            # Only games on previous Eastern calendar dates are in history.
            h=history[home];a=history[away]
            baseline[g["game_id"]].update(features_for(h,a))
        for g in group:
            home,away=g["home"],g["away"]
            for team in (home,away):
                p=advanced.get(g["game_id"],{}).get(team,{})
                opp=away if team==home else home
                q=advanced.get(g["game_id"],{}).get(opp,{})
                record=game_stats(g,team,advanced)
                record.update({
                  "sack_allowed":rate(p,"sack_count","sack_observed"),
                  "sack_generated":rate(q,"sack_count","sack_observed"),
                  "pressure_allowed":rate(p,"pressure_count","pressure_observed"),
                  "redzone_success":rate(p,"redzone_success","redzone_plays"),
                  "fourth_success":rate(p,"fourth_success","fourth_plays"),
                })
                history[team].append(record)
    return list(baseline.values())

def evaluate(rows,start="2026-09-26",min_training=90):
    variants={"baseline_v03":FEATURES}
    for group,fields in GROUPS.items():
        variants[group]=FEATURES+fields
    variants["all_available"]=FEATURES+sum(GROUPS.values(),[])
    variants["all_except_line_front"]=FEATURES+GROUPS["redzone_fourth"]+GROUPS["trajectory"]
    variants["all_except_redzone_fourth"]=FEATURES+GROUPS["line_front"]+GROUPS["trajectory"]
    variants["all_except_trajectory"]=FEATURES+GROUPS["line_front"]+GROUPS["redzone_fourth"]
    weeks=[];all_predictions=defaultdict(list)
    last=max(dt.date.fromisoformat(r["date"]) for r in rows)
    for i in range(30):
        begin=dt.date.fromisoformat(start)+dt.timedelta(days=7*i)
        if begin>last:break
        end=begin+dt.timedelta(days=7)
        train=[r for r in rows if dt.date.fromisoformat(r["date"])<begin and min(r["home_games_prior"],r["away_games_prior"])>=1]
        test=[r for r in rows if begin<=dt.date.fromisoformat(r["date"])<end and min(r["home_games_prior"],r["away_games_prior"])>=1]
        if len(train)<min_training or not test:continue
        fold={"week_start":begin.isoformat(),"train_games":len(train),"test_games":len(test),"variants":{}}
        for name,fields in variants.items():
            pred,sigma=predict(test,fields,fit_ridge(train,fields))
            records=[]
            for g,p in zip(test,pred):
                margin=float(np.clip(p[0],-55,55));total=float(np.clip(p[1],0,110))
                actual=g["home_score"]-g["away_score"]
                probability=.5*(1+math.erf(margin/(sigma*math.sqrt(2))))
                records.append({"game_id":g["game_id"],"week_start":begin.isoformat(),
                                "variant":name,"home":g["home"],"away":g["away"],
                                "pred_margin":round(margin,3),"actual_margin":actual,
                                "su_correct":int((margin>0)==(actual>0)),
                                "margin_abs_error":abs(margin-actual),
                                "total_abs_error":abs(total-g["home_score"]-g["away_score"]),
                                "brier":(probability-int(actual>0))**2})
            fold["variants"][name]=metrics(records)
            all_predictions[name].extend(records)
        weeks.append(fold)
    if not weeks:raise ValueError("No eligible chronological folds")
    overall={name:metrics(records) for name,records in all_predictions.items()}
    base=overall["baseline_v03"]
    for name,v in overall.items():
        v["correct_delta_vs_baseline"]=v["correct"]-base["correct"]
        v["weeks_better_su"]=sum(w["variants"][name]["correct"]>w["variants"]["baseline_v03"]["correct"] for w in weeks)
        v["weeks_worse_su"]=sum(w["variants"][name]["correct"]<w["variants"]["baseline_v03"]["correct"] for w in weeks)
    return {"status":"RETROSPECTIVE_CANDIDATE_RESEARCH_ONLY","model_promoted":False,
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
            "historical_publication_times_verified":False,
            "unavailable_feature_groups":UNAVAILABLE,
            "warning":"Same holdout weeks used for feature exploration; fresh prospective validation required.",
            "weekly":weeks,"overall":overall},all_predictions

def run(games,advanced,manifest,output):
    games,advanced,_=load_inputs(games,advanced,manifest)
    report,preds=evaluate(augment(games,advanced))
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    with (root/"feature_experiments.json").open("x") as f:json.dump(report,f,indent=2)
    with (root/"feature_predictions.csv").open("x",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(next(iter(preds.values()))[0]))
        writer.writeheader()
        for records in preds.values():writer.writerows(records)
    # The experiment is research-only and never promotes the candidate.\n    print(json.dumps({"status":report["status"],"weeks":len(report["weekly"]),
                      "baseline":report["overall"]["baseline_v03"],
                      "candidates":report["overall"],"unavailable":UNAVAILABLE}))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("games","advanced","manifest","output"):p.add_argument("--"+name,required=True)
    a=p.parse_args();run(a.games,a.advanced,a.manifest,a.output)

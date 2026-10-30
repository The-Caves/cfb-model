
"""2026 next-generation CFB challenger versus EXACT-COHORT V03 backtest.

Opponent-adjusted team/style/pressure/turnover and nonlinear interaction
feature families are fit on earlier Eastern football dates only.
Every challenger is contrasted with a separately refit V03 on the *same*
training AND held-out games: no easy-game subset or postgame team ratings.
Historical PBP release dates remain unauthenticated, so this is an exploratory
walk-forward, NOT a point-in-time verified outcome or bettable prediction.
"""
import argparse
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts import model_v03 as v03
from scripts import team_matchup_intelligence as scouting
from scripts.advanced_matchup_interactions import interactions

STATUS="NEXTGEN_MATCHED_WALKFORWARD_RESEARCH_ONLY"
CORE=tuple(v03.FEATURES)
STYLE=(
    "home_run_edge","away_run_edge","home_pass_edge","away_pass_edge",
    "home_pressure_exposure","away_pressure_exposure",
    "home_redzone_conversion","away_redzone_conversion",
)
ADJUSTED=tuple(scouting.ADJUSTED_FIELDS)
NONLINEAR=tuple("nonlinear_"+k for k in (
    "home_pressure_times_pass_reliance",
    "away_pressure_times_pass_reliance",
    "home_run_off_vs_away_run_def",
    "away_run_off_vs_home_run_def",
    "home_pass_explosiveness_vs_away_pass_def",
    "away_pass_explosiveness_vs_home_pass_def",
    "pressure_reliance_gap","run_matchup_gap"))
TRAJECTORY=("home_pass_trajectory","away_pass_trajectory",
            "home_run_trajectory","away_run_trajectory")
TURNOVERS=tuple(scouting.TURNOVER_FIELDS)
GROUPS={
    "opponent_adjusted":ADJUSTED,
    "style_pressure":STYLE,
    "nonlinear_matchup":STYLE+NONLINEAR,
    "trajectory":TRAJECTORY,
    "verified_turnover_context":TURNOVERS,
    "combined":ADJUSTED+STYLE+NONLINEAR+TRAJECTORY+TURNOVERS,
}

def _mean(x):
    return sum(x)/len(x) if x else None

def _trajectory(history,field):
    # At least 4 separately completed games with opponent-adjusted
    # metrics, and no within-target-date observation.
    last=[float(r[field]) for r in history if r.get(field) is not None][-6:]
    if len(last)<4:return None
    return _mean(last[-2:])-_mean(last[-4:-2])

def add_temporal_features(games,advanced,turnovers=None):
    base={str(r["game_id"]):r for r in scouting.augment(games,advanced,turnovers)}
    verified=scouting.validated_turnovers(turnovers,games)
    history=defaultdict(list)
    for _,group in v03.group_by_date(games):
        # Freeze all teams' current-day profile before advancing ANY final.
        pending=[]
        for g in group:
            gid=str(g["game_id"])
            home,away=g["home"],g["away"]
            h=scouting._profile(history[home]);a=scouting._profile(history[away])
            base[gid].update({"nonlinear_"+k:v for k,v in interactions(h,a).items()})
            for side,records in (("home",history[home]),("away",history[away])):
                base[gid][side+"_pass_trajectory"]=_trajectory(records,"pass_off_adj")
                base[gid][side+"_run_trajectory"]=_trajectory(records,"run_off_adj")
        for g in group:
            for team in (g["home"],g["away"]):
                opponent=g["away"] if team==g["home"] else g["home"]
                prior=scouting._profile(history[opponent])
                record=scouting._team_game(g,team,advanced,verified)
                for kind in ("run","pass"):
                    record[kind+"_off_adj"]=(
                        record[kind+"_off"]-prior[kind+"_def_allowed"]
                        if (record[kind+"_off"] is not None and
                            prior[kind+"_def_allowed"] is not None and
                            prior[kind+"_def_games"]>=scouting.MIN_OPPONENT_ADJUST_GAMES)
                        else None)
                    record[kind+"_def_adj"]=(
                        record[kind+"_def_allowed"]-prior[kind+"_off"]
                        if (record[kind+"_def_allowed"] is not None and
                            prior[kind+"_off"] is not None and
                            prior[kind+"_off_games"]>=scouting.MIN_OPPONENT_ADJUST_GAMES)
                        else None)
                pending.append((team,record))
        for team,record in pending:
            history[team].append(record)
    return list(base.values())

def _has(row,fields):
    return all(type(row.get(f)) in (int,float) and math.isfinite(row[f]) for f in fields)

def _grade(test,preds,sigma):
    stats=[]
    for row,p in zip(test,preds):
        margin=float(max(-55,min(55,p[0])))
        total=float(max(0,min(110,p[1])))
        actual=float(row["home_score"])-float(row["away_score"])
        actual_total=float(row["home_score"])+float(row["away_score"])
        prob=.5*(1+math.erf(margin/(max(7.,sigma)*math.sqrt(2))))
        stats.append({
            "game_id":str(row["game_id"]),"date":row["date"],
            "actual_margin":actual,"pred_margin":round(margin,5),
            "actual_total":actual_total,"pred_total":round(total,5),
            "margin_absolute_error":abs(margin-actual),
            "total_absolute_error":abs(total-actual_total),
            "margin_signed_error":margin-actual,
            "su_correct":int((margin>0)==(actual>0)) if actual else None,
            "su_brier":(prob-int(actual>0))**2 if actual else None,
            "su_probability_home":round(prob,6),
        })
    return stats

def _aggregate(rows):
    n=len(rows)
    if not n:return None
    def avg(field):
        x=[r[field] for r in rows if r.get(field) is not None]
        return round(sum(x)/len(x),5) if x else None
    return {"games":n,"margin_mae":avg("margin_absolute_error"),
        "total_mae":avg("total_absolute_error"),
        "signed_home_bias":avg("margin_signed_error"),
        "su_accuracy":avg("su_correct"),
        "su_brier":avg("su_brier")}

def evaluate(rows,start="2026-09-26",min_train=90,min_test=1,penalty=45.):
    if not rows or min_train<20 or min_test<1 or penalty<=0:
        raise ValueError("Invalid backtest size or regularization policy")
    ids=set()
    for r in rows:
        if str(r["game_id"]) in ids:raise ValueError("Repeated game across folds")
        ids.add(str(r["game_id"]))
        if (r.get("betting_status")!="PASS_UNVALIDATED" or
            r.get("feature_evidence_status")!="RETROSPECTIVE_NOT_PUBLICATION_VERIFIED"):
            raise ValueError("Untrusted historical football feature row")
    last=max(dt.date.fromisoformat(r["date"]) for r in rows)
    start_date=dt.date.fromisoformat(start)
    details=defaultdict(list);folds=[];excluded=defaultdict(int)
    for step in range(30):
        first=start_date+dt.timedelta(days=7*step)
        if first>last:break
        end=first+dt.timedelta(days=7)
        train=[r for r in rows if dt.date.fromisoformat(r["date"])<first
               and r["home_games_prior"]>=1 and r["away_games_prior"]>=1]
        test=[r for r in rows if first<=dt.date.fromisoformat(r["date"])<end
              and r["home_games_prior"]>=1 and r["away_games_prior"]>=1]
        if not test:continue
        fold={"first_test_date":first.isoformat(),"train_pool":len(train),
              "test_pool":len(test),"model_cohorts":{}}
        for name,extras in GROUPS.items():
            matched_train=[r for r in train if _has(r,CORE+extras)]
            matched_test=[r for r in test if _has(r,CORE+extras)]
            missing_train=len(train)-len(matched_train)
            missing_test=len(test)-len(matched_test)
            if len(matched_train)<min_train or len(matched_test)<min_test:
                excluded[name]+=len(test)
                fold["model_cohorts"][name]={
                    "status":"PASS_COVERAGE_OR_TRAINING_INSUFFICIENT",
                    "matched_train_games":len(matched_train),
                    "matched_test_games":len(matched_test),
                    "missing_train":missing_train,"missing_test":missing_test,
                }
                continue
            # Both baseline & candidate train on exactly the same matched rows.
            control=v03.fit_ridge(matched_train,CORE,penalty=penalty)
            candidate=v03.fit_ridge(matched_train,CORE+extras,penalty=penalty)
            control_preds,sigma0=v03.predict(matched_test,CORE,control)
            candidate_preds,sigma1=v03.predict(matched_test,CORE+extras,candidate)
            before=_grade(matched_test,control_preds,sigma0)
            after=_grade(matched_test,candidate_preds,sigma1)
            for b,a in zip(before,after):
                if b["game_id"]!=a["game_id"]:raise ValueError("Paired predictions misaligned")
                details[name].append({"week_start":first.isoformat(),
                    "game_id":b["game_id"],"v03":b,"candidate":a})
            fold["model_cohorts"][name]={
                "status":"RESEARCH_MATCHED_HELDOUT",
                "matched_train_games":len(matched_train),
                "matched_test_games":len(matched_test),
                "missing_train":missing_train,"missing_test":missing_test,
                "v03":_aggregate(before),"candidate":_aggregate(after)}
        folds.append(fold)
    aggregate={}
    for name in GROUPS:
        matched=details[name]
        base=[x["v03"] for x in matched]
        candidate=[x["candidate"] for x in matched]
        a,b=_aggregate(base),_aggregate(candidate)
        aggregate[name]={
            "status":"RETROSPECTIVE_PAIRED_EVIDENCE_NOT_PROSPECTIVE"
                     if matched else "NO_MATCHED_GAMES_TO_TEST",
            "paired_games":len(matched),"v03_same_cohort":a,"candidate":b,
            "delta_margin_mae":round(b["margin_mae"]-a["margin_mae"],5) if a else None,
            "delta_total_mae":round(b["total_mae"]-a["total_mae"],5) if a else None,
            "delta_su_brier":round(b["su_brier"]-a["su_brier"],5)
                if a and a["su_brier"] is not None and b["su_brier"] is not None else None,
            "no_promotion_reason":"RETROSPECTIVE_PBP_PUBLICATION_NOT_AUTHENTICATED",
        }
    return {"status":STATUS,"season":2026,
        "source_timing":"RETROSPECTIVE_PBP_REVISED_NOT_ORIGINAL_POINT_IN_TIME",
        "folds":folds,"summary":aggregate,
        "feature_groups":{k:list(v) for k,v in GROUPS.items()},
        "paired_game_predictions":{k:v for k,v in details.items()},
        "skipped_test_game_slots":dict(excluded),
        "automatic_model_promotion":False,"model_promoted":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

def run(games_path,advanced_path,manifest_path,turnovers_path,output):
    games,advanced,_=v03.load_inputs(games_path,advanced_path,manifest_path)
    turns=json.loads(Path(turnovers_path).read_text()) if turnovers_path else None
    rows=add_temporal_features(games,advanced,turns)
    result=evaluate(rows)
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":STATUS,"matched_games":{
        k:v["paired_games"] for k,v in result["summary"].items()},
        "model_promoted":False}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True);p.add_argument("--advanced",required=True)
    p.add_argument("--manifest",required=True);p.add_argument("--turnovers")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.games,a.advanced,a.manifest,a.turnovers,a.output)

"""V08 opponent-specific challenger: compare on identical V04 held-out games.

This is a chronological *game-label* backtest, not a genuine 2026 as-published
predecision PBP replay: historical data were downloaded retrospectively. Never
retrofit it to the 2026 performance tab or promote a model from these folds.
V04 is refit using ALL prior completed games as it was designed; each
matchup-focused challenger uses only its *eligible* prior-date features.
A mismatch in observed identity/scores fails closed rather than earning a win.
"""
import argparse
import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts import model_v03 as basic
from scripts import v04_direct_scores as v04
from scripts.nextgen_walkforward import (
    add_temporal_features,CORE,ADJUSTED,NONLINEAR,TURNOVERS,REDZONE,
    PRESSURE,TRAJECTORY,EXPLOSIVES,_has,_aggregate,_grade)

STATUS="V08_OPPONENT_MATCHUP_V04_COHORT_CHALLENGE_RESEARCH_ONLY"
# No automatic feature-search winner, no coefficients chosen from the test slate.
FAMILIES={
 "run_pass_defense":ADJUSTED,
 "pressure_vs_passing":PRESSURE+("pass_rate_difference",
       "nonlinear_home_pressure_times_pass_reliance",
       "nonlinear_away_pressure_times_pass_reliance"),
 "explosives_vs_defense":EXPLOSIVES+(
       "nonlinear_home_pass_explosiveness_vs_away_pass_def",
       "nonlinear_away_pass_explosiveness_vs_home_pass_def"),
 "redzone_play_success":REDZONE,
 "giveaways_vs_takeaways":TURNOVERS,
 "combined":ADJUSTED+PRESSURE+EXPLOSIVES+REDZONE+TURNOVERS+TRAJECTORY,
}
MIN_TRAINING=90
MIN_HELDOUT=8
MAX_MARGIN=55
MAX_TOTAL=110


def _baseline(games,matched,at):
    past=[g for g in games if dt.date.fromisoformat(g["date"])<
          dt.date.fromisoformat(at)]
    vmodel=v04.fit(past,at+"T12:00:00+00:00")
    baseline={}
    for row in matched:
        gid=str(row["game_id"])
        original=next((g for g in games if str(g["game_id"])==gid),None)
        if original is None:raise ValueError("Matchup has no matched ESPN source game")
        # Strong source pairing: a PBP matchup row cannot swap opponent
        # identities or alter actual score labels in a retrospective replay.
        if (row["home"]!=original["home"] or row["away"]!=original["away"] or
            row["date"]!=original["date"] or
            row["kickoff_utc"]!=original["kickoff_utc"] or
            int(row["home_score"])!=int(original["home_score"]) or
            int(row["away_score"])!=int(original["away_score"])):
            raise ValueError("V04 and matchup game labels/source identities differ")
        neutral=original.get("neutral")
        if neutral not in ("True","False"):
            raise ValueError("Missing sourced neutral site for V04 comparison")
        pred=v04.predict(vmodel,original["home"],original["away"],neutral=="True")
        if pred:
            baseline[gid]=(pred["home_margin"],pred["total_points"])
    return baseline


def evaluate(games,rows,start="2026-09-26",min_train=MIN_TRAINING,
             min_test=MIN_HELDOUT):
    if not games or not rows or min_train<40 or min_test<1:
        raise ValueError("Insufficient or invalid CFB matchup comparison")
    ids={str(g["game_id"]) for g in games}
    if len(ids)!=len(games):raise ValueError("Duplicate ESPN scoreboard game")
    observed=set()
    for row in rows:
        gid=str(row["game_id"])
        if (gid in observed or gid not in ids or
            row.get("betting_status")!="PASS_UNVALIDATED" or
            row.get("feature_evidence_status")!="RETROSPECTIVE_NOT_PUBLICATION_VERIFIED"):
            raise ValueError("Untrusted/duplicate retrospective feature game")
        observed.add(gid)
    last=max(dt.date.fromisoformat(g["date"]) for g in games)
    first=dt.date.fromisoformat(start)
    folds=[]; pairs=defaultdict(list)
    for step in range(30):
        cutoff=first+dt.timedelta(days=7*step)
        if cutoff>last:break
        ending=cutoff+dt.timedelta(days=7)
        train=[r for r in rows if dt.date.fromisoformat(r["date"])<cutoff and
               min(r["home_games_prior"],r["away_games_prior"])>=1]
        test=[r for r in rows if cutoff<=dt.date.fromisoformat(r["date"])<ending
              and min(r["home_games_prior"],r["away_games_prior"])>=1]
        if not test:continue
        report={"cutoff":cutoff.isoformat(),"train_pool":len(train),
                "test_pool":len(test),"model_cohorts":{}}
        if len(train)<min_train:continue
        v04_baselines=_baseline(games,test,cutoff.isoformat())
        for name,features in FAMILIES.items():
            columns=CORE+tuple(features)
            training=[r for r in train if _has(r,columns)]
            heldout=[r for r in test if _has(r,columns)
                     and str(r["game_id"]) in v04_baselines]
            cohort={
                "training_games":len(training),"heldout_games":len(heldout),
                "missing_or_incomplete_test":len(test)-len(heldout),
                "identical_game_ids_for_baseline_and_challenger":True}
            if len(training)<min_train or len(heldout)<min_test:
                report["model_cohorts"][name]={
                    **cohort,"status":"PASS_INSUFFICIENT_PRIOR_FEATURE_COVERAGE"}
                continue
            # Both targets (margin and total) are fit with past-only
            # opponent-style interactions, no final score from heldout.
            params=basic.fit_ridge(training,columns)
            scores,sigma=basic.predict(heldout,columns,params)
            control=[v04_baselines[str(r["game_id"])] for r in heldout]
            before=_grade(heldout,control,14.0) # no V04 calibrated probability
            after=_grade(heldout,scores,sigma)
            for row,a,b in zip(heldout,before,after):
                if str(row["game_id"])!=a["game_id"] or a["game_id"]!=b["game_id"]:
                    raise ValueError("V04 versus matchup comparison game mismatch")
                pairs[name].append({
                    "game_id":a["game_id"],"cutoff":cutoff.isoformat(),
                    "v04":a,"candidate":b})
            cohort.update({
                "status":"RETROSPECTIVE_SAME_GAME_V04_V08_COMPARISON",
                "v04":_aggregate(before),"matchup_challenger":_aggregate(after),
                "v04_brier_not_calibrated":True})
            report["model_cohorts"][name]=cohort
        folds.append(report)
    aggregate={}
    for name in FAMILIES:
        data=pairs[name]
        before=_aggregate([x["v04"] for x in data])
        after=_aggregate([x["candidate"] for x in data])
        aggregate[name]={
            "paired_games":len(data),
            "status":"RETROSPECTIVE_RESEARCH_ONLY" if data else "PASS_NO_MATCHED_GAMES",
            "v04_same_cohort":before,"candidate":after,
            "delta_margin_mae":round(after["margin_mae"]-before["margin_mae"],5)
                if before else None,
            "delta_total_mae":round(after["total_mae"]-before["total_mae"],5)
                if before else None,
            "feature_coverage_not_imputed":True,
            "not_permitted_for_2026_retroactive_pregame_grade":True}
    return {
        "status":STATUS,"season":2026,"folds":folds,
        "families":{k:list(CORE+v) for k,v in FAMILIES.items()},
        "summary":aggregate,"paired_predictions":dict(pairs),
        "no_source_timing_proof_for_historical_pbp":True,
        "provisional_brier_not_comparable_to_calibrated_v04":True,
        "not_genuine_prospective_validation":True,
        "market_lines_in_fit":False,"changes_frozen_v04_predictions":False,
        "betting_status":"PASS_UNVALIDATED","model_promoted":False,
        "safe_for_betting":False}


def run(games,advanced,manifest,turnovers,output):
    complete,advanced,_=basic.load_inputs(games,advanced,manifest)
    source=json.loads(Path(turnovers).read_text()) if turnovers else None
    rows=add_temporal_features(complete,advanced,source)
    result=evaluate(complete,rows)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":STATUS,"paired_games":{
        name:res["paired_games"] for name,res in result["summary"].items()},
        "model_promoted":False}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for flag in ("games","advanced","manifest","output"):
        p.add_argument("--"+flag,required=True)
    p.add_argument("--turnovers")
    a=p.parse_args()
    run(a.games,a.advanced,a.manifest,a.turnovers,a.output)

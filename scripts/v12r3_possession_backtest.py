"""V12R3 historical same-cohort ablation with frozen V04/V11 controls.

Uses the already executed V12R2 artifact; V11+learned-pace is independently
replayed and rejected on ANY drift. Only extra context additions are compared.
Not proof that 2026 source records were first published before earlier games.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.v10_possession_sim import advanced_index,fit,simulate as simulate_v11
from scripts.possession_drive_ingest import STATUS as DRIVE_STATUS
from scripts.v11_dated_profile_bridge import bridge
from scripts.v12_regularized_hazards import train as train_hazards,pace_profile
from scripts.v12r3_possession_context import (
    STATUS as R3_STATUS,fit_context,matchup_pace)
from scripts.v12_possession_backtest import (
    REPORT as V12_REPORT,_metric,_crps,_distribution_grade)

STATUS="V12R3_MATCHED_V04_V11_OPPONENT_PACE_FIELD_REDZONE_RESEARCH_ONLY"
BASELINE=("v04","v11_dated_opponent_epa","v11_learned_pace_only",
          "v12r2_empirical_hazards_learned_pace")
VARIANTS=("v12r3_opponent_pace","v12r3_original_pace_field",
          "v12r3_original_pace_redzone","v12r3_original_pace_field_redzone",
          "v12r3_opponent_pace_field_redzone")


def evaluate(old,source,advanced,profiles,trials=2000):
    if (old.get("status")!=V12_REPORT or old.get("matched_games")!=377 or
        old.get("model_promoted") is not False or
        old.get("historical_source_first_publication_verified") is not False or
        old.get("training_is_strictly_before_week") is not True or
        source.get("status")!=DRIVE_STATUS or source.get("games_accepted")!=387 or
        len(source.get("games",[]))!=387 or
        source.get("historical_pregame_publication_times_verified") is not False or
        trials!=2000):
        raise ValueError("V12R3 requires authentic SAME-cohort 2000-draw V12R2 baseline")
    source_games=source["games"]
    rows=[];by_week={};seen=set()
    for old_game in old["games"]:
        gid=str(old_game["game_id"])
        if gid in seen:raise ValueError("Duplicate original held-out case")
        seen.add(gid)
        cutoff=old_game["cutoff"]
        target={"game_id":gid,"date":cutoff,
                "home":old_game["home"],"away":old_game["away"]}
        model=fit(source_games,advanced,target)
        if not model["ready"]:
            raise ValueError("Lost original source-aligned V11 fit")
        if cutoff not in by_week:
            context=fit_context(source_games,model,cutoff)
            original_pace=train_hazards(source_games,[],cutoff)
            if not original_pace.get("ready"):
                raise ValueError("Missing strictly earlier-week original pace")
            by_week[cutoff]=(context,original_pace)
        ctx,hazard=by_week[cutoff]
        if (ctx["status"]!=R3_STATUS or
            any(x["date"]>=cutoff for x in hazard["observed_pace"])):
            raise ValueError("Leaked held-out game to R3 context")
        freeze=old_game["v04"]
        prior={"source":"EARLIER_FOLD_V04",
               "game_id":gid,"asof_cutoff":cutoff,
               "home_points":freeze["home_points"],"away_points":freeze["away_points"]}
        p=profiles["profiles"][gid]
        seed=int(hashlib.sha256(("v11|"+gid).encode()).hexdigest()[:16],16)
        historical=pace_profile(hazard,old_game["home"],old_game["away"])
        opponent=matchup_pace(ctx,old_game["home"],old_game["away"])
        # Reconfirm previous accepted V11 + pace from original V12R2 artifact.
        replay=simulate_v11(model,True,trials=trials,seed=seed,
                            regress_turnovers=True,v04_prior=prior,dated_profile=p,
                            return_draws=True,pace_override=historical)
        old_replay=old_game["simulations"]["v11_learned_pace_only"]
        for raw,key in (("home_points_mean","home_points"),("away_points_mean","away_points"),
                        ("home_margin_mean","margin"),("total_mean","total"),
                        ("home_win_probability","home_win_probability")):
            if abs(replay[raw]-old_replay[key])>1e-5:
                raise ValueError("Frozen V11+pace replay drift: "+gid+" "+raw)
        # Source-frozen scored controls remain unchanged.
        row=dict(old_game)
        row["simulations"]=dict(old_game["simulations"])
        row["r3_source"]={"cutoff_date_exclusive":cutoff,
                          "source_prior_games":ctx["source_games"],
                          "prior_game_ids":ctx["source_prior_game_ids"],
                          "opponent_tempo":opponent["team_role_estimates"],
                          "first_publication_verified":False,
                          "availability_effects_used":False}
        act_margin=old_game["final_home"]-old_game["final_away"]
        act_total=old_game["final_home"]+old_game["final_away"]
        sp=old_game["market"].get("home_spread")
        total_line=old_game["market"].get("total")
        configs=(
            (VARIANTS[0],opponent,False,False),
            (VARIANTS[1],historical,True,False),
            (VARIANTS[2],historical,False,True),
            (VARIANTS[3],historical,True,True),
            (VARIANTS[4],opponent,True,True))
        for name,pace,field,rz in configs:
            forecast=simulate_v11(
                model,True,trials=trials,seed=seed,regress_turnovers=True,
                v04_prior=prior,dated_profile=p,return_draws=True,
                pace_override=pace,r3_context=ctx,r3_field=field,r3_redzone=rz)
            margins=forecast.pop("margin_draws")
            totals=forecast.pop("total_draws")
            row["simulations"][name]={
                "margin":forecast["home_margin_mean"],
                "total":forecast["total_mean"],
                "home_points":forecast["home_points_mean"],
                "away_points":forecast["away_points_mean"],
                "home_win_probability":forecast["home_win_probability"]}
            row[name+"_probabilities"]={
                "home_win":forecast["home_win_probability"],
                "home_cover":(sum(x+sp>0 for x in margins)/trials
                               if sp is not None else None),
                "over":(sum(x>total_line for x in totals)/trials
                        if total_line is not None else None)}
            grade={}
            for key,draws,y in (("margin",margins,act_margin),("total",totals,act_total)):
                sorted_draws=sorted(draws)
                lo=sorted_draws[int((trials-1)*.10)]
                hi=sorted_draws[int((trials-1)*.90)]
                grade[key]={"crps":_crps(draws,y),
                            "within_80pct_interval":int(lo<=y<=hi),
                            "width":hi-lo,"p10":lo,"p90":hi}
            row[name+"_calibration"]=grade
        rows.append(row)
    versions=BASELINE+VARIANTS
    def summary(games):
        return {"games":len(games),
                "models":{x:_metric(games,x) for x in versions},
                "distribution_calibration":{
                    x:_distribution_grade(games,x if x!="v11_learned_pace_only"
                                         else "v11_learned_pace_only")
                    for x in versions if x!="v04" and x!="v11_dated_opponent_epa"}}
    weekly={w:summary([r for r in rows if r["cutoff"]==w])
            for w in sorted(by_week)}
    overall=summary(rows)
    return {"status":STATUS,"matched_games":len(rows),"original_weeks":len(by_week),
            "source_games":387,"trials_per_game":trials,
            "models":overall["models"],
            "distribution_calibration":overall["distribution_calibration"],
            "weekly":weekly,"games":rows,
            "historical_source_first_publication_verified":False,
            "player_availability_scoring_used":False,
            "model_promoted":False,"promotion_eligible":False,
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
            "limitations":[
                "Historical original ESPN PBP first-publication times unauthenticated",
                "Same previously examined 377-game 2026 slate; NOT independent validation",
                "Bookmaker quotes only for observed 156 ATS and 154 totals rows",
                "No source-proven historical QB, injury or weather effects",
                "Fixed empirical corrections; no market-edge promotion allowed"]}


def run(previous,drives,games,advanced,manifest,output,trials=2000):
    archive=json.loads(Path(previous).read_text())
    source=json.loads(Path(drives).read_text())
    targets=[{"game_id":str(r["game_id"]),"home":r["home"],"away":r["away"],
              "cutoff":r["cutoff"],"home_points":r["v04"]["home_points"],
              "away_points":r["v04"]["away_points"]}
              for r in archive["games"]]
    profiles=bridge(games,advanced,manifest,targets)
    outcome=evaluate(archive,source,advanced_index(advanced),profiles,trials)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(outcome,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:outcome[k] for k in
         ("status","matched_games","original_weeks","models",
          "distribution_calibration","promotion_eligible")},sort_keys=True))
    return outcome

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("previous","drives","games","advanced","manifest","output"):
        p.add_argument("--"+key,required=True)
    p.add_argument("--trials",type=int,default=2000)
    args=p.parse_args()
    run(args.previous,args.drives,args.games,args.advanced,args.manifest,args.output,
        args.trials)

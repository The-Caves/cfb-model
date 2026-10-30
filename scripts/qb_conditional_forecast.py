"""Prospectively frozen QB-conditioned research projections, never live V03 picks.

A separately source-ranked expected starter (not always confirmed) determines
the *scenario* player. Historical named passers condition the already trained
V03 PASS EPA feature. No QB1/QB2/QB3 ordinal point penalty exists.

No prior player production => no QB adjustment, not a negative assignment.
All old provider PBP is retrospectively mutable; today's receipt is real but
this cannot validate hypothetical historical pregame player identity.
"""
import argparse,csv,datetime as dt,json,math
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.game_context import parse_time
from scripts.model_v03 import fit_ridge,predict
from scripts.personnel_forecast import verify as verify_baseline,checksum,_check_training,_fixed_rows
from scripts.personnel_features import BASE_FIELDS,verify_joined,sha256
from scripts.qb_passer_history import prior_qb_form
from scripts.qb_expected_starters import STATUS as EXPECTED_STATUS
from scripts.qb_scenario_exposure import mixture as qb_exposure,STATUS as EXPOSURE_STATUS

STATUS="QB_CONDITIONAL_PLAYER_EPA_FROZEN_SHADOW_RESEARCH_ONLY"
MODEL="QB_EXPECTED_PLAYER_PASS_EPA_CONDITIONAL_V1"
MIN_QB_PASS_EPA_PLAYS=15
SHRINK_PSEUDO_PLAYS=60.
MAX_EPA_INPUT_CHANGE=.7
MAX_SINGLE_QB_MARGIN_CHANGE=4.
MAX_DELAY_MINUTES=25

def _asof_day(game):
    return parse_time(game["kickoff_utc"]).astimezone(ZoneInfo("America/New_York")).date().isoformat()

def _condition(passer_rows,team,player,game_date,decision,team_epa,coefficient):
    if not player:return {"status":"PASS_UNKNOWN_PLAYER","player":None,
                          "margin_impact":0.,"reliability":0.}
    stat=prior_qb_form(passer_rows,team,player,game_date,decision.isoformat(),
                      minimum_pass_plays=MIN_QB_PASS_EPA_PLAYS)
    n=stat["prior_player_pass_tagged_plays"]
    player_epa=stat["player_epa_per_pass_tagged_play"]
    if player_epa is None or team_epa is None:
        return {"status":"PASS_NO_PRIOR_PLAYER_OR_TEAM_PASSING_SAMPLE",
                "player":player,"prior_passing_plays":n,
                "team_passing_epa":team_epa,"player_passing_epa":player_epa,
                "margin_impact":0.,"reliability":0.}
    if not math.isfinite(float(team_epa)):
        raise ValueError("Nonfinite team passing EPA")
    reliability=n/(n+SHRINK_PSEUDO_PLAYS)
    # Scores are updated only through the same historical-trained coefficient
    # as the V03 scoring model; no depth-chart rank appears in this function.
    expected_feature_delta=max(-MAX_EPA_INPUT_CHANGE,
                               min(MAX_EPA_INPUT_CHANGE,
                                   (player_epa-float(team_epa))*reliability))
    raw_points=expected_feature_delta*coefficient
    points=max(-MAX_SINGLE_QB_MARGIN_CHANGE,min(MAX_SINGLE_QB_MARGIN_CHANGE,raw_points))
    return {"status":"PLAYER_CONDITIONED_RESEARCH_ONLY",
            "player":player,"prior_passing_plays":n,
            "prior_player_games":stat["prior_player_games"],
            "team_passing_epa":round(float(team_epa),6),
            "player_passing_epa":player_epa,
            "team_replacement_epa_comparison":stat["within_team_player_minus_other_epa"],
            "reliability":round(reliability,6),
            "pass_epa_feature_delta":round(expected_feature_delta,6),
            "margin_impact":round(points,5),
            "no_depth_chart_rank_penalty":True}

def scenario(forecast,joined_game,source_by_side,passer_rows,params,decision):
    projection=forecast["projection"]
    baseline_margin=projection["predicted_home_margin"]
    total=projection["predicted_total_points"]
    if baseline_margin is None or total is None:
        return {"status":"PASS_NO_BASELINE","expected_projection":None,"scenarios":{}}
    coefs,means,stds,_=params
    index=BASE_FIELDS.index("pass_epa_form")
    coefficient=float(coefs[index+1,0]/stds[index])
    if not math.isfinite(coefficient):raise ValueError("Invalid learned QB coefficient")
    day=_asof_day(forecast)
    candidates={}
    chosen={}
    empirical={}
    exposure_impact={}
    sample_exposure={}
    for side in ("home","away"):
        slot=source_by_side[side]
        team=forecast[side]
        pooled=joined_game["team_profiles"][side]["recent_form"].get("epa_pass")
        players={r["player"]:r for r in slot["scenarios"]}
        if slot["starter"] and slot["starter"] not in players:
            players[slot["starter"]]={"player":slot["starter"],"depth_rank":slot["depth_rank"]}
        evaluated={}
        for name,r in players.items():
            item=_condition(passer_rows,team,name,day,decision,pooled,coefficient)
            evaluated[name]={**item,"depth_rank":r["depth_rank"],
                             "depth_label":("QB"+str(r["depth_rank"])
                                             if r["depth_rank"] else "UNKNOWN")}
        candidates[side]=evaluated
        chosen[side]=(evaluated.get(slot["starter"]) if slot["starter"] else None)
        exposure=qb_exposure(passer_rows,team,slot,day,decision.isoformat())
        empirical[side]=exposure
        weighted_points=0.
        valid_sample_mass=0.
        for name,weight in exposure["weights"].items():
            if name not in evaluated:raise ValueError("Scenario exposure not matched to evaluated QB")
            if not 0<=weight<=1:raise ValueError("Invalid empirical passer exposure")
            item=evaluated[name]
            weighted_points+=weight*item["margin_impact"]
            if item["status"]=="PLAYER_CONDITIONED_RESEARCH_ONLY":
                valid_sample_mass+=weight
        exposure_impact[side]=weighted_points
        sample_exposure[side]=round(valid_sample_mass,8)
    home=chosen["home"];away=chosen["away"]
    # Every QB1/2/3 chart member gets a separate *conditional score margin*,
    # not merely a depth ranking or a vague positive/negative annotation.
    # The opposite side is held to its selected expected QB scenario, or
    # baseline if still UNKNOWN, with uncertainty explicitly retained.
    player_scenarios={}
    limit=min(55.,float(total))
    for side,players in candidates.items():
        opposite=(away if side=="home" else home)
        opposite_points=opposite["margin_impact"] if opposite else 0.
        scenarios={}
        for name,item in players.items():
            delta=(item["margin_impact"]-opposite_points if side=="home"
                   else opposite_points-item["margin_impact"])
            adjusted_scenario=max(-limit,min(limit,float(baseline_margin)+delta))
            scenarios[name]={**item,
                "conditional_predicted_home_margin":round(adjusted_scenario,5)
                    if item["status"]=="PLAYER_CONDITIONED_RESEARCH_ONLY" else None,
                "conditional_status":("PLAYER_EPA_MODEL_FORECAST" if item["status"]==
                    "PLAYER_CONDITIONED_RESEARCH_ONLY" else "PASS_NO_PLAYER_EPA"),
                "opponent_qb_source_status":source_by_side[
                    "away" if side=="home" else "home"]["starter_status"]}
        player_scenarios[side]=scenarios
    home=chosen["home"];away=chosen["away"]
    corrections=sum((home["margin_impact"] if home else 0.,
                     -(away["margin_impact"] if away else 0.)))
    limit=min(55.,float(total))
    adjusted=max(-limit,min(limit,float(baseline_margin)+corrections))
    coverage=[r["status"] if r else "PASS_NO_EXPECTED_STARTER" for r in (home,away)]
    adjusted_sides=sum(v=="PLAYER_CONDITIONED_RESEARCH_ONLY" for v in coverage)
    status=("QB_PLAYER_CONDITIONAL_SHADOW" if adjusted_sides else
            "PASS_NO_VERIFIED_PERFORMANCE_SAMPLE")
    # Uncalibrated *participation-exposure* mixtures are distinct from
    # projected-starter point estimates. Unknown/missing QBs retain the
    # original zero-adjustment V03 reference, not a fictitious backup penalty.
    usage_delta=exposure_impact["home"]-exposure_impact["away"]
    usage_margin=max(-limit,min(limit,float(baseline_margin)+usage_delta))
    usage_status=("QB_EMPIRICAL_EXPOSURE_SHADOW" if
                  any(v>0 for v in sample_exposure.values()) else
                  "PASS_NO_RELIABLE_QB_EXPOSURE_AND_PASS_EPA")
    return {"status":status,"baseline_margin":baseline_margin,"adjusted_home_margin":round(adjusted,5),
        "usage_weighted_home_margin":round(usage_margin,5),
        "usage_weighted_margin_delta":round(usage_margin-float(baseline_margin),5),
        "usage_weighted_status":usage_status,
        "empirical_pass_exposure_by_side":empirical,
        "evaluated_player_sample_exposure_by_side":sample_exposure,
        "exposure_method":EXPOSURE_STATUS,
        "exposure_not_calibrated_next_game_starter_probabilities":True,
        "margin_delta":round(adjusted-float(baseline_margin),5),
        "unchanged_total":total,
        "expected_starters_by_side":{
            k:{"player":source_by_side[k]["starter"],
               "status":source_by_side[k]["starter_status"],
               "confidence":source_by_side[k]["confidence"],
               "depth_rank":source_by_side[k]["depth_rank"],
               "source_url":source_by_side[k].get("chart_source_url")}
            for k in ("home","away")},
        "player_scenarios_by_side":player_scenarios,
        "expected_player_adjustments":chosen,
        "adjusted_side_count":adjusted_sides,
        "confidence":"RESEARCH_ONLY_NOT_CALIBRATED",
        "no_automatic_QB2_QB3_downgrade":True,"model_version":MODEL,
        "betting_status":"PASS_UNVALIDATED","model_promoted":False}

def build(frozen,joined,expected,passers,training_rows,observed_at_utc):
    verify_baseline(frozen);verify_joined(joined)
    decision=parse_time(observed_at_utc)
    forecast_time=parse_time(frozen["forecast_observed_utc"])
    source_time=parse_time(expected["observed_at_utc"])
    if (expected.get("status")!=EXPECTED_STATUS or expected.get("betting_status")!="PASS_UNVALIDATED"
        or not forecast_time<=decision or not source_time<=decision or
        (decision-max(source_time,forecast_time)).total_seconds()>MAX_DELAY_MINUTES*60):
        raise ValueError("Late or untrusted expected QB forecast")
    if (sha256(joined)!=frozen["joined_profile_sha256"]
        or frozen["model_training"]["training_game_ids_sha256"]!=checksum(
            sorted(str(r["game_id"]) for r in training_rows))):
        raise ValueError("Baseline and expected QB research not same training")
    ix={str(g["game_id"]):g for g in joined["games"]}
    src={(str(g["game_id"]),g["team"]):g for g in expected["games"]}
    if len(src)!=len(expected["games"]):raise ValueError("Duplicate expected QB slot")
    if len({str(g["game_id"]) for g in frozen["games"]})!=len(frozen["games"]):
        raise ValueError("Duplicate baseline projection")
    if len(training_rows)<90:raise ValueError("Insufficient score training")
    params=fit_ridge(training_rows,BASE_FIELDS)
    outputs=[]
    for forecast in frozen["games"]:
        gid=str(forecast["game_id"])
        if parse_time(forecast["kickoff_utc"])<=decision:continue
        current=ix.get(gid)
        if current is None:raise ValueError("No matched personnel capture")
        if (forecast["home"],forecast["away"],forecast["kickoff_utc"])!=(
            current["home"],current["away"],current["kickoff_utc"]):
            raise ValueError("Joined matchup changed after freeze")
        if forecast["feature_sha256"]!=current["record_sha256"]:
            raise ValueError("Baseline feature checksum mismatch")
        side={}
        for k in ("home","away"):
            slot=src.get((gid,forecast[k]))
            if slot is None or slot["opponent"]!=forecast["away" if k=="home" else "home"]:
                raise ValueError("Missing expected QB team slot")
            if parse_time(slot["observed_at_utc"])>decision:raise ValueError("Postdecision QB player")
            side[k]=slot
        result=scenario(forecast,current,side,passers,params,decision)
        outputs.append({"game_id":gid,"home":forecast["home"],"away":forecast["away"],
          "kickoff_utc":forecast["kickoff_utc"],"baseline_row_sha256":forecast["row_sha256"],
          "candidate":result})
    return {"status":STATUS,"season":2026,"observed_at_utc":decision.isoformat(),
         "baseline_forecast_run_id":frozen["run_id"],
         "baseline_forecast_sha256":checksum(frozen),
         "expected_qb_source_sha256":checksum(expected),
         "training_game_ids_sha256":frozen["model_training"]["training_game_ids_sha256"],
         "training_feature_sha256":frozen["model_training"]["training_features_sha256"],
         "summary":{"games":len(outputs),
            "games_with_qb_conditional_adjustment":sum(
                x["candidate"]["status"]=="QB_PLAYER_CONDITIONAL_SHADOW" for x in outputs),
            "sides_with_expected_player_history":sum(
                x["candidate"].get("adjusted_side_count",0) for x in outputs),
            "games_with_empirical_usage_margin":sum(
                x["candidate"]["usage_weighted_status"]=="QB_EMPIRICAL_EXPOSURE_SHADOW"
                for x in outputs),
            "sides_with_empirical_player_samples":sum(
                sum(v>0 for v in x["candidate"]["evaluated_player_sample_exposure_by_side"].values())
                for x in outputs)},
         "games":outputs,"model_promoted":False,
         "historical_pbp_publication_authenticated":False,
         "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

def run(forecast_file,joined_file,expected_file,passers_file,games_file,
        advanced_file,advanced_manifest,score_manifest,output):
    frozen=json.loads(Path(forecast_file).read_text())["record"]
    joined=json.loads(Path(joined_file).read_text())
    expected=json.loads(Path(expected_file).read_text())
    with open(passers_file,newline="",encoding="utf-8") as f:passers=list(csv.DictReader(f))
    games,advanced,_,_=_check_training(
        games_file,advanced_file,advanced_manifest,score_manifest,joined)
    training=_fixed_rows(games,advanced,parse_time(joined["captured_at_utc"]))
    result=build(frozen,joined,expected,passers,training,dt.datetime.now(dt.timezone.utc).isoformat())
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x") as f:json.dump(result,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({"status":STATUS,**result["summary"],
          "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("forecast","joined","expected","passers","games","advanced",
                "advanced-manifest","score-manifest","output"):
        p.add_argument("--"+key,required=True)
    a=p.parse_args()
    run(a.forecast,a.joined,a.expected,a.passers,a.games,a.advanced,
        a.advanced_manifest,a.score_manifest,a.output)

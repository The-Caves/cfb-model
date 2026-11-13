"""Publish reproducible prospective V09 score Monte Carlo shadows only.

No forecast, sportsbook, V04 decision, historical grade or settled result is
rewritten. Uses only earlier independently SETTLED V04 errors, with actual
pre-kickoff source capture; no contemporaneous or future result is trained on.
Score residual simulation is not a possession/drive simulation.
"""
import argparse,datetime as dt,json,math
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.game_context import parse_time
from scripts.v09_score_sim_backtest import read_frozen,simulate

STATUS="V09_SOURCE_TIMED_SCORE_MONTE_CARLO_SHADOW_RESEARCH_ONLY"
ET=ZoneInfo("America/New_York")
def number(x):return type(x) in (int,float) and math.isfinite(x)

def attach(board,history,now,min_train=24,trials=1200):
    now=parse_time(now)
    if (board.get("schema_version")!=2 or
        board.get("betting_status")!="PASS_UNVALIDATED" or
        not isinstance(board.get("games"),list)):
        raise ValueError("Not a source-qualified V09 dashboard")
    if not 10<=min_train<=150 or not 100<=trials<=5000:
        raise ValueError("Invalid V09 research simulation coverage")
    asof=parse_time(board["forecast_observed_utc"])
    if asof>now:raise ValueError("Future-dated V04 forecast")
    source_forecasts=json.dumps([(g.get("v04_direct_scores"),g.get("model_home_margin"),
        g.get("model_total"),g.get("model_ats_side"),g.get("model_ou_side"))
        for g in board["games"]],sort_keys=True)
    original_performance=json.dumps(board.get("prospective_records"),sort_keys=True)
    counts={"ready":0,"insufficient_history":0,"missing_v04":0,"kicked_off":0}
    for g in board["games"]:
        g["v09_score_shadows"]=None
        kickoff=parse_time(g["kickoff_utc"])
        if kickoff<=now or asof>=kickoff:
            counts["kicked_off"]+=1
            continue
        model=g.get("v04_direct_scores") or {}
        if (g.get("home_bias_quarantined") is not True or
            model.get("model")!="V04_INDEPENDENT_OPPONENT_ADJUSTED_SCORES_RESEARCH_ONLY" or
            model.get("status")!="SOURCE_OBSERVED_DIRECT_TEAM_SCORE_MODEL_RESEARCH_ONLY" or
            model.get("model_promoted") is not False or
            model.get("no_market_lines_in_training") is not True or
            model.get("direct_scoring_fit_uses_v03_total") is not False or
            not all(number(model.get(k)) for k in ("home_points","away_points","home_margin","total_points"))):
            counts["missing_v04"]+=1
            continue
        prior=[r for r in history if r["game_id"]!=str(g["game_id"])
            and parse_time(r["result_known_utc"])<=asof
            and parse_time(r["kickoff_utc"])<kickoff]
        if (len(prior)<min_train or
            len({parse_time(r["kickoff_utc"]).astimezone(ET).date() for r in prior})<2):
            counts["insufficient_history"]+=1
            continue
        provider=g.get("market_provider")
        observed=g.get("market_observed_utc")
        valid_market=bool(provider and observed and
            parse_time(observed)<=now and parse_time(observed)<kickoff)
        spread=g.get("market_home_spread")
        total=g.get("market_total")
        target={"game_id":str(g["game_id"]),"home":g["home_team"],"away":g["away_team"],
                "kickoff_utc":g["kickoff_utc"],"forecast_utc":board["forecast_observed_utc"],
                "home_points":model["home_points"],"away_points":model["away_points"],
                "market":{
                    "home_spread":float(spread) if valid_market and number(spread) and abs(spread)<80 else None,
                    "total":float(total) if valid_market and number(total) and 0<total<150 else None,
                    "provider":provider if valid_market else None,
                    "observed_at_utc":observed if valid_market else None,
                }}
        versions={name:simulate(target,prior,name,trials) for name in ("global","team_form")}
        g["v09_score_shadows"]={
            "status":STATUS,"simulation_type":"EMPIRICAL_PAIRED_V04_SCORE_RESIDUALS_NOT_DRIVE_SIMULATOR",
            "forecast_observed_utc":board["forecast_observed_utc"],
            "generated_at_utc":now.isoformat(),"source_provenance":"IMMUTABLE_CAPTURED_PREKICKOFF_SETTLED_V04",
            "earlier_settled_v04_games":len(prior),
            "earlier_game_days":len({parse_time(r["kickoff_utc"]).astimezone(ET).date() for r in prior}),
            "projections":versions,"market_comparison_source_timed":valid_market,
            "published_scores_unchanged":True,"historical_grades_unchanged":True,
            "model_promoted":False,"calibrated_betting_probability":False,
            "safe_for_betting":False}
        counts["ready"]+=1
    after=json.dumps([(g.get("v04_direct_scores"),g.get("model_home_margin"),
        g.get("model_total"),g.get("model_ats_side"),g.get("model_ou_side"))
        for g in board["games"]],sort_keys=True)
    if after!=source_forecasts or json.dumps(board.get("prospective_records"),sort_keys=True)!=original_performance:
        raise ValueError("V09 shadow altered original models or settled records")
    board["v09_shadow_display"]={
        "status":STATUS,**counts,"trials_per_model":trials,
        "source_history_games":len(history),"model_promoted":False,
        "first_pub_historic_2026_pbp_authenticated":False,
        "calibration_independently_proven":False,"frozen_model_scores_changed":False}
    return board

def run(root,dashboard,now=None,trials=1200):
    file=Path(dashboard);board=json.loads(file.read_text())
    now=now or dt.datetime.now(dt.timezone.utc).isoformat()
    history,coverage=read_frozen(root,now)
    out=attach(board,history,now,trials=trials)
    out["v09_shadow_display"]["verified_history_coverage"]=coverage
    file.write_text(json.dumps(out,indent=2,allow_nan=False)+"\n")
    print(json.dumps(out["v09_shadow_display"],sort_keys=True))
    return out

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",required=True)
    p.add_argument("--dashboard",required=True)
    p.add_argument("--trials",type=int,default=1200)
    a=p.parse_args()
    run(a.archive_root,a.dashboard,trials=a.trials)

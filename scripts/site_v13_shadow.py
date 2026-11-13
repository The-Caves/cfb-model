"""Attach V13 V04-centered probability SHADOW to current pregame website board.

No V03, V04, V05, archived research grades, or model side/totals picks changed.
Requires independently settled prior V04 forecasts with source-observed PREkick
receipts and result_known < current forecast observation. The V13 probability
overlay is published prospectively but remains explicitly experimental.

In particular it is not a possession simulation, not verified bookmaker EV,
and NOT a claimed promoted score-model challenger.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time
from scripts.v09_score_sim_backtest import read_frozen
from scripts.v13_v04_probabilities import (
    STATUS as PRED_STATUS, fit_uncertainty, predict, scores
)

STATUS="V13_SOURCE_TIMED_V04_PROBABILITY_SHADOW"
ET=ZoneInfo("America/New_York")


def _day(timestamp):
    return parse_time(timestamp).astimezone(ET).date().isoformat()


def _history_row(record,at,cutoff):
    if not isinstance(record,dict) or not record.get("snapshot_sha256"):
        return None
    try:
        forecast=parse_time(record["forecast_utc"])
        capture=parse_time(record["capture_utc"])
        kickoff=parse_time(record["kickoff_utc"])
        result=parse_time(record["result_known_utc"])
        if not (forecast<=capture<kickoff<result<=at and
                _day(record["kickoff_utc"])<cutoff and
                _day(record["forecast_utc"])<cutoff):
            return None
        home=record["home_points"];away=record["away_points"]
        if (type(home) not in (int,float) or type(away) not in (int,float) or
            not (0<=home<=130 and 0<=away<=130)):
            return None
        v={"home_points":home,"away_points":away,
           "margin":home-away,"total":home+away}
        scores(v)
        return {"game_id":str(record["game_id"]),
                "cutoff":_day(record["forecast_utc"]),
                "date":_day(record["kickoff_utc"]),"v04":v,
                "final_home":record["final_home"],"final_away":record["final_away"]}
    except (ValueError,KeyError,TypeError):
        return None


def attach(board,history,now,min_train=35):
    now=parse_time(now)
    if (board.get("schema_version")!=2 or
        board.get("betting_status")!="PASS_UNVALIDATED" or
        not isinstance(board.get("games"),list) or
        not isinstance(history,list) or type(min_train) is not int or
        not 0<=min_train<=300):
        raise ValueError("Invalid V13 research dashboard or historical evidence")
    source_at=parse_time(board["forecast_observed_utc"])
    if source_at>now:
        raise ValueError("Future V04 source cannot create V13 probability research")
    snapshot=json.dumps([{"v04":g.get("v04_direct_scores"),
        "model_home_margin":g.get("model_home_margin"),
        "model_total":g.get("model_total"),
        "model_ats_side":g.get("model_ats_side"),
        "model_ou_side":g.get("model_ou_side"),
        "v04_market_research":g.get("v04_market_research")}
        for g in board["games"]],sort_keys=True)
    settled=json.dumps(board.get("prospective_records"),sort_keys=True)
    available={"ready":0,"not_enough_prior_games":0,"unverified_v04":0,"kicked_off":0}
    cutoff=_day(board["forecast_observed_utc"])
    converted=[a for r in history if (a:=_history_row(r,source_at,cutoff)) is not None]
    ids=set()
    for r in converted:
        if r["game_id"] in ids:raise ValueError("Duplicate earlier settled V04 forecast game")
        ids.add(r["game_id"])
    calibration=fit_uncertainty(converted,cutoff)
    enough=(calibration["earlier_games"]>=min_train and
            calibration["earlier_weeks"]>=2)
    for g in board["games"]:
        g["v13_probability_shadow"]=None
        kickoff=parse_time(g["kickoff_utc"])
        if kickoff<=now or source_at>=kickoff:
            available["kicked_off"]+=1;continue
        v=g.get("v04_direct_scores")
        if g.get("home_bias_quarantined") is not True or v is None:
            available["unverified_v04"]+=1;continue
        try:
            scores(v,site=True)
        except ValueError:
            available["unverified_v04"]+=1;continue
        if not enough:
            available["not_enough_prior_games"]+=1;continue
        provider=g.get("market_provider")
        observed=g.get("market_observed_utc")
        market=None
        if provider and observed:
            quote_at=parse_time(observed)
            if quote_at<=now and quote_at<kickoff:
                market={"home_spread":g.get("market_home_spread"),
                        "total":g.get("market_total"),
                        "source":provider,"observed_at_utc":observed}
        prediction=predict(v,calibration,cutoff,variant="prior_variance",
                           market=market,site=True)
        prediction.update({
            "site_status":STATUS,"game_id":str(g["game_id"]),
            "home":g["home_team"],"away":g["away_team"],
            "kickoff_utc":g["kickoff_utc"],
            "original_forecast_observed_utc":board["forecast_observed_utc"],
            "generated_at_utc":now.isoformat(),
            "source_run_id":str(board["forecast_run_id"]) if board.get("forecast_run_id") else None,
            "original_v04_score_checksum_unchanged":True,
            "source_provenance":"IMMUTABLE_CAPTURED_PREKICKOFF_SETTLED_V04",
            "previous_frozen_grades_unchanged":True,
            "market_quote_eligible":market is not None,
            "research_probability_not_certified_betting_edge":True})
        g["v13_probability_shadow"]=prediction
        available["ready"]+=1
    after=json.dumps([{"v04":g.get("v04_direct_scores"),
        "model_home_margin":g.get("model_home_margin"),
        "model_total":g.get("model_total"),
        "model_ats_side":g.get("model_ats_side"),
        "model_ou_side":g.get("model_ou_side"),
        "v04_market_research":g.get("v04_market_research")}
        for g in board["games"]],sort_keys=True)
    if after!=snapshot or json.dumps(board.get("prospective_records"),sort_keys=True)!=settled:
        raise ValueError("V13 shadow must not modify original forecast/settled record")
    board["v13_probability_display"]={
        "status":STATUS,**available,
        "source_frozen_earlier_settled_games":len(converted),
        "prior_original_forecast_days":calibration["earlier_weeks"],
        "variant":"prior_variance",
        "updated_score_model_promoted":False,
        "original_v04_points_preserved":True,
        "historical_score_feed_first_publication_authenticated":False,
        "independent_prospective_improvement_proven":False,
        "model_replacement":False}
    return board


def run(archive_root,dashboard,now=None,min_train=35):
    path=Path(dashboard)
    board=json.loads(path.read_text())
    at=now or dt.datetime.now(dt.timezone.utc).isoformat()
    earlier,_=read_frozen(archive_root,at)
    output=attach(board,earlier,at,min_train=min_train)
    path.write_text(json.dumps(output,indent=2,allow_nan=False)+"\n")
    print(json.dumps(output["v13_probability_display"],sort_keys=True))
    return output


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--archive-root",required=True)
    parser.add_argument("--dashboard",required=True)
    parser.add_argument("--min-train",type=int,default=35)
    a=parser.parse_args()
    run(a.archive_root,a.dashboard,min_train=a.min_train)

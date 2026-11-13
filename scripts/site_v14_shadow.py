"""V14 opponent-matchup score shadow for prospective CFB website capture.

Original V04 game scores, V13 probabilities, old model picks/grades and market
sources are NEVER replaced. All V14 history is frozen original 2026 research,
without authenticated historical publication times. Current source manifest
and sportsbook quote must be captured before this V14 forecast and kickoff.

V14 forecast is RESEARCH ONLY, not an ATS selection or validated betting edge.
"""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time
from scripts.v13_v04_probabilities import scores as verify_v04
from scripts.v13_v04_backtest import STATUS as V13_ARCHIVE
from scripts.v14_matchup_features import load_inputs,profile,matchup
from scripts.v14_residual_challenger import fit as fit_scores,project
from scripts.v14_market_calibration import fit as fit_market,project as calc_prob

STATUS="V14_SOURCE_TIMED_OPPONENT_MATCHUP_SCORE_SHADOW"
ET=ZoneInfo("America/New_York")


def _historical_training(v13,source,cutoff):
    if (v13.get("status")!=V13_ARCHIVE or
        v13.get("original_cohort_games")!=377 or
        v13.get("historical_first_publication_authenticated") is not False or
        v13.get("model_promoted") is not False):
        raise ValueError("Missing immutable historical V13 comparison")
    dates={}
    rows=[]
    for g in v13["games"]:
        if g["date"]>=cutoff or g["cutoff"]>=cutoff:continue
        week=g["cutoff"]
        if week not in dates:dates[week]=profile(source,week)
        m=matchup(dates[week],g["home"],g["away"])
        rows.append({k:g[k] for k in
            ("game_id","home","away","date","cutoff","v04","market",
             "predictions","final_home","final_away")}|{"matchup":m})
    return rows


def attach(board,score_model,market_model,dated,now):
    at=parse_time(now)
    if (board.get("schema_version")!=2 or
        board.get("betting_status")!="PASS_UNVALIDATED" or
        not isinstance(board.get("games"),list)):
        raise ValueError("Invalid site input for V14")
    cutoff=at.astimezone(ET).date().isoformat()
    if (dated.get("cutoff")!=cutoff or
        score_model.get("cutoff_exclusive")!=cutoff or
        market_model.get("cutoff_exclusive")!=cutoff):
        raise ValueError("V14 current forecast and matchup source cutoff differ")
    before=json.dumps([{
        "v04":g.get("v04_direct_scores"),
        "v13":g.get("v13_probability_shadow"),
        "margin":g.get("model_home_margin"),
        "total":g.get("model_total"),
        "ats":g.get("model_ats_side"),
        "ou":g.get("model_ou_side")}
        for g in board["games"]],sort_keys=True)
    accepted=0;missing=0;started=0;gates=0
    for g in board["games"]:
        g["v14_matchup_shadow"]=None
        kickoff=parse_time(g["kickoff_utc"])
        if kickoff<=at:
            started+=1;continue
        source=g.get("v04_direct_scores")
        if g.get("home_bias_quarantined") is not True or source is None:
            missing+=1;continue
        try:
            orig=verify_v04(source,site=True)
        except ValueError:
            missing+=1;continue
        if score_model["models"]["margin"]["ready"] is not True:
            gates+=1;continue
        match=matchup(dated,g["home_team"],g["away_team"])
        if not match["ready"]:
            missing+=1;continue
        market=None
        if g.get("market_provider") and g.get("market_observed_utc"):
            quote_at=parse_time(g["market_observed_utc"])
            if quote_at<=at and quote_at<kickoff:
                market={"provider":g["market_provider"],
                        "home_spread":g.get("market_home_spread"),
                        "total":g.get("market_total")}
        p=project(orig,match,score_model,cutoff,variant="joint_close")
        prior=g.get("v13_probability_shadow")
        if (prior is None or
            prior.get("status")!="V13_V04_ANCHORED_PROBABILITIES_RESEARCH_ONLY" or
            prior.get("v04_mean_scores_unchanged") is not True or
            prior.get("calibration_prospectively_proven") is not False):
            # V14 point challenger can still be displayed, but never fabricate
            # ATS/OU uncertainty if source-verified V13 SD is unavailable.
            probs=None
        else:
            probs=calc_prob(p["margin"],p["total"],prior["margin_sd"],
                            prior["total_sd"],market,market_model,cutoff)
        p.update({"site_status":STATUS,"game_id":str(g["game_id"]),
                  "home":g["home_team"],"away":g["away_team"],
                  "kickoff_utc":g["kickoff_utc"],
                  "source_observed_utc":now,
                  "original_v04_forecast_observed_utc":board["forecast_observed_utc"],
                  "forecast_run_id":str(board["forecast_run_id"]),
                  "original_v04_score_unchanged":True,
                  "historical_source_publication_authenticated":False,
                  "historical_research_not_prospective_backtest":True,
                  "probabilities":probs,
                  "model_promoted":False,"safe_for_betting":False})
        g["v14_matchup_shadow"]=p;accepted+=1
    after=json.dumps([{
        "v04":g.get("v04_direct_scores"),
        "v13":g.get("v13_probability_shadow"),
        "margin":g.get("model_home_margin"),
        "total":g.get("model_total"),
        "ats":g.get("model_ats_side"),
        "ou":g.get("model_ou_side")}
        for g in board["games"]],sort_keys=True)
    if before!=after:raise ValueError("V14 attempted to overwrite published model")
    board["v14_matchup_display"]={
        "status":STATUS,"ready":accepted,"missing_source":missing,
        "already_kicked_off":started,"insufficient_training":gates,
        "original_v04_predictions_unchanged":True,
        "v13_probabilities_unchanged":True,
        "historical_first_publication_authenticated":False,
        "independent_prospective_improvement_proven":False,
        "model_promoted":False}
    return board


def run(dashboard,v13_archive,historical_advanced,historical_turnovers,
        current_advanced,current_turnovers,current_manifest,output=None,now=None):
    file=Path(dashboard)
    b=json.loads(file.read_text())
    instant=now or dt.datetime.now(dt.timezone.utc).isoformat()
    at=parse_time(instant)
    cutoff=at.astimezone(ET).date().isoformat()
    manifest=json.loads(Path(current_manifest).read_text())
    turnovers=json.loads(Path(current_turnovers).read_text())
    if (manifest.get("season")!=2026 or
        manifest.get("historical_pregame_availability_verified") is not False or
        parse_time(manifest["retrieved_at_utc"])>at or
        parse_time(turnovers["captured_at_utc"])>at):
        raise ValueError("Fresh V14 source was not observed by this forecast's cutoff")
    if manifest.get("asof_exclusive")!=cutoff:
        # An interrupted or old intake is NOT a reason to break the whole
        # existing V04/V13 website. Fail closed for optional V14 predictions.
        for g in b["games"]:g["v14_matchup_shadow"]=None
        b["v14_matchup_display"]={
            "status":"V14_PASS_STALE_ASOF_SOURCE_RESEARCH_ONLY",
            "ready":0,"model_promoted":False,
            "reason":"CURRENT_SOURCE_NOT_FROM_FORECAST_DATE",
            "original_v04_predictions_unchanged":True,
            "independent_prospective_improvement_proven":False}
        dest=Path(output or dashboard)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(b,indent=2,allow_nan=False)+"\n")
        print(json.dumps(b["v14_matchup_display"],sort_keys=True))
        return b
    original=json.loads(Path(v13_archive).read_text())
    fixed_turnover=json.loads(Path(historical_turnovers).read_text())
    with open(historical_advanced,newline="") as fh:
        frozen_source=load_inputs(list(csv.DictReader(fh)),fixed_turnover)
    with open(current_advanced,newline="") as fh:
        active_source=load_inputs(list(csv.DictReader(fh)),turnovers)
    history=_historical_training(original,frozen_source,cutoff)
    scores=fit_scores(history,cutoff)
    calibrator=fit_market(history,cutoff)
    current=profile(active_source,cutoff)
    result=attach(b,scores,calibrator,current,instant)
    dest=Path(output or dashboard)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result["v14_matchup_display"],sort_keys=True))
    return result

if __name__=="__main__":
    arg=argparse.ArgumentParser()
    for key in ("dashboard","v13-archive","historical-advanced",
                "historical-turnovers","current-advanced",
                "current-turnovers","current-manifest"):
        arg.add_argument("--"+key,required=True)
    arg.add_argument("--output")
    a=arg.parse_args()
    run(a.dashboard,a.v13_archive,a.historical_advanced,
        a.historical_turnovers,a.current_advanced,
        a.current_turnovers,a.current_manifest,a.output)

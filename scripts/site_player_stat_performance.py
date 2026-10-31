"""Read-only current PlayerForm forecast-versus-stat accuracy site overlay.

Player-stat MAE is conditional recorded-category accuracy, NOT sportsbook
player-prop returns. No past pregame predictions are regenerated. This layer
does not alter SU/ATS/totals results or the frozen V03 score model.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

from scripts.game_context import parse_time
from scripts.player_prop_prospective_stat_grade import STATUS as GRADE,LATEST

STATUS="SITE_VERIFIED_PROSPECTIVE_PLAYER_STAT_RESEARCH_PERFORMANCE"
UNAVAILABLE="NO_SETTLED_PLAYER_STAT_RESEARCH_GRADE_YET"
METRICS=("passing_yards","rushing_yards","receiving_yards")

def _num(x):
    return type(x) in (int,float) and math.isfinite(x)

def overlay(board,summary=None,now=None):
    instant=parse_time(now or dt.datetime.now(dt.timezone.utc).isoformat())
    if board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Invalid original score board")
    originals=[(g["game_id"],g["model_home_margin"],g["model_total"],
                g["model_home_points"],g["model_away_points"])
               for g in board.get("games",[])]
    if summary is None:
        board["player_stat_performance"]={
            "status":UNAVAILABLE,"graded_recorded_player_stat_samples":0,
            "source_forecasts_archived":None,"metrics":{},
            "player_stat_accuracy_not_market_betting_prop_accuracy":True}
    else:
        if (summary.get("status")!=GRADE or summary.get("season")!=2026 or
            summary.get("betting_status")!="PASS_UNVALIDATED" or
            summary.get("model_promoted") is not False or
            summary.get("safe_for_betting") is not False or
            summary.get("no_bookmaker_prop_lines_or_return_calculated") is not True or
            summary.get("first_valid_pregame_snapshot_only") is not True or
            summary.get("missing_player_or_category_is_not_zero_or_assumed_dnp") is not True or
            parse_time(summary["graded_at_utc"])>instant):
            raise ValueError("Source-invalid prospective player-stat grade")
        metrics={}
        total=0
        for metric in METRICS:
            x=summary.get("metrics",{}).get(metric)
            if not isinstance(x,dict):raise ValueError("Missing stat performance metric")
            n=x.get("graded_recorded_player_games")
            if type(n) is not int or n<0:raise ValueError("Invalid grade cohort")
            total+=n
            mae=x.get("playerform_conditional_mae")
            bias=x.get("playerform_mean_signed_error")
            if (n>0 and (not _num(mae) or not _num(bias) or mae<0)) or (
                n==0 and (mae is not None or bias is not None)):
                raise ValueError("Invalid or invented player performance accuracy")
            paired=x.get("paired_with_frozen_recent_four_baseline",0)
            if type(paired) is not int or not 0<=paired<=n:
                raise ValueError("Invalid same-cohort baseline comparison count")
            compared=x.get("paired_mae_improvement")
            if paired>0 and not _num(compared) or paired==0 and compared is not None:
                raise ValueError("Unsupported paired research benchmark grade")
            metrics[metric]={
                "graded_recorded_player_games":n,
                "playerform_conditional_mae":mae,
                "mean_signed_error":bias,
                "paired_recency_control_samples":paired,
                "paired_mae_improvement":compared,
            }
        if total!=summary.get("graded_recorded_player_stat_samples"):
            raise ValueError("Player stat grade total does not reconcile")
        archive=summary.get("archive_verification",{})
        if (archive.get("archive_status") not in
            ("VALID_PREKICKOFF_PLAYER_STAT_ARCHIVES","NO_ARCHIVE_INDEX_YET") or
            type(archive.get("archived_forecasts_across_runs")) is not int):
            raise ValueError("Unverified player prediction archive")
        board["player_stat_performance"]={
            "status":STATUS,
            "graded_at_utc":summary["graded_at_utc"],
            "source_forecasts_archived":archive["archived_forecasts_across_runs"],
            "eligible_unique_pre_kickoff_player_forecasts":
                summary["eligible_unique_pre_kickoff_player_forecasts"],
            "graded_recorded_player_stat_samples":total,
            "player_category_coverage_rate":summary.get("player_category_coverage_rate"),
            "metrics":metrics,
            "missing_or_unsettled":summary.get("missing_or_unsettled",{}),
            "player_stat_accuracy_not_market_betting_prop_accuracy":True,
            "no_auto_promotion":True,
        }
    after=[(g["game_id"],g["model_home_margin"],g["model_total"],
           g["model_home_points"],g["model_away_points"]) for g in board["games"]]
    if originals!=after:
        raise ValueError("Player performance cannot rewrite frozen V03 score forecast")
    return board

def run(dashboard,root):
    file=Path(dashboard)
    board=json.loads(file.read_text(encoding="utf-8"))
    candidate=Path(root)/LATEST
    summary=json.loads(candidate.read_text(encoding="utf-8")) if candidate.is_file() else None
    result=overlay(board,summary)
    file.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(result["player_stat_performance"]))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dashboard",required=True)
    p.add_argument("--archive-root",required=True)
    a=p.parse_args();run(a.dashboard,a.archive_root)

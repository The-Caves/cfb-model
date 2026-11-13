"""Prospective-only grading for V13's first actually published probability receipt.

Reads immutable context-state captured website snapshots and independently
finalized scores. Never rebuilds a retrospective V13 forecast or changes V04,
V03, V05, V09, market decisions, settled performance or model version.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from scripts.game_context import parse_time
from scripts.site_history import (
    ARCHIVE_STATUS,FINAL_STATUS,INDEX,FINALS,_load,_digest)
from scripts.v13_v04_probabilities import crps

STATUS="V13_FIRST_SOURCE_FROZEN_PREGAME_PROBABILITY_PERFORMANCE"


def summarize(root,now=None):
    root=Path(root)
    at=parse_time(now or dt.datetime.now(dt.timezone.utc).isoformat())
    index=json.loads((root/INDEX).read_text())
    finals=json.loads((root/FINALS).read_text())
    if (index.get("status")!=ARCHIVE_STATUS or index.get("schema_version")!=1 or
        not isinstance(index.get("runs"),list) or
        finals.get("status")!=FINAL_STATUS or finals.get("season")!=2026 or
        finals.get("safe_for_betting") is not False or
        not isinstance(finals.get("games"),dict)):
        raise ValueError("Cannot grade V13 without immutable original source receipt and finals")
    first={}
    for receipt in sorted(index["runs"],key=lambda r:r["capture_utc"]):
        cap=parse_time(receipt["capture_utc"])
        if cap>at:continue
        snap=_load(root,receipt["path"])
        if (_digest(snap)!=receipt["sha256"] or
            snap.get("status")!=ARCHIVE_STATUS or
            snap.get("capture_utc")!=receipt["capture_utc"] or
            str(snap.get("dashboard_run_id"))!=str(receipt["run_id"])):
            raise ValueError("V13 archive receipt cannot be authenticated")
        for row in snap.get("rows",[]):
            p=row.get("v13_frozen_probability_shadow")
            gid=str(row.get("game_id",""))
            if not p or not gid or gid in first:continue
            kickoff=parse_time(row["kickoff_utc"])
            if (cap>=kickoff or
                parse_time(row["frozen_forecast_observed_utc"])>=kickoff or
                parse_time(p["generated_at_utc"])>cap or
                parse_time(p["generated_at_utc"])>=kickoff):
                raise ValueError("Post-kickoff or future V13 model receipt")
            if (p.get("site_status")!="V13_SOURCE_TIMED_V04_PROBABILITY_SHADOW" or
                p.get("v04_mean_scores_unchanged") is not True or
                p.get("model_promoted") is not False or
                p.get("safe_for_betting") is not False or
                str(p.get("game_id"))!=gid or
                p.get("home")!=row["home"] or
                p.get("away")!=row["away"]):
                raise ValueError("Malformed V13 probability source identity")
            first[gid]={"row":row,"prediction":p,"cap":cap}
    eligible=[];unsettled=0
    for gid,receipt in sorted(first.items()):
        row=receipt["row"];p=receipt["prediction"];cap=receipt["cap"]
        result=finals["games"].get(gid)
        if not result:
            unsettled+=1;continue
        try:
            actual_kick=parse_time(result["kickoff_utc"])
            kickoff=parse_time(row["kickoff_utc"])
            known=parse_time(result["outcome_known_at_utc"])
            if (str(result["game_id"])!=gid or
                result["home"]!=row["home"] or result["away"]!=row["away"] or
                abs((kickoff-actual_kick).total_seconds())>900 or
                not kickoff<known<=at or
                any(type(result.get(k)) is not int or not 0<=result[k]<=200
                    for k in ("home_score","away_score"))):
                unsettled+=1;continue
        except (KeyError,TypeError,ValueError):
            unsettled+=1;continue
        margin=result["home_score"]-result["away_score"]
        total=result["home_score"]+result["away_score"]
        eligible.append({"game_id":gid,"home":row["home"],"away":row["away"],
            "kickoff_utc":row["kickoff_utc"],"first_prediction_observed_utc":cap.isoformat(),
            "result_known_utc":result["outcome_known_at_utc"],
            "margin_error":margin-p["margin_mean"],
            "total_error":total-p["total_mean"],
            "margin_crps":crps(margin,p["margin_mean"],p["margin_sd"]),
            "total_crps":crps(total,p["total_mean"],p["total_sd"]),
            "margin_80pct_hit":int(p["margin_p10"]<=margin<=p["margin_p90"]),
            "total_80pct_hit":int(p["total_p10"]<=total<=p["total_p90"]),
            "winner_correct":int((margin>0)==(p["margin_mean"]>0)) if margin else None,
            "winner_brier":(p["home_win_probability"]-int(margin>0))**2 if margin else None,
            "home_cover_brier":(
                (p["home_cover_probability"]-int(margin+row["market_home_spread"]>0))**2
                if p["home_cover_probability"] is not None and
                   row["market_home_spread"] is not None and
                   margin+row["market_home_spread"]!=0 else None),
            "over_brier":(
                (p["over_probability"]-int(total>row["market_total"]))**2
                if p["over_probability"] is not None and
                   row["market_total"] is not None and
                   total!=row["market_total"] else None)})
    def average(key):
        values=[row[key] for row in eligible if row[key] is not None]
        return round(sum(values)/len(values),6) if values else None
    def absolute(key):
        values=[abs(row[key]) for row in eligible]
        return round(sum(values)/len(values),5) if values else None
    return {"status":STATUS,"evaluated_at_utc":at.isoformat(),
        "version":"V13_V04_ANCHORED_PROBABILITIES_RESEARCH_ONLY",
        "first_frozen_pregame_v13_games":len(first),
        "settled_v13_games":len(eligible),
        "unsettled_v13_games":unsettled,
        "scoring":{"margin_mae":absolute("margin_error"),
                   "total_mae":absolute("total_error"),
                   "margin_crps":average("margin_crps"),
                   "total_crps":average("total_crps"),
                   "margin_80pct_coverage":average("margin_80pct_hit"),
                   "total_80pct_coverage":average("total_80pct_hit"),
                   "winner_correct":sum(g["winner_correct"] or 0 for g in eligible),
                   "winner_eligible":sum(g["winner_correct"] is not None for g in eligible),
                   "winner_brier":average("winner_brier"),
                   "home_cover_brier":average("home_cover_brier"),
                   "over_brier":average("over_brier"),
                   "home_cover_evaluable":sum(g["home_cover_brier"] is not None for g in eligible),
                   "total_over_evaluable":sum(g["over_brier"] is not None for g in eligible)},
        "model_promoted":False,
        "original_v04_predictions_unchanged":True,
        "retrospective_predictions_created":False,
        "independent_validation_sufficient":False,
        "safe_for_betting":False,
        "games":eligible}


def run(archive_root,dashboard,now=None):
    path=Path(dashboard);board=json.loads(path.read_text())
    if board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Invalid original site")
    original=json.dumps([g.get("v04_direct_scores") for g in board["games"]],sort_keys=True)
    grades=json.dumps(board.get("prospective_records"),sort_keys=True)
    result=summarize(archive_root,now)
    board["v13_prospective_performance"]=result
    if (json.dumps([g.get("v04_direct_scores") for g in board["games"]],sort_keys=True)!=original or
        json.dumps(board.get("prospective_records"),sort_keys=True)!=grades):
        raise ValueError("V13 grade changed older frozen models")
    path.write_text(json.dumps(board,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:result[k] for k in
                      ("status","first_frozen_pregame_v13_games","settled_v13_games",
                       "unsettled_v13_games","scoring")},sort_keys=True))
    return board

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--archive-root",required=True)
    parser.add_argument("--dashboard",required=True)
    opts=parser.parse_args()
    run(opts.archive_root,opts.dashboard)

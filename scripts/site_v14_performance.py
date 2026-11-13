"""Grade first immutable pre-kickoff V14 matchup-score shadow vs frozen V04.

No backfilled V14 forecasts. Original V04/V13 and sportsbook lines are read
only. Independent verified finals are attached after kickoff. Retrospective
2026 377-game research is NEVER added to prospective performance counters.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from scripts.game_context import parse_time
from scripts.site_history import (
    ARCHIVE_STATUS,FINAL_STATUS,INDEX,FINALS,_load,_digest)

STATUS="V14_FIRST_FROZEN_PREGAME_MATCHUP_CHALLENGER_GRADE"


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
        raise ValueError("V14 missing immutable source-linked website archive")
    earliest={}
    for receipt in sorted(index["runs"],key=lambda r:r["capture_utc"]):
        captured=parse_time(receipt["capture_utc"])
        if captured>at:continue
        snap=_load(root,receipt["path"])
        if (_digest(snap)!=receipt["sha256"] or
            snap.get("status")!=ARCHIVE_STATUS or
            snap.get("capture_utc")!=receipt["capture_utc"] or
            str(snap.get("dashboard_run_id"))!=str(receipt["run_id"])):
            raise ValueError("V14 original website snapshot was modified")
        for row in snap.get("rows",[]):
            p=row.get("v14_frozen_matchup_shadow")
            gid=str(row.get("game_id",""))
            if p is None or not gid or gid in earliest:continue
            kick=parse_time(row["kickoff_utc"])
            if (captured>=kick or
                parse_time(p["source_observed_utc"])>=kick or
                parse_time(p["source_observed_utc"])>captured or
                p.get("site_status")!="V14_SOURCE_TIMED_OPPONENT_MATCHUP_SCORE_SHADOW" or
                p.get("model_promoted") is not False or
                p.get("original_v04_score_unchanged") is not True or
                p.get("safe_for_betting") is not False or
                str(p.get("game_id"))!=gid or
                p.get("home")!=row["home"] or
                p.get("away")!=row["away"]):
                raise ValueError("Untrusted V14 first pregame score snapshot")
            earliest[gid]=(row,p,captured)
    graded=[];waiting=0
    for gid,(row,p,captured) in sorted(earliest.items()):
        result=finals["games"].get(gid)
        if result is None:
            waiting+=1;continue
        try:
            kick=parse_time(row["kickoff_utc"])
            source_kick=parse_time(result["kickoff_utc"])
            published=parse_time(result["outcome_known_at_utc"])
            if (str(result["game_id"])!=gid or
                result["home"]!=row["home"] or result["away"]!=row["away"] or
                abs((kick-source_kick).total_seconds())>900 or
                not kick<published<=at or
                any(type(result.get(k)) is not int or not 0<=result[k]<=200
                    for k in ("home_score","away_score"))):
                waiting+=1;continue
        except (KeyError,TypeError,ValueError):
            waiting+=1;continue
        actual_m=result["home_score"]-result["away_score"]
        actual_t=result["home_score"]+result["away_score"]
        pred_m=p["margin"];pred_t=p["total"]
        base_m=row["v04_direct_home_margin"]
        base_t=row["v04_direct_total_points"]
        if base_m is None or base_t is None:
            raise ValueError("V14 challenger has no original V04 paired score")
        market_spread=row.get("market_home_spread")
        market_total=row.get("market_total")
        probs=p.get("probabilities") or {}
        graded.append({
            "game_id":gid,"home":row["home"],"away":row["away"],
            "kickoff_utc":row["kickoff_utc"],
            "first_v14_captured_utc":captured.isoformat(),
            "result_known_at_utc":result["outcome_known_at_utc"],
            "v04_margin_error":abs(base_m-actual_m),
            "v14_margin_error":abs(pred_m-actual_m),
            "v04_total_error":abs(base_t-actual_t),
            "v14_total_error":abs(pred_t-actual_t),
            "v04_winner_correct":int((base_m>0)==(actual_m>0)) if actual_m else None,
            "v14_winner_correct":int((pred_m>0)==(actual_m>0)) if actual_m else None,
            "v04_ats_correct":(
                int((base_m+market_spread>0)==(actual_m+market_spread>0))
                if market_spread is not None and actual_m+market_spread!=0 else None),
            "v14_ats_correct":(
                int((pred_m+market_spread>0)==(actual_m+market_spread>0))
                if market_spread is not None and actual_m+market_spread!=0 else None),
            "v04_over_correct":(
                int((base_t>market_total)==(actual_t>market_total))
                if market_total is not None and actual_t!=market_total else None),
            "v14_over_correct":(
                int((pred_t>market_total)==(actual_t>market_total))
                if market_total is not None and actual_t!=market_total else None),
            "v14_winner_brier":(
                (probs["home_win"]-int(actual_m>0))**2
                if actual_m and probs.get("home_win") is not None else None),
            "v14_ats_brier":(
                (probs["home_cover_calibrated"]-int(actual_m+market_spread>0))**2
                if market_spread is not None and actual_m+market_spread!=0
                   and probs.get("home_cover_calibrated") is not None else None),
            "v14_over_brier":(
                (probs["over_calibrated"]-int(actual_t>market_total))**2
                if market_total is not None and actual_t!=market_total
                   and probs.get("over_calibrated") is not None else None)
        })
    def means(keys):
        result={}
        for key in keys:
            nums=[r[key] for r in graded if r[key] is not None]
            result[key]={"n":len(nums),"value":round(sum(nums)/len(nums),6) if nums else None}
        return result
    return {"status":STATUS,"evaluated_at_utc":at.isoformat(),
            "first_frozen_v14_games":len(earliest),"settled_v14_games":len(graded),
            "unsettled_v14_games":waiting,
            "paired":means(("v04_margin_error","v14_margin_error",
                            "v04_total_error","v14_total_error",
                            "v04_winner_correct","v14_winner_correct",
                            "v04_ats_correct","v14_ats_correct",
                            "v04_over_correct","v14_over_correct",
                            "v14_winner_brier","v14_ats_brier","v14_over_brier")),
            "games":graded,"model_promoted":False,
            "first_source_frozen_predictions_only":True,
            "retrospective_2026_backtest_not_included":True,
            "independent_validation_sufficient":False,
            "safe_for_betting":False}


def run(archive_root,dashboard,now=None):
    file=Path(dashboard)
    b=json.loads(file.read_text())
    if b.get("schema_version")!=2 or b.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("V14 invalid website board")
    originals=json.dumps([(g.get("v04_direct_scores"),
        g.get("v13_probability_shadow"),g.get("model_ats_side"),g.get("model_ou_side"))
        for g in b["games"]],sort_keys=True)
    previous=json.dumps(b.get("prospective_records"),sort_keys=True)
    r=summarize(archive_root,now)
    b["v14_prospective_performance"]=r
    if (originals!=json.dumps([(g.get("v04_direct_scores"),
        g.get("v13_probability_shadow"),g.get("model_ats_side"),g.get("model_ou_side"))
        for g in b["games"]],sort_keys=True) or
        previous!=json.dumps(b.get("prospective_records"),sort_keys=True)):
        raise ValueError("V14 grade changed original immutable performance")
    file.write_text(json.dumps(b,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:r[k] for k in (
        "status","first_frozen_v14_games","settled_v14_games",
        "unsettled_v14_games","paired")},sort_keys=True))
    return b


if __name__=="__main__":
    arg=argparse.ArgumentParser()
    arg.add_argument("--archive-root",required=True)
    arg.add_argument("--dashboard",required=True)
    a=arg.parse_args()
    run(a.archive_root,a.dashboard)

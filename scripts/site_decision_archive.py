"""Immutable, time-signed snapshots of exactly displayed model picks and market lines.

Site observations are not the same as synchronized forecast/market decision
snapshots. They can be graded prospectively but must NEVER be treated as
prices observed when the older frozen model originally ran.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
from scripts import context_archive as store
from scripts.game_context import parse_time
from scripts.personnel_results_archive import _commit_material

ROOT="research_2026/site_board_snapshots"
INDEX=ROOT+"/index.json"
STATUS="IMMUTABLE_DISPLAYED_RESEARCH_MARKET_SNAPSHOT"
VALID_SIDES={"HOME","AWAY","PASS"}
VALID_TOTALS={"OVER","UNDER","PASS"}

def finite(x):
    return type(x) in (int,float) and math.isfinite(x)

def freeze(board,now,run_id):
    if (board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED"
        or not isinstance(board.get("games"),list) or
        not isinstance(board.get("forecast_sha256"),str)
        or len(board["forecast_sha256"])!=64
        or not isinstance(board.get("model"),str) or not board["model"].strip()
        or not str(run_id).isdigit()):
        raise ValueError("Invalid published research snapshot/identity")
    orig=parse_time(board["forecast_observed_utc"])
    if orig>now:raise ValueError("Forecast from future")
    # External odds timestamps are preserved separately from model timestamps.
    rows=[];ids=set();quote_count=0;ats=0;ou=0;high_disagreement=0
    for g in board["games"]:
        gid=str(g["game_id"])
        kickoff=parse_time(g["kickoff_utc"])
        if gid in ids:raise ValueError("Duplicate game ID")
        ids.add(gid)
        if kickoff<=now:continue  # never create a post-kickoff prospectively graded pick
        if orig>=kickoff:raise ValueError("Prediction after scheduled kickoff")
        home=g["home_team"];away=g["away_team"]
        margin=g["model_home_margin"];total=g["model_total"]
        if (not home or not away or not finite(margin) or not finite(total)
                or margin<=-150 or margin>=150 or not 0<=total<=160):
            raise ValueError("Invalid frozen model output")
        spread=g.get("market_home_spread")
        market_total=g.get("market_total")
        sp=spread is not None
        tt=market_total is not None
        if sp and (not finite(spread) or abs(spread)>=80):raise ValueError("Bad home spread")
        if tt and (not finite(market_total) or market_total<=0 or market_total>=150):
            raise ValueError("Bad market total")
        provider=g.get("market_provider")
        market_observed=g.get("market_observed_utc")
        if sp or tt:
            if not provider or not market_observed:
                raise ValueError("Unsourced displayed odds")
            observed=parse_time(market_observed)
            if observed>now or observed>=kickoff:
                raise ValueError("Market line collected in future or after kickoff")
            quote_count+=1
        elif provider or market_observed:
            raise ValueError("Provider/clock without a displayed market line")
        side=g.get("model_ats_side")
        over=g.get("model_ou_side")
        if side is not None:
            expected=("PASS" if g.get("home_bias_quarantined") is True else
                      "HOME" if margin+spread>0 else
                      "AWAY" if margin+spread<0 else "PASS")
            if not sp or side not in VALID_SIDES or side!=expected:
                raise ValueError("Displayed ATS selection changed or no source")
            if side!="PASS":ats+=1
        elif sp:
            raise ValueError("Observed ATS line without computed side")
        if over is not None:
            expected="OVER" if total>market_total else "UNDER" if total<market_total else "PASS"
            if not tt or over not in VALID_TOTALS or over!=expected:
                raise ValueError("Displayed totals selection changed or no source")
            if over!="PASS":ou+=1
        elif tt:
            raise ValueError("Observed total without computed side")
        # Freeze the ACTUALLY DISPLAYED independent V04 research score
        # alongside (never replacing) the original V03 forecast receipts.
        candidate=g.get("v04_direct_scores")
        if candidate is not None:
            if (not isinstance(candidate,dict) or
                candidate.get("status")!="SOURCE_OBSERVED_DIRECT_TEAM_SCORE_MODEL_RESEARCH_ONLY"
                or candidate.get("model")!="V04_INDEPENDENT_OPPONENT_ADJUSTED_SCORES_RESEARCH_ONLY"
                or candidate.get("direct_scoring_fit_uses_v03_total") is not False
                or candidate.get("no_market_lines_in_training") is not True
                or candidate.get("model_promoted") is not False or
                g.get("home_bias_quarantined") is not True):
                raise ValueError("V04 research source/status mismatch")
            home_pts=candidate.get("home_points")
            away_pts=candidate.get("away_points")
            pred_margin=candidate.get("home_margin")
            pred_total=candidate.get("total_points")
            if (not all(finite(v) for v in (home_pts,away_pts,pred_margin,pred_total))
                or min(home_pts,away_pts,pred_total)<0 or
                abs(home_pts+away_pts-pred_total)>.03 or
                abs(home_pts-away_pts-pred_margin)>.03):
                raise ValueError("V04 model score incoherent or unsupported")
        else:
            home_pts=away_pts=pred_margin=pred_total=None
        discrepancy=round(abs(margin+spread),4) if sp else None
        risk="HIGH_MODEL_MARKET_DISAGREEMENT" if discrepancy is not None and discrepancy>=10 else "NONE"
        high_disagreement+=int(risk!="NONE")
        rows.append({
            "model_market_margin_disagreement":discrepancy,
            "calibration_review_flag":risk,
            "game_id":gid,"home":home,"away":away,"kickoff_utc":g["kickoff_utc"],
            "frozen_forecast_home_margin":margin,"frozen_forecast_total":total,
            "frozen_forecast_run_id":str(board["forecast_run_id"]),
            "forecast_model_version":board["model"],
            "frozen_forecast_observed_utc":board["forecast_observed_utc"],
            "frozen_forecast_sha256":board["forecast_sha256"],
            "market_home_spread":spread,"market_total":market_total,
            "market_provider":provider,"market_observed_utc":market_observed,
            "displayed_ats_side":side,"displayed_ou_side":over,
            "home_bias_quarantined":g.get("home_bias_quarantined") is True,
            "opponent_rating_shadow_model":(
                g["opponent_rating"]["model"] if isinstance(g.get("opponent_rating"),dict)
                else None),
            "opponent_rating_shadow_margin":(
                g["opponent_rating"]["predicted_home_margin"]
                if isinstance(g.get("opponent_rating"),dict) else None),
            "v04_direct_score_model":candidate.get("model") if candidate else None,
            "v04_direct_home_points":home_pts,
            "v04_direct_away_points":away_pts,
            "v04_direct_home_margin":pred_margin,
            "v04_direct_total_points":pred_total,
            "v04_direct_source_no_v03_total_reuse":(
                candidate["direct_scoring_fit_uses_v03_total"] is False
                if candidate else None),
            "v04_research_not_promoted":candidate.get("model_promoted") is False
                if candidate else None,
            "qb_verified_at_forecast":g.get("qb_starters_verified",0),
        })
    if not rows:raise ValueError("No unstarted games to archive")
    rows.sort(key=lambda g:(g["kickoff_utc"],g["game_id"]))
    return {"status":STATUS,"schema_version":1,"betting_status":"PASS_UNVALIDATED",
            "capture_utc":now.isoformat(),"dashboard_run_id":str(run_id),
            "model_forecast_sha256":board["forecast_sha256"],
            "model_version":board["model"],
            "model_forecast_observed_utc":board["forecast_observed_utc"],
            "comparison_timing":"MARKET_MAY_HAVE_BEEN_OBSERVED_AFTER_FROZEN_MODEL_FORECAST",
            "market_publication_time_authenticated":False,
            "not_an_executed_bet":True,"eligible_for_future_verified_outcome_grading":True,
            "summary":{"future_games":len(rows),"games_with_line":quote_count,
                       "ats_decisions":ats,"total_decisions":ou,
                       "model_market_high_disagreements":high_disagreement},
            "rows":rows}

def archive(snapshot):
    if snapshot["status"]!=STATUS:raise ValueError("Invalid snapshot")
    run=str(snapshot["dashboard_run_id"])
    path=ROOT+"/"+parse_time(snapshot["capture_utc"]).strftime("%Y/%m/%d")+"/run-"+run+".json.gz"
    blob=store.pack(snapshot)
    old=store.get_blob_file(path)
    if old is not None:
        if old!=blob:raise ValueError("Different decisions for a preexisting run; refusing rewrite")
        return {"status":"ALREADY_ARCHIVED","path":path,"summary":snapshot["summary"]}
    saved=store.get_blob_file(INDEX)
    index=json.loads(saved) if saved else {"status":STATUS,"schema_version":1,"runs":[]}
    if (index.get("status")!=STATUS or index.get("schema_version")!=1
        or not isinstance(index.get("runs"),list)
        or any(x["run_id"]==run for x in index["runs"])):
        raise ValueError("Duplicate or corrupted model decision index")
    index["runs"].append({"run_id":run,"path":path,
                         "sha256":hashlib.sha256(store.encode(snapshot)).hexdigest(),
                         "capture_utc":snapshot["capture_utc"],
                         **snapshot["summary"]})
    _commit_material({path:blob,INDEX:store.encode(index)},run)
    return {"status":"ARCHIVED","path":path,"summary":snapshot["summary"]}

def run(input_file,now=None,run_id=None,persist=True):
    now=now or dt.datetime.now(dt.timezone.utc)
    run_id=run_id or os.environ.get("GITHUB_RUN_ID","")
    board=json.loads(Path(input_file).read_text(encoding="utf-8"))
    frozen=freeze(board,now,run_id)
    if not persist:return frozen
    return archive(frozen)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dashboard",required=True)
    a=p.parse_args()
    print(json.dumps(run(a.dashboard),sort_keys=True))

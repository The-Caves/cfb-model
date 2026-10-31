"""Game-day frozen V03 home-bias circuit breaker + independent opponent rating.

Scores in existing model_home_margin/model_total remain EXACTLY the archived
V03 values and are never silently revised. A diagnostic QA gate suppresses
new displayed V03 spread choices when severe bias is verified. When the
source archive from THAT same original forecast run is available, a
score-only opponent-strength R1 challenger is displayed SEPARATELY.

R1 is a plain ridge/Massey-style opponent adjustment: solve observed team
ratings from completed game differences, subtract a conservative fixed
2.5-point non-neutral home allowance, clip game margins at +/-28, and
shrink team skill estimates with 1.0 L2 penalty. No sportsbook odds
are used to fit or tune the candidate. Its retrospective evaluation is
NOT independently prospectively validated and its output is not a bet.
"""
import argparse
import csv
import hashlib
import datetime as dt
import json
import math
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from scripts.game_context import parse_time
from scripts.personnel_forecast import checksum

ET=ZoneInfo("America/New_York")
STATUS="V03_HOME_BIAS_CIRCUIT_BREAKER_AND_OPPONENT_RATING_SHADOW"
MODEL="OPPONENT_ADJUSTED_SCORE_MARGIN_R1_RESEARCH_ONLY"
HOME_ALLOWANCE=2.5
MARGIN_CAP=28.
PENALTY=1.
MIN_TRAINING_GAMES=90
MIN_FLAG_SAMPLE=15
FLAG_FRACTION=.85
FLAG_MARGIN=7.

def _is_number(x):
    return type(x) in (int,float) and math.isfinite(x)

def _margin(a,b):
    if not _is_number(a) or not _is_number(b):
        raise ValueError("Nonfinite football score")
    return a-b

def _source_games(rows,forecast):
    seen=set();accepted=[]
    for row in rows:
        gid=str(row["game_id"])
        if gid in seen:raise ValueError("Duplicated source game identity")
        seen.add(gid)
        home=row["home"];away=row["away"]
        if not home or not away or home==away:
            raise ValueError("Invalid completed football opponents")
        kickoff=parse_time(row["kickoff_utc"])
        # A completed game cannot be used from the same Eastern football
        # calendar day, even if its UTC kickoff happened to be earlier.
        if (kickoff>=forecast or
            dt.date.fromisoformat(row["date"])>=forecast.astimezone(ET).date()):
            raise ValueError("Training input is not strictly before forecast football day")
        neutral=row["neutral"]
        if neutral not in ("True","False"):
            raise ValueError("Neutral-site indicator must be source-confirmed")
        h=float(row["home_score"]);a=float(row["away_score"])
        if not all(x.is_integer() and 0<=x<=200 for x in (h,a)):
            raise ValueError("Invalid final score")
        accepted.append((home,away,h-a,neutral=="True"))
    if len(accepted)<MIN_TRAINING_GAMES:
        raise ValueError("Too few real completed games for rating model")
    return accepted

def ratings(completed):
    names=sorted({n for h,a,_,_ in completed for n in (h,a)})
    lookup={n:i for i,n in enumerate(names)}
    x=np.zeros((len(completed),len(names)),dtype=float)
    y=np.empty(len(completed),dtype=float)
    for i,(home,away,margin,neutral) in enumerate(completed):
        x[i,lookup[home]]=1.
        x[i,lookup[away]]=-1.
        y[i]=float(np.clip(margin,-MARGIN_CAP,MARGIN_CAP))-(0 if neutral else HOME_ALLOWANCE)
    coeff=np.linalg.solve(x.T@x+PENALTY*np.eye(len(names)),x.T@y)
    if not np.isfinite(coeff).all():raise ValueError("Rating solution is nonfinite")
    return {n:float(coeff[i]) for n,i in lookup.items()}

def _bias(board):
    observed=parse_time(board["generated_at_utc"])
    local=observed.astimezone(ET).date()
    today=[g for g in board["games"] if
           parse_time(g["kickoff_utc"]).astimezone(ET).date()==local and
           parse_time(g["kickoff_utc"])>observed and
           _is_number(g.get("model_home_margin"))]
    home=sum(g["model_home_margin"]>0 for g in today)
    fraction=home/len(today) if today else None
    mean=sum(g["model_home_margin"] for g in today)/len(today) if today else None
    fail=(len(today)>=MIN_FLAG_SAMPLE and fraction>=FLAG_FRACTION
          and mean>=FLAG_MARGIN)
    return fail,{"local_date":local.isoformat(),"future_games":len(today),
        "home_picks":home,"home_pick_fraction":round(fraction,5) if fraction is not None else None,
        "mean_home_margin":round(mean,5) if mean is not None else None,
        "home_bias_threshold":{"min_games":MIN_FLAG_SAMPLE,
           "home_selection_fraction":FLAG_FRACTION,"mean_margin_points":FLAG_MARGIN}}

def apply(board,source_rows=None,manifest=None,context=None):
    if (board.get("schema_version")!=2 or
        board.get("betting_status")!="PASS_UNVALIDATED" or
        not isinstance(board.get("games"),list) or
        board.get("model")!="V03_RIDGE_OBSERVED_PROSPECTIVE_BASE14_V1"):
        raise ValueError("Expected original frozen V03 source board")
    forecast=parse_time(board["forecast_observed_utc"])
    seen=set()
    frozen=[(g["game_id"],g["model_home_margin"],g["model_home_points"],
             g["model_away_points"],g["model_total"],g["research_home_win_probability"])
            for g in board["games"]]
    for g in board["games"]:
        if str(g["game_id"]) in seen:raise ValueError("Duplicate website matchup")
        seen.add(str(g["game_id"]))
    fail,audit=_bias(board)
    # No authenticated same-run evidence means the already-discredited
    # V03 must remain quarantined, regardless of today's shrinking count.
    if source_rows is None:
        fail=True
    quality=("V03_HOME_BIAS_SOURCE_MISSING_FAIL_CLOSED"
             if source_rows is None else
             "V03_HOME_BIAS_QUARANTINED" if fail else "V03_HOME_BIAS_NOT_FLAGGED")
    scores={}
    training_home_margin=None
    training_games=0
    if source_rows is not None or manifest is not None or context is not None:
        if not(isinstance(source_rows,list) and isinstance(manifest,dict)
               and isinstance(context,dict)):
            raise ValueError("Incomplete independent football score evidence")
        if (manifest.get("status")!="SUCCESS" or manifest.get("failures") or
            manifest.get("requested_start")!="2026-08-01" or
            manifest.get("scoreboard_date_timezone")!="America/New_York" or
            parse_time(manifest["retrieved_at_utc"])>forecast or
            parse_time(context["captured_at_utc"])>forecast):
            raise ValueError("Wrong, late or unverified historical score snapshot")
        candidates={}
        for r in context.get("games",[]):
            gid=str(r["game_id"])
            if gid in candidates:raise ValueError("Duplicate context game")
            candidates[gid]=r
        train=_source_games(source_rows,forecast)
        training_home_margin=round(sum(r[2] for r in train)/len(train),5)
        training_games=len(train)
        # Whole-season 2026 schedule imbalance is independently diagnostic.
        # Keep V03 in quarantine even after noon games kick off and the
        # dashboard's remaining "today" sample becomes small.
        fail=fail or (len(train)>=90 and training_home_margin>=8.)
        quality="V03_HOME_BIAS_QUARANTINED" if fail else "V03_HOME_BIAS_NOT_FLAGGED"
        strength=ratings(train)
        for g in board["games"]:
            ctx=candidates.get(str(g["game_id"]))
            if ctx is None:continue
            if (g["home_team"]!=ctx["home"] or g["away_team"]!=ctx["away"] or
                parse_time(g["kickoff_utc"])!=parse_time(ctx["kickoff_utc"]) or
                type(ctx.get("neutral")) is not bool):
                raise ValueError("Candidate matchup differs from source fixture")
            home,away=g["home_team"],g["away_team"]
            if home not in strength or away not in strength:continue
            m=strength[home]-strength[away]+(0 if ctx["neutral"] else HOME_ALLOWANCE)
            # The independent R1 candidate currently predicts a margin,
            # not possession-level points or a total. For the one-glance
            # site, derive an explicitly HYBRID score illustration using
            # the separately archived, unvalidated V03 total. Never
            # relabel the resulting points as trained R1 score outputs.
            original_total=g.get("model_total")
            illustrative=(original_total is not None and
                          _is_number(original_total) and 0<=original_total<=160 and
                          math.isfinite(m) and abs(m)<=original_total)
            scenario_home=round((original_total+m)/2,2) if illustrative else None
            scenario_away=round((original_total-m)/2,2) if illustrative else None
            scores[str(g["game_id"])]={
                "status":"SOURCE_MATCHED_OPPONENT_RATING_R1_RESEARCH_ONLY",
                "score_scenario_status":("HYBRID_R1_MARGIN_WITH_FROZEN_V03_TOTAL_UNVALIDATED"
                    if illustrative else "NO_VALID_SCORE_SPLIT"),
                "scenario_home_points":scenario_home,
                "scenario_away_points":scenario_away,
                "scenario_total_points":original_total if illustrative else None,
                "scenario_total_source":"FROZEN_UNVALIDATED_V03_TOTAL" if illustrative else None,
                "score_scenario_is_jointly_trained_or_calibrated":False,
                "original_v03_scores_and_margin_unchanged":True,
                "model":MODEL,"predicted_home_margin":round(m,5),
                "home_team_rating":round(strength[home],5),
                "away_team_rating":round(strength[away],5),
                "home_field_allowance":0. if ctx["neutral"] else HOME_ALLOWANCE,
                "source_training_games":len(train),
                "not_prospectively_calibrated":True,
                "not_a_live_V03_replacement":True,
                "real_market_odds_not_used_to_fit":True,
                "forecast_training_cutoff_utc":forecast.isoformat()}
    suppressed=0
    for g in board["games"]:
        g["opponent_rating"]=scores.get(str(g["game_id"]))
        g["home_bias_quarantined"]=bool(fail)
        if fail and g.get("market_home_spread") is not None:
            # These are withheld from the website decision ledger as well.
            # The older immutable original V03 score stays for accountability.
            g["model_ats_side"]="PASS"
            g["ats_edge_points"]=None
            suppressed+=1
    after=[(g["game_id"],g["model_home_margin"],g["model_home_points"],
            g["model_away_points"],g["model_total"],g["research_home_win_probability"])
           for g in board["games"]]
    if after!=frozen:
        raise ValueError("Bias guard may not rewrite original V03 projections")
    selected=[g for g in board["games"] if
              g["opponent_rating"] is not None and
              parse_time(g["kickoff_utc"]).astimezone(ET).date().isoformat()==audit["local_date"]]
    alternate_home=sum(g["opponent_rating"]["predicted_home_margin"]>0 for g in selected)
    board["home_bias_audit"]={
        "status":quality,"method":STATUS,"opponent_model":MODEL,
        "opponent_model_status":"RESEARCH_NOT_PROMOTED",
        "source_same_forecast_training_run_verified":len(scores)>0,
        "source_training_games":max((p["source_training_games"] for p in scores.values()),default=0),
        "opponent_rating_games":len(scores),
        "training_raw_mean_home_margin":training_home_margin,
        "training_game_count":training_games,
        "today_opponent_rating_games":len(selected),
        "today_opponent_home_picks":alternate_home,
        "today_opponent_home_pick_fraction":round(alternate_home/len(selected),5) if selected else None,
        "quarantined_ats_lines":suppressed,
        "snapshot_training_observed_utc":forecast.isoformat(),
        "model_market_odds_used_to_fit":False,
        "home_field_points_fixed_conservative_prior":HOME_ALLOWANCE,
        "score_archive_rewritten":False,
        "automatic_model_promotion":False,
        "betting_status":"PASS_UNVALIDATED",
        "warning":("V03 exhibits severe repeated home selections; its SU and ATS "
                   "direction is quarantined. Opponent R1 is an independent "
                   "research-only score-margin scenario, not validated bets."
                   if fail else "V03 home selections below circuit-breaker threshold."),
        **audit}
    return board

def run(dashboard,score_dir):
    p=Path(dashboard);board=json.loads(p.read_text(encoding="utf-8"))
    root=Path(score_dir)
    needed=[root/"games_2026.csv",root/"manifest.json",
            root/"context/upcoming_game_context_2026.json",
            root/"pregame_evidence"/("step3g-forecast-"+str(board["forecast_run_id"])+".json")]
    if all(x.is_file() for x in needed):
        with needed[0].open(newline="",encoding="utf-8") as f:
            rows=list(csv.DictReader(f))
        manifest=json.loads(needed[1].read_text(encoding="utf-8"))
        context=json.loads(needed[2].read_text(encoding="utf-8"))
        saved=json.loads(needed[3].read_text(encoding="utf-8"))["record"]
        hashes=saved["model_training"]["source_hashes"]
        if (str(saved["run_id"])!=str(board["forecast_run_id"]) or
            checksum(saved)!=board["forecast_sha256"] or
            hashlib.sha256(needed[0].read_bytes()).hexdigest()!=hashes["completed_score_csv_sha256"] or
            hashlib.sha256(needed[1].read_bytes()).hexdigest()!=hashes["scoreboard_manifest_sha256"] or
            saved["forecast_observed_utc"]!=board["forecast_observed_utc"]):
            raise ValueError("Game-day opponent rating source differs from immutable forecast source")
        result=apply(board,rows,manifest,context)
    elif not any(x.is_file() for x in needed):
        result=apply(board)
        # A score-file download failure cannot silently reinstate
        # V03 selections after the known severe model home-bias incident.
        for game in result["games"]:
            if game.get("market_home_spread") is not None:
                game["model_ats_side"]="PASS"
                game["ats_edge_points"]=None
            game["home_bias_quarantined"]=True
        result["home_bias_audit"].update({
            "status":"V03_HOME_BIAS_SOURCE_MISSING_FAIL_CLOSED",
            "warning":"No same-run completed-game score evidence. V03 directional and ATS research picks withheld; no opponent model inferred.",
            "quarantined_ats_lines":sum(g.get("market_home_spread") is not None for g in result["games"])})
    else:
        raise ValueError("Partial model evidence is unsafe; no fallback to guessed teams")
    p.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(result["home_bias_audit"],sort_keys=True))
    return result

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--dashboard",required=True)
    a.add_argument("--source-dir",required=True)
    v=a.parse_args()
    run(v.dashboard,v.source_dir)

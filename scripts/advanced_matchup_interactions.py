"""Research-only nonlinear team-style interaction features.

Derived from prior-date team profiles. No fitted score coefficient, lineup
value or sportsbook recommendation is claimed for these interactions.
"""
import argparse
import json
import math
from pathlib import Path

STATUS="NONLINEAR_MATCHUP_INTERACTIONS_RESEARCH_ONLY"

def finite(value):
    return type(value) in (int,float) and math.isfinite(value)

def product(*xs):
    return round(math.prod(xs),8) if all(finite(x) for x in xs) else None

def difference(a,b):
    return round(a-b,8) if finite(a) and finite(b) else None

def interactions(home,away):
    # The proposed interaction directions are intentionally descriptive.
    # They need coefficients learned from held-out historical folds.
    return {
        "home_pressure_times_pass_reliance":product(
            home.get("pass_rate"),home.get("pressure_allowed"),away.get("pressure_generated")),
        "away_pressure_times_pass_reliance":product(
            away.get("pass_rate"),away.get("pressure_allowed"),home.get("pressure_generated")),
        "home_run_off_vs_away_run_def":product(
            home.get("run_off"),away.get("run_def_allowed")),
        "away_run_off_vs_home_run_def":product(
            away.get("run_off"),home.get("run_def_allowed")),
        "home_pass_explosiveness_vs_away_pass_def":product(
            home.get("pass_explosive_off"),away.get("pass_def_allowed")),
        "away_pass_explosiveness_vs_home_pass_def":product(
            away.get("pass_explosive_off"),home.get("pass_def_allowed")),
        "pressure_reliance_gap":difference(
            product(home.get("pass_rate"),home.get("pressure_allowed"),away.get("pressure_generated")),
            product(away.get("pass_rate"),away.get("pressure_allowed"),home.get("pressure_generated"))),
        "run_matchup_gap":difference(
            product(home.get("run_off"),away.get("run_def_allowed")),
            product(away.get("run_off"),home.get("run_def_allowed"))),
    }

def build(board):
    if (board.get("status")!="TEAM_OPPONENT_MATCHUP_STYLE_RESEARCH_ONLY"
        or board.get("betting_status")!="PASS_UNVALIDATED"
        or board.get("model_promoted") is not False
        or board.get("historical_publication_authenticated") is not False):
        raise ValueError("Untrusted team source board")
    profiles=board["profiles"]
    games=[]
    seen=set()
    for g in board["games"]:
        gid=str(g["game_id"])
        if gid in seen or g["home"] not in profiles or g["away"] not in profiles:
            raise ValueError("Duplicate game or missing prior team")
        seen.add(gid)
        features=interactions(profiles[g["home"]],profiles[g["away"]])
        games.append({
            "game_id":gid,"home":g["home"],"away":g["away"],"kickoff_utc":g["kickoff_utc"],
            "interactions":features,
            "complete_interactions":sum(v is not None for v in features.values()),
            "learned_model_coefficients":None,
            "model_forecast_margin_adjustment":None,
        })
    return {"status":STATUS,"games":games,"feature_count":8,
        "historical_publication_authenticated":False,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

def run(input_path,output_path):
    result=build(json.loads(Path(input_path).read_text()))
    p=Path(output_path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--input",required=True)
    p.add_argument("--output",required=True);a=p.parse_args();run(a.input,a.output)

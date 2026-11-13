"""V14 score-conditional context + source-verified player-opportunity scenarios.

Reuses the existing *conservation-first* shared-possession/attempts/catches/
yardage simulator. V14 score projections are recorded on the same game ID,
but we DO NOT pretend the point estimate is a fitted player-target allocation
coefficient or turn boxscore averages into betting prop observations.
All player activity is a conditional scenario unless explicitly sourced.
"""
import math
from scripts.game_context import parse_time
from scripts.player_prop_conserved_opportunities import simulate as conserve
from scripts.v14_residual_challenger import STATUS as V14_SCORE

STATUS="V14_GAME_AND_CONSERVED_PLAYER_OPPORTUNITIES_RESEARCH_ONLY"


def simulate(gamefit,roles,forecast,decision_utc,quotes=None,trials=400,seed=2026):
    if (forecast.get("status")!=V14_SCORE or
        forecast.get("model_promoted") is not False or
        forecast.get("safe_for_betting") is not False or
        forecast.get("current_market_line_used_for_training") is not False or
        forecast.get("historical_source_first_publication_verified") is not False or
        not forecast.get("source_cutoff_exclusive") or
        any(type(forecast.get(k)) not in (int,float) or
            not math.isfinite(forecast[k]) for k in
            ("home_points","away_points","margin","total")) or
        min(forecast["home_points"],forecast["away_points"])<0 or
        abs(forecast["home_points"]-forecast["away_points"]-
            forecast["margin"])>.02 or
        abs(forecast["home_points"]+forecast["away_points"]-
            forecast["total"])>.02):
        raise ValueError("V14 cannot attach unverified or promoted model to player opportunities")
    now=parse_time(decision_utc)
    if now>=parse_time(gamefit["kickoff_utc"]):
        raise ValueError("Cannot forecast player markets after kickoff")
    import datetime as dt
    if (forecast["source_cutoff_exclusive"]>
        now.date().isoformat()):
        raise ValueError("Future weekly V14 matchup source")
    result=conserve(gamefit,roles,decision_utc,trials=trials,
                    seed=seed,quotes=quotes)
    if (str(result["game_id"])!=str(gamefit["game_id"]) or
        {x["team"] for x in result["team_scenarios"]}!={gamefit["home"],gamefit["away"]} or
        result["team_stat_conservation"] is not True or
        result["unknown_players_preserved"] is not True):
        raise ValueError("V14 scored matchup did not reconcile player simulation")
    return {"status":STATUS,"game_id":str(gamefit["game_id"]),
            "kickoff_utc":gamefit["kickoff_utc"],
            "decision_utc":now.isoformat(),
            "score_model":V14_SCORE,
            "game_points":{"home":forecast["home_points"],
                           "away":forecast["away_points"],
                           "margin":forecast["margin"],
                           "total":forecast["total"]},
            "player_opportunity_model":result["status"],
            "player_opportunity_scenarios":result["team_scenarios"],
            "matched_sourced_prop_probabilities":
                result["v14_matched_player_prop_quote_probabilities"],
            "unsupported_verified_prop_categories":
                result["v14_unsupported_verified_prop_categories"],
            "shared_possession_distribution":True,
            "team_opportunities_conserved":True,
            "unknown_athletes_preserved":True,
            "player_active_scenario_conditional":True,
            "score_points_not_used_to_artificially_reweight_player_stat_shares":True,
            "fully_jointly_calibrated_game_and_player_scores":False,
            "historical_player_source_first_publication_authenticated":False,
            "player_prop_betting_edge_proven":False,
            "model_promoted":False,"safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED"}

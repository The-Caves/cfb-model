"""V06 research: detect sustained score-quality changes, without narratives.

Pre-registered rule. A team's last 3 *past games* must differ persistently
from the preceding 4 on opponent-adjusted margin / attack / defense residuals.
A one-game collapse or coach-news anecdote never changes a rating.

Use V05's source-matched fit as baseline, but remove V05's prior form adjustment
before computing a distinct V06 score variant. No inferred QB injury value;
the verified QB evidence system remains separate and still incomplete.
"""
import datetime as dt
import math
from statistics import median
from collections import defaultdict
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time
from scripts.site_home_bias_guard import _source_games, MARGIN_CAP
from scripts.v05_robust_scores import (
    MODEL as V05_MODEL, STATUS as V05_STATUS,
    predict as predict_v05, MIN_TOTAL, MAX_TOTAL, MAX_MARGIN)

MODEL="V06_SUSTAINED_OPPONENT_ADJUSTED_REGIME_RESEARCH_ONLY"
STATUS="V06_PRIOR_SCORE_REGIME_SHADOW_NO_PERSONNEL_INFERENCE"
RECENT=3
REFERENCE=4
MIN_MOVE=4.0
MAX_OFFENSE_SHIFT=3.5
MAX_DEFENSE_SHIFT=3.5
MAX_MARGIN_SHIFT=4.0
MAX_TEAM_CHANGE=6.0
HISTORY_MIN=RECENT+REFERENCE
_VARIANTS=("v06_full","v06_margin_only","v06_scoring_only","v06_no_change")


def _mean(values):
    return sum(values)/len(values)


def _signal(records,field,cap):
    """Compare separate recent and old game residuals with persistence gate."""
    if len(records)<HISTORY_MIN:
        return {"shift":0.,"available":False,"reference_games":min(len(records),REFERENCE),
                "recent_games":min(len(records),RECENT),
                "consistent_recent_games":0,"raw_change":None}
    newest=records[-RECENT:]
    older=records[-HISTORY_MIN:-RECENT]
    # Median-to-median change is resistant to one unlucky late score
    # and to a single anomalous game inside the older comparison set.
    reference=median([x[field] for x in older])
    recent=median([x[field] for x in newest])
    difference=recent-reference
    supportive=sum(((x[field]-reference)*difference>0 and
                    abs(x[field]-reference)>=MIN_MOVE/2)
                    for x in newest)
    # No post-hoc selection of "best" trend or reacting to one upset.
    if supportive<2 or abs(difference)<MIN_MOVE:
        shift=0.
    else:
        # Prior shrinkage, dead zone and capped effective team score change.
        shift=math.copysign(min(cap,(abs(difference)-MIN_MOVE)*.45*.6),difference)
    return {"shift":round(shift,5),"available":True,
            "reference_games":REFERENCE,"recent_games":RECENT,
            "consistent_recent_games":supportive,
            "raw_change":round(difference,5)}


def fit(rows,forecast_utc,v05):
    forecast=parse_time(forecast_utc)
    if (not isinstance(v05,dict) or v05.get("model")!=V05_MODEL or
        v05.get("status")!=V05_STATUS or
        v05.get("model_promoted") is not False or
        v05.get("market_used_for_fit") is not False or
        parse_time(v05.get("asof_utc"))!=forecast or
        v05.get("source_training_games")!=len(rows)):
        raise ValueError("V06 requires exactly matched prior-only V05 cohort")
    games=_source_games(rows,forecast)
    if len(games)!=len(rows):
        raise ValueError("V06 training cohort identity differs")
    cutoff=forecast.astimezone(ZoneInfo("America/New_York")).date()
    history=defaultdict(list)
    games_to_fit=sorted(zip(rows,games),key=lambda item:(
        item[0]["date"],item[0]["kickoff_utc"],str(item[0]["game_id"])))
    for row,(home,away,margin,neutral) in games_to_fit:
        when=parse_time(row["kickoff_utc"])
        if dt.date.fromisoformat(row["date"])>=cutoff or when>=forecast:
            raise ValueError("Same-day or future V06 final")
        if home not in v05["strength"] or away not in v05["strength"]:
            raise ValueError("Unmatched V06 team strengths")
        venue=0. if neutral else v05["home_field_points"]
        expected_margin=v05["strength"][home]-v05["strength"][away]+venue
        observed=max(-MARGIN_CAP,min(MARGIN_CAP,margin))
        # Robust score residuals, not bookmaker lines or win/loss narratives.
        hp=min(70.,float(row["home_score"]))
        ap=min(70.,float(row["away_score"]))
        expected_hp=(v05["baseline_team_points"]+
             v05["offense"][home]-v05["defense"][away]+venue/2.)
        expected_ap=(v05["baseline_team_points"]+
             v05["offense"][away]-v05["defense"][home]-venue/2.)
        home_error=max(-30.,min(30.,hp-expected_hp))
        away_error=max(-30.,min(30.,ap-expected_ap))
        margin_error=max(-30.,min(30.,observed-expected_margin))
        history[home].append({"margin":margin_error,"offense":home_error,
                               "defense":-away_error})
        history[away].append({"margin":-margin_error,"offense":away_error,
                               "defense":-home_error})
    states={}
    for team in v05["strength"]:
        records=history.get(team,[])
        margin=_signal(records,"margin",MAX_MARGIN_SHIFT)
        offense=_signal(records,"offense",MAX_OFFENSE_SHIFT)
        defense=_signal(records,"defense",MAX_DEFENSE_SHIFT)
        states[team]={"games":len(records),"margin":margin,
                      "offense":offense,"defense":defense,
                      "sufficient_comparison":len(records)>=HISTORY_MIN}
    return {"status":STATUS,"model":MODEL,"asof_utc":forecast.isoformat(),
            "source_training_games":len(rows),"states":states,
            "recent_games_required":RECENT,"older_games_required":REFERENCE,
            "minimum_mean_residual_change":MIN_MOVE,
            "home_rating_not_modified":True,
            "verified_qb_effect_used":False,"qb_status_not_assumed":True,
            "coach_narratives_used":False,
            "all_training_games_before_forecast_day":True,
            "publication_timestamp_history_authenticated":False,
            "no_market_lines_in_fit":True,
            "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}


def predict(fitted,v05,home,away,neutral,variant="v06_full"):
    if variant not in _VARIANTS:
        raise ValueError("Unregistered V06 regime ablation")
    if (not isinstance(fitted,dict) or fitted.get("model")!=MODEL or
        fitted.get("status")!=STATUS or fitted.get("model_promoted") is not False or
        not isinstance(v05,dict) or v05.get("model")!=V05_MODEL or
        v05.get("status")!=V05_STATUS or
        parse_time(fitted["asof_utc"])!=parse_time(v05["asof_utc"]) or
        fitted["source_training_games"]!=v05["source_training_games"] or
        type(neutral) is not bool):
        raise ValueError("V06/V05 provenance mismatch")
    base=predict_v05(v05,home,away,neutral,"v05_no_form")
    if base is None:return None
    home_state=fitted["states"][home];away_state=fitted["states"][away]
    def delta(state,key):
        return state[key]["shift"]
    score_home=delta(home_state,"offense")+delta(away_state,"defense")
    score_away=delta(away_state,"offense")+delta(home_state,"defense")
    score_home=max(-MAX_TEAM_CHANGE,min(MAX_TEAM_CHANGE,score_home))
    score_away=max(-MAX_TEAM_CHANGE,min(MAX_TEAM_CHANGE,score_away))
    strength_shift=delta(home_state,"margin")-delta(away_state,"margin")
    if variant=="v06_no_change":
        score_home=score_away=strength_shift=0.
    if variant=="v06_margin_only":
        score_home=score_away=0.
    if variant=="v06_scoring_only":
        strength_shift=0.
    # With two coherent score effects, cap momentum without magical value
    # from a named player's absence; 40% margin and 60% scored-point gap.
    margin=(base["home_margin"]+.4*strength_shift+
            .6*(score_home-score_away))
    total=base["total_points"]+score_home+score_away
    total=max(MIN_TOTAL,min(MAX_TOTAL,total))
    margin=max(-min(MAX_MARGIN,total),min(min(MAX_MARGIN,total),margin))
    home_points=(total+margin)/2.
    away_points=(total-margin)/2.
    if not all(math.isfinite(z) and z>=0 for z in (home_points,away_points,total)):
        raise ValueError("V06 score went nonfinite")
    return {"status":STATUS,"model":MODEL,"variant":variant,
            "home_margin":round(margin,4),"total_points":round(total,4),
            "home_points":round(home_points,4),"away_points":round(away_points,4),
            "neutral":neutral,"source_training_games":fitted["source_training_games"],
            "home_recent_score_games":home_state["games"],
            "away_recent_score_games":away_state["games"],
            "home_regime_evaluable":home_state["sufficient_comparison"],
            "away_regime_evaluable":away_state["sufficient_comparison"],
            "margin_regime_adjustment":round(margin-base["home_margin"],4),
            "total_regime_adjustment":round(total-base["total_points"],4),
            "home_offense_change":home_state["offense"]["shift"],
            "away_offense_change":away_state["offense"]["shift"],
            "home_defense_change":home_state["defense"]["shift"],
            "away_defense_change":away_state["defense"]["shift"],
            "home_margin_change":home_state["margin"]["shift"],
            "away_margin_change":away_state["margin"]["shift"],
            "qb_effect_applied":False,"unverified_injury_effect_applied":False,
            "coach_narrative_applied":False,"no_market_lines_in_training":True,
            "no_v03_reuse":True,"home_field_not_reestimated":True,
            "score_model_promoted":False,"safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED"}

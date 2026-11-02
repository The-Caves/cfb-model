"""Fixed, preregistered V04/V05 equal-score ensemble; research only.

The blend has no fitted weights and consumes ONLY two pregame source-observed
score projections. This is not an ATS selection, win probability or a claim of
predictive lift. A result cannot be retrospectively substituted as a forecast.
"""
import math

from scripts.v04_direct_scores import MODEL as V04_MODEL, STATUS as V04_STATUS
from scripts.v05_robust_scores import MODEL as V05_MODEL, STATUS as V05_STATUS

MODEL="V04_V05_FIXED_50_50_SCORE_ENSEMBLE_RESEARCH_ONLY"
STATUS="INDEPENDENT_PREGAME_SCORE_BLEND_UNVALIDATED"
WEIGHT_V04=.5
WEIGHT_V05=.5


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def blend(v04,v05):
    if (not isinstance(v04,dict) or not isinstance(v05,dict) or
        v04.get("model")!=V04_MODEL or v04.get("status")!=V04_STATUS or
        v05.get("model")!=V05_MODEL or v05.get("status")!=V05_STATUS or
        v05.get("variant")!="v05_full" or
        v04.get("model_promoted") is not False or
        v05.get("model_promoted") is not False or
        v04.get("no_market_lines_in_training") is not True or
        v05.get("no_market_lines_in_training") is not True or
        v04.get("direct_scoring_fit_uses_v03_total") is not False or
        v05.get("no_v03_forecast_reuse") is not True or
        type(v04.get("neutral")) is not bool or
        v04.get("neutral")!=v05.get("neutral") or
        type(v04.get("source_training_games")) is not int or
        v04["source_training_games"]!=v05.get("source_training_games")):
        raise ValueError("Mismatched research score model provenance")
    for p in (v04,v05):
        hp=p.get("home_points");ap=p.get("away_points")
        m=p.get("home_margin");t=p.get("total_points")
        if not all(finite(x) for x in (hp,ap,m,t)) or min(hp,ap,t)<0 or (
            abs(hp+ap-t)>.03 or abs(hp-ap-m)>.03):
            raise ValueError("Invalid input score conservation")
    home=(v04["home_points"]+v05["home_points"])/2
    away=(v04["away_points"]+v05["away_points"])/2
    if not all(math.isfinite(x) and x>=0 for x in (home,away)):
        raise ValueError("Nonfinite ensemble result")
    return {"status":STATUS,"model":MODEL,
            "home_points":round(home,4),
            "away_points":round(away,4),
            "home_margin":round(home-away,4),
            "total_points":round(home+away,4),
            "neutral":v04["neutral"],
            "source_training_games":v04["source_training_games"],
            "fixed_weights":{"v04":WEIGHT_V04,"v05":WEIGHT_V05},
            "selected_after_test_performance":False,
            "source_models_unpromoted":True,
            "market_lines_not_used":True,
            "not_a_wagering_probability":True,
            "model_promoted":False,
            "safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED"}

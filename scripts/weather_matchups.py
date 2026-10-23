"""Timestamp-safe, opponent-style weather interaction features for captured games.

Produces *features*, never trained point adjustments or claims about actual
game-day conditions. Weather remains UNKNOWN if the forecast is missing.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from scripts.game_context import parse_time
from scripts.personnel_features import verify_joined

STATUS = "OBSERVED_WEATHER_STYLE_FEATURES_RESEARCH_ONLY"
FIELDS = ("wind_pass_exposure", "wind_explosive_pass_exposure",
          "precip_rush_exposure", "cold_pass_exposure",
          "weather_wind_mph", "weather_precip_probability",
          "weather_temperature_f")

def _number(x, minimum=None, maximum=None):
    if type(x) not in (int, float) or not math.isfinite(x):
        return None
    if minimum is not None and x < minimum:
        return None
    if maximum is not None and x > maximum:
        return None
    return float(x)

def _interaction(context_game, joined_game):
    home = joined_game["team_profiles"]["home"]["recent_form"]
    away = joined_game["team_profiles"]["away"]["recent_form"]
    neutral = dict.fromkeys(FIELDS)
    if context_game.get("venue_indoor") is True:
        if context_game.get("weather_status") != "INDOOR_NOT_APPLICABLE":
            raise ValueError("Indoor venue has conflicting weather report")
        return {"evidence": "VERIFIED_INDOOR_EXPOSURE_ZERO",
                "features": {name: 0.0 for name in FIELDS},
                "weather_missing": False}
    if context_game.get("weather_status") != "LIVE_FORECAST":
        return {"evidence": "UNKNOWN_NO_PREGAME_FORECAST",
                "features": neutral, "weather_missing": True}
    wind = _number(context_game.get("wind_mph"), 0, 180)
    rain = _number(context_game.get("precip_probability_pct"), 0, 100)
    temp = _number(context_game.get("temperature_f"), -100, 160)
    if wind is None and rain is None and temp is None:
        return {"evidence": "UNKNOWN_INVALID_FORECAST_VALUES",
                "features": neutral, "weather_missing": True}
    pass_rates = [_number(side.get("pass_rate"), 0, 1) for side in (home, away)]
    explosive = [_number(side.get("explosive_pass"), 0, 1) for side in (home, away)]
    rush_rates = [1 - p if p is not None else None for p in pass_rates]
    def avg(pair):
        return sum(pair)/2 if all(x is not None for x in pair) else None
    pass_avg = avg(pass_rates)
    explosive_avg = avg(explosive)
    rush_avg = avg(rush_rates)
    # Pure transformations: numerical effect sizes must be fit on PRIOR games.
    strong_wind = max(0.0, wind - 12.0) if wind is not None else None
    wet = rain/100 if rain is not None else None
    cold = max(0.0, 40.0-temp) if temp is not None else None
    def multiply(a, b):
        return round(a*b, 6) if a is not None and b is not None else None
    return {"evidence": "CAPTURED_PREGAME_FORECAST_NOT_OUTCOME_WEATHER",
            "weather_missing": False,
            "features": {
                "wind_pass_exposure": multiply(strong_wind, pass_avg),
                "wind_explosive_pass_exposure": multiply(strong_wind, explosive_avg),
                "precip_rush_exposure": multiply(wet, rush_avg),
                "cold_pass_exposure": multiply(cold, pass_avg),
                "weather_wind_mph": wind, "weather_precip_probability": rain,
                "weather_temperature_f": temp}}

def build(joined, context):
    verify_joined(joined)
    if context.get("safe_for_betting") is True or context.get("betting_status") != "PASS_UNVALIDATED":
        raise ValueError("Untrusted weather context")
    asof = parse_time(context["asof_utc"])
    capture = parse_time(context["captured_at_utc"])
    decision = parse_time(joined["captured_at_utc"])
    if not asof <= capture <= decision:
        raise ValueError("Weather context captured after decision")
    source = {}
    for game in context.get("games", []):
        gid = str(game["game_id"])
        if gid in source:
            raise ValueError("Duplicate weather-context game")
        source[gid] = game
    records = []
    for game in joined["games"]:
        gid = str(game["game_id"])
        ctx = source.get(gid)
        if ctx is None:
            raise ValueError("Joined game has no observed weather context")
        if (ctx["home"] != game["home"] or ctx["away"] != game["away"] or
            parse_time(ctx["kickoff_utc"]) != parse_time(game["kickoff_utc"])):
            raise ValueError("Weather context identity mismatch")
        if not decision < parse_time(game["kickoff_utc"]):
            raise ValueError("Postkickoff weather feature")
        issued = parse_time(ctx["forecast_issue_utc"])
        if not issued <= capture:
            raise ValueError("Forecast issuance after capture")
        values = _interaction(ctx, game)
        records.append({"game_id": gid, "home": game["home"], "away": game["away"],
                        "kickoff_utc": game["kickoff_utc"],
                        "decision_asof_utc": joined["captured_at_utc"],
                        "forecast_issued_at_utc": ctx["forecast_issue_utc"],
                        "forecast_captured_at_utc": context["captured_at_utc"],
                        **values})
    raw = json.dumps(context, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {"status": STATUS, "season": 2026, "run_id": joined["run_id"],
            "context_sha256": hashlib.sha256(raw).hexdigest(),
            "captured_at_utc": joined["captured_at_utc"],
            "games": records, "summary": {
                "games": len(records), "forecast_or_indoor_count": sum(not x["weather_missing"] for x in records),
                "unknown_weather_count": sum(x["weather_missing"] for x in records)},
            "historical_forecast_publication_independently_attested": False,
            "weather_effects_trained": False, "safe_for_betting": False,
            "betting_status": "PASS_UNVALIDATED"}

def run(joined_path, context_path, output_path):
    a = json.loads(Path(joined_path).read_text())
    b = json.loads(Path(context_path).read_text())
    report = build(a, b)
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(report["summary"]))
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--joined", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.joined, args.context, args.output)

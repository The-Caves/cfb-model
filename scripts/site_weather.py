"""Attach strictly matched, source-timed forecast context to CFB game cards.

Open-Meteo forecast observations are NOT actual game weather, model coefficient
adjustments, nor post-kickoff evidence. Missing data remains unknown.
"""
import argparse
import datetime as dt
import gzip
import json
import math
from pathlib import Path

from scripts.game_context import parse_time

STATUS = "SOURCE_TIMED_PREGAME_WEATHER_DISPLAY_ONLY"


def _number(value, low, high):
    return float(value) if type(value) in (int, float) and math.isfinite(value) and low <= value <= high else None


def attach(board, context, now):
    if board.get("schema_version") != 2 or board.get("betting_status") != "PASS_UNVALIDATED":
        raise ValueError("Invalid CFB dashboard")
    now = parse_time(now)
    records = {}
    if context is not None:
        if not isinstance(context, dict) or not isinstance(context.get("games"), list):
            raise ValueError("Invalid context-state weather archive")
        captured = parse_time(context["asof_utc"])
        if captured > now:
            raise ValueError("Future-dated weather context")
        for row in context["games"]:
            gid = str(row.get("game_id", ""))
            if not gid or gid in records:
                raise ValueError("Missing or duplicated archived weather game")
            records[gid] = row
    matched = risky = unknown = 0
    for game in board["games"]:
        game["weather"] = {"status": "UNKNOWN", "risk": False}
        row = records.get(str(game["game_id"]))
        if not row:
            unknown += 1
            continue
        kickoff = parse_time(game["kickoff_utc"])
        if (row.get("home") != game["home_team"] or
                row.get("away") != game["away_team"] or
                abs((parse_time(row["kickoff_utc"]) - kickoff).total_seconds()) > 900):
            unknown += 1
            continue
        captured = parse_time(context["asof_utc"])
        if captured >= kickoff:
            unknown += 1
            continue
        issued = row.get("forecast_issue_utc")
        if not issued or parse_time(issued) > captured or parse_time(issued) >= kickoff:
            unknown += 1
            continue
        if row.get("venue_indoor") is True:
            if row.get("weather_status") != "INDOOR_NOT_APPLICABLE":
                unknown += 1
                continue
            game["weather"] = {"status": "INDOOR", "risk": False, "source": "Verified venue context",
                                "captured_at_utc": context["asof_utc"]}
            matched += 1
            continue
        if row.get("weather_status") != "LIVE_FORECAST" or row.get("weather_source") != "OPEN_METEO_LIVE_FORECAST":
            unknown += 1
            continue
        observed = row.get("forecast_retrieved_utc")
        if not observed or parse_time(observed) > captured or parse_time(observed) >= kickoff:
            unknown += 1
            continue
        temp = _number(row.get("temperature_f"), -100, 150)
        wind = _number(row.get("wind_mph"), 0, 180)
        gust = _number(row.get("gust_mph"), 0, 200)
        rain = _number(row.get("precip_probability_pct"), 0, 100)
        if all(x is None for x in (temp, wind, gust, rain)):
            unknown += 1
            continue
        flags = []
        if wind is not None and wind >= 18 or gust is not None and gust >= 30:
            flags.append("WIND")
        if rain is not None and rain >= 60:
            flags.append("PRECIPITATION")
        if temp is not None and temp <= 35:
            flags.append("COLD")
        if temp is not None and temp >= 95:
            flags.append("HEAT")
        game["weather"] = {
            "status": "FORECAST", "risk": bool(flags), "flags": flags,
            "temperature_f": temp, "wind_mph": wind, "gust_mph": gust,
            "precip_probability_pct": rain,
            "source": "Open-Meteo", "captured_at_utc": observed,
            "venue_precision": row.get("weather_location_precision", "CITY_CENTROID"),
            "conditions_do_not_adjust_frozen_scores": True,
        }
        matched += 1
        risky += bool(flags)
    board["weather_display"] = {
        "status": STATUS, "forecast_games": matched, "flagged_games": risky,
        "unknown_games": unknown, "source": "Open-Meteo / archived Context Delta",
        "forecast_not_actual_observation": True,
        "frozen_model_scores_changed": False,
    }
    return board


def run(dashboard, context_path, now=None):
    file = Path(dashboard)
    board = json.loads(file.read_text(encoding="utf-8"))
    archive = Path(context_path)
    context = json.loads(gzip.decompress(archive.read_bytes())) if archive.is_file() else None
    result = attach(board, context, now or dt.datetime.now(dt.timezone.utc).isoformat())
    file.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["weather_display"], sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--context", required=True)
    args = parser.parse_args()
    run(args.dashboard, args.context)

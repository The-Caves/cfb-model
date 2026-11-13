"""Source-timed weather for CFB matchups with bounded archived-forecast recovery.

A failed Open-Meteo refresh must not erase a still-recent authentic forecast.
Every fallback must match ESPN game ID, schools, kickoff and actual collection
timestamps. Prior forecasts are clearly marked as cached, not current weather.
"""
import argparse
import datetime as dt
import gzip
import json
import math
from pathlib import Path

from scripts.game_context import parse_time

STATUS = "SOURCE_TIMED_PREGAME_WEATHER_DISPLAY_ONLY"
MAX_AGE_HOURS = 48
CONDITION_FIELDS = ("temperature_f", "wind_mph", "gust_mph",
                    "precip_probability_pct", "precip_mm")
PROVENANCE_FIELDS = ("weather_source", "forecast_issue_utc",
                     "forecast_retrieved_utc", "weather_location_precision")


def _number(value, low, high):
    return float(value) if type(value) in (int, float) and math.isfinite(value) and low <= value <= high else None


def _identity(candidate, game):
    return (str(candidate.get("game_id", "")) == str(game.get("game_id", "")) and
            candidate.get("home") == game.get("home_team", game.get("home")) and
            candidate.get("away") == game.get("away_team", game.get("away")) and
            abs((parse_time(candidate["kickoff_utc"]) -
                 parse_time(game["kickoff_utc"])).total_seconds()) <= 900)


def _candidate(row, captured_utc, game, now, max_age_hours=MAX_AGE_HOURS):
    if not isinstance(row, dict) or not _identity(row, game):
        return None
    captured = parse_time(captured_utc)
    kickoff = parse_time(game["kickoff_utc"])
    if captured > now or captured >= kickoff or kickoff <= now:
        return None
    if row.get("venue_indoor") is True and row.get("weather_status") == "INDOOR_NOT_APPLICABLE":
        return {"kind": "INDOOR", "captured_at_utc": captured.isoformat(),
                "retrieved": captured}
    if (row.get("venue_indoor") is True or row.get("weather_status") != "LIVE_FORECAST"
        or row.get("weather_source") != "OPEN_METEO_LIVE_FORECAST"):
        return None
    issue = row.get("forecast_issue_utc")
    observed = row.get("forecast_retrieved_utc")
    if not issue or not observed:
        return None
    issued = parse_time(issue)
    retrieved = parse_time(observed)
    if (issued > retrieved or retrieved > captured or retrieved >= kickoff
        or retrieved > now or (now-retrieved).total_seconds() < 0
        or (now-retrieved).total_seconds() > max_age_hours*3600):
        return None
    temp = _number(row.get("temperature_f"), -100, 150)
    wind = _number(row.get("wind_mph"), 0, 180)
    gust = _number(row.get("gust_mph"), 0, 200)
    rain = _number(row.get("precip_probability_pct"), 0, 100)
    if all(x is None for x in (temp, wind, gust, rain)):
        return None
    return {"kind": "FORECAST", "retrieved": retrieved,
            "captured_at_utc": observed, "context_asof_utc": captured_utc,
            "temperature_f": temp, "wind_mph": wind, "gust_mph": gust,
            "precip_probability_pct": rain, "precip_mm": _number(row.get("precip_mm"), 0, 1000),
            "venue_precision": row.get("weather_location_precision", "CITY_CENTROID"),
            "row": row}


def attach(board, context, now, history=None, max_age_hours=MAX_AGE_HOURS):
    if board.get("schema_version") != 2 or board.get("betting_status") != "PASS_UNVALIDATED":
        raise ValueError("Invalid CFB dashboard")
    now = parse_time(now)
    if type(max_age_hours) not in (float, int) or not 1 <= max_age_hours <= 72:
        raise ValueError("Weather forecast retention window must be bounded")
    sources = []
    for source in [context] + list(history or []):
        if source is None:
            continue
        if not isinstance(source, dict) or not isinstance(source.get("games"), list):
            raise ValueError("Invalid context-state weather archive")
        captured = parse_time(source["asof_utc"])
        if captured > now:
            raise ValueError("Future-dated weather context")
        records = {}
        for row in source["games"]:
            gid = str(row.get("game_id", ""))
            if not gid or gid in records:
                raise ValueError("Missing or duplicated archived weather game")
            records[gid] = row
        sources.append((source["asof_utc"], records))
    matched = risky = unknown = cached = 0
    for game in board["games"]:
        game["weather"] = {"status": "UNKNOWN", "risk": False}
        options = []
        for index, (asof, records) in enumerate(sources):
            row = records.get(str(game["game_id"]))
            if not row:
                continue
            result = _candidate(row, asof, game, now, max_age_hours)
            if result:
                options.append((result["retrieved"], -index, result, index))
        if not options:
            unknown += 1
            continue
        _, _, winner, source_index = max(options, key=lambda x: (x[0], x[1]))
        if winner["kind"] == "INDOOR":
            game["weather"] = {
                "status": "INDOOR", "risk": False, "source": "Verified venue context",
                "captured_at_utc": winner["captured_at_utc"]}
            matched += 1
            continue
        flags = []
        if ((winner["wind_mph"] is not None and winner["wind_mph"] >= 18)
            or (winner["gust_mph"] is not None and winner["gust_mph"] >= 30)):
            flags.append("WIND")
        if winner["precip_probability_pct"] is not None and winner["precip_probability_pct"] >= 60:
            flags.append("PRECIPITATION")
        if winner["temperature_f"] is not None and winner["temperature_f"] <= 35:
            flags.append("COLD")
        if winner["temperature_f"] is not None and winner["temperature_f"] >= 95:
            flags.append("HEAT")
        was_cached = source_index > 0 or bool(winner["row"].get("weather_cached_from_asof_utc"))
        hours = round((now - winner["retrieved"]).total_seconds()/3600, 1)
        game["weather"] = {
            "status": "FORECAST", "risk": bool(flags), "flags": flags,
            "temperature_f": winner["temperature_f"],
            "wind_mph": winner["wind_mph"], "gust_mph": winner["gust_mph"],
            "precip_probability_pct": winner["precip_probability_pct"],
            "source": "Open-Meteo", "captured_at_utc": winner["captured_at_utc"],
            "age_hours": hours, "cached": was_cached, "source_retrieved_before_kickoff": True,
            "venue_precision": winner["venue_precision"],
            "conditions_do_not_adjust_frozen_scores": True,
        }
        cached += int(was_cached)
        matched += 1
        risky += bool(flags)
    board["weather_display"] = {
        "status": STATUS, "forecast_games": matched, "flagged_games": risky,
        "unknown_games": unknown, "cached_forecast_games": cached,
        "max_forecast_age_hours": max_age_hours,
        "source": "Open-Meteo / archived Context Delta",
        "forecast_not_actual_observation": True,
        "frozen_model_scores_changed": False,
    }
    return board


def load_history(directory, now, max_age_hours=MAX_AGE_HOURS, max_snapshots=18):
    """Read recent immutable context snapshots from the checked-out state branch."""
    root = Path(directory)
    if not root.is_dir():
        return []
    now = parse_time(now)
    previous = []
    days = 1 + math.ceil(max_age_hours/24)
    for delta in range(days + 1):
        day = (now - dt.timedelta(days=delta)).strftime("%Y/%m/%d")
        folder = root / day
        if not folder.is_dir():
            continue
        for p in folder.glob("*.json.gz"):
            try:
                name_time = dt.datetime.strptime(p.name, "%Y%m%dT%H%M%SZ.json.gz").replace(
                    tzinfo=dt.timezone.utc)
                if name_time > now or (now-name_time).total_seconds() > max_age_hours*3600:
                    continue
                previous.append((name_time, p))
            except ValueError:
                continue
    selected = sorted(previous, key=lambda z: z[0], reverse=True)[:max_snapshots]
    archives = []
    for stamp, p in selected:
        try:
            data = json.loads(gzip.decompress(p.read_bytes()))
            if parse_time(data["asof_utc"]) > now:
                continue
            archives.append(data)
        except (ValueError, OSError, KeyError, TypeError, gzip.BadGzipFile, json.JSONDecodeError):
            continue
    return archives


def restore_previous_weather(rows, previous, now, max_age_hours=MAX_AGE_HOURS):
    """During context ingest, retain ONLY previous sourced weather if a new fetch failed."""
    if previous is None or not isinstance(previous, dict):
        return 0
    asof = previous.get("asof_utc")
    if not asof:
        return 0
    cutoff = parse_time(now)
    if parse_time(asof) > cutoff:
        raise ValueError("Future-dated previous weather archive")
    old_rows = {str(g["game_id"]): g for g in previous.get("games", [])}
    restored = 0
    for row in rows:
        if row.get("weather_status") in ("LIVE_FORECAST", "INDOOR_NOT_APPLICABLE"):
            continue
        earlier = old_rows.get(str(row["game_id"]))
        if earlier is None:
            continue
        candidate = _candidate(earlier, asof, row, cutoff, max_age_hours)
        if candidate is None or candidate["kind"] != "FORECAST":
            continue
        for key in CONDITION_FIELDS + PROVENANCE_FIELDS:
            row[key] = earlier.get(key)
        row["weather_status"] = "LIVE_FORECAST"
        row["weather_cached_from_asof_utc"] = asof
        restored += 1
    return restored


def run(dashboard, context_path, now=None, history_dir=None):
    file = Path(dashboard)
    board = json.loads(file.read_text(encoding="utf-8"))
    archive = Path(context_path)
    context = json.loads(gzip.decompress(archive.read_bytes())) if archive.is_file() else None
    timestamp = now or dt.datetime.now(dt.timezone.utc).isoformat()
    history = load_history(history_dir, timestamp) if history_dir else []
    result = attach(board, context, timestamp, history=history)
    file.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["weather_display"], sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--history-dir")
    args = parser.parse_args()
    run(args.dashboard, args.context, history_dir=args.history_dir)

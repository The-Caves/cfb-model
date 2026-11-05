"""Source-timed ESPN live scores matched to previously archived CFB site picks.

Live scores and pre-kickoff model projections are intentionally separate.
This never generates a new prediction after kickoff, never uses postgame scores
for forecasting, and never writes to the immutable context-state branch.
"""
import argparse
import datetime as dt
import gzip
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time
from scripts.free_market_capture import BASE

ET = ZoneInfo("America/New_York")
STATUS = "ESPN_LIVE_SCORE_WITH_IMMUTABLE_PREGAME_SNAPSHOT_RESEARCH_ONLY"
ARCHIVE = "research_2026/site_board_snapshots/index.json"
MAX_SNAPSHOT_LOOKBACK_DAYS = 10
MAX_FETCH_DAYS = 2


def _canon(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _intscore(value):
    return int(value) if isinstance(value, str) and value.isdigit() and 0 <= int(value) <= 200 else (
        value if type(value) is int and 0 <= value <= 200 else None)


def _side(comp, homeaway):
    teams = [c for c in comp.get("competitors", [])
             if c.get("homeAway") == homeaway]
    if len(teams) != 1:
        return None
    item = teams[0]
    team = item.get("team") or {}
    name = team.get("displayName")
    return {"name": name, "score": _intscore(item.get("score"))} if name else None


def live_events(payload, observed_at):
    """Parse only ESPN games actively being played, never final/scheduled."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid live ESPN scoreboard")
    result = {}
    for event in payload.get("events", []):
        if not isinstance(event, dict):
            continue
        identity = str(event.get("id") or "")
        comps = (event.get("competitions") or [])
        status = event.get("status") or {}
        kind = status.get("type") or {}
        if (not identity.isdigit() or len(comps) != 1 or
            kind.get("state") != "in" or kind.get("completed") is True):
            continue
        comp = comps[0]
        away, home = _side(comp, "away"), _side(comp, "home")
        if not home or not away or home["score"] is None or away["score"] is None:
            continue
        kick = comp.get("date") or event.get("date")
        if not kick or parse_time(kick) > parse_time(observed_at):
            continue
        result[identity] = {
            "game_id": identity, "home_team": home["name"], "away_team": away["name"],
            "home_score": home["score"], "away_score": away["score"],
            "kickoff_utc": parse_time(kick).isoformat(),
            "period": int(status["period"]) if type(status.get("period")) is int
                      and 0 <= status["period"] <= 10 else None,
            "clock": str(status.get("displayClock") or "")[:18],
            "description": str(kind.get("shortDetail") or kind.get("description") or "Live")[:52],
            "state": "in",
            "source_observed_at_utc": parse_time(observed_at).isoformat(),
            "source": "ESPN_SCOREBOARD_ACTUAL_SCORE_NOT_MODEL"}
    return result


def fetch_day(day, when, opener=urllib.request.urlopen):
    url = BASE + "?dates=" + day.strftime("%Y%m%d") + "&limit=500&groups=80"
    request = urllib.request.Request(url, headers={
        "User-Agent": "CFB-Lab-live-game-observer/2026",
        "Accept": "application/json"})
    with opener(request, timeout=12) as response:
        payload = json.load(response)
    return live_events(payload, when)


def _snapshot_rows(root, runs, live, now):
    candidates = defaultdict(list)
    for r in runs:
        captured = parse_time(r["capture_utc"])
        if (captured > now or
            (now-captured).total_seconds() > MAX_SNAPSHOT_LOOKBACK_DAYS * 86400):
            continue
        for gid, game in live.items():
            if captured < parse_time(game["kickoff_utc"]):
                candidates[gid].append((captured, r["path"]))
    paths = {}
    for gid, options in candidates.items():
        options.sort(reverse=True)
        for _, path in options:
            paths.setdefault(path, set()).add(gid)
    result = {}
    # Newest genuine pre-kickoff snapshot wins; this is not a live model revision.
    for path in sorted(paths, key=lambda p: max(
            captured for gid, options in candidates.items()
            for captured, candidate in options if candidate == p), reverse=True):
        file = root / path
        if (file.suffixes != [".json", ".gz"] or
            ".." in Path(path).parts or Path(path).is_absolute() or
            not path.startswith("research_2026/site_board_snapshots/") or
            not file.is_file()):
            raise ValueError("Invalid immutable pregame snapshot path")
        raw = json.loads(gzip.decompress(file.read_bytes()))
        if (raw.get("status") != "IMMUTABLE_DISPLAYED_RESEARCH_MARKET_SNAPSHOT" or
            raw.get("betting_status") != "PASS_UNVALIDATED"):
            raise ValueError("Untrusted immutable website prediction receipt")
        capture = parse_time(raw["capture_utc"])
        for row in raw.get("rows", []):
            gid = str(row.get("game_id"))
            if gid not in paths[path] or gid in result:
                continue
            event = live[gid]
            kick = parse_time(event["kickoff_utc"])
            if (capture >= kick or
                abs((parse_time(row["kickoff_utc"])-kick).total_seconds()) > 900 or
                _canon(row.get("home")) != _canon(event["home_team"]) or
                _canon(row.get("away")) != _canon(event["away_team"])):
                continue
            # Prefer a coherent, independently modeled V04 estimate.
            hp, ap = row.get("v04_direct_home_points"), row.get("v04_direct_away_points")
            if not (type(hp) in (int,float) and type(ap) in (int,float) and
                    0 <= hp <= 100 and 0 <= ap <= 100 and
                    row.get("v04_research_not_promoted") is True):
                continue
            result[gid] = {
                "game_id": gid,
                "archived_model": "V04 independent team scoring · research",
                "archived_home_points": hp, "archived_away_points": ap,
                "archived_home_margin": row["v04_direct_home_margin"],
                "archived_total": row["v04_direct_total_points"],
                "archived_model_observed_at_utc": capture.isoformat(),
                "archived_model_source_run": raw["dashboard_run_id"],
                "archived_ats_side": row.get("v04_research_ats_side"),
                "archived_ou_side": row.get("v04_research_ou_side"),
                "archived_market_home_spread": row.get("market_home_spread"),
                "archived_market_total": row.get("market_total"),
                "pre_kickoff_archive_verified": True,
                "updated_after_kickoff": False}
    return result


def overlay(board, root, scoreboards, observed_at):
    now = parse_time(observed_at)
    if (board.get("schema_version") != 2 or
        board.get("betting_status") != "PASS_UNVALIDATED" or
        not isinstance(board.get("prospective_records"), dict)):
        raise ValueError("Untrusted research board / historical performance")
    originals = json.dumps(board["prospective_records"], sort_keys=True)
    active = {}
    for date, events in scoreboards:
        if not isinstance(events, dict):
            raise ValueError("Malformed ESPN live game capture")
        for gid, g in events.items():
            if gid in active:
                if active[gid] != g:
                    raise ValueError("Conflicting live scoreboard game observations")
            else:
                active[gid] = g
    archive = root / ARCHIVE
    runs = []
    if archive.is_file():
        index = json.loads(archive.read_text())
        if (index.get("status") != "IMMUTABLE_DISPLAYED_RESEARCH_MARKET_SNAPSHOT" or
            not isinstance(index.get("runs"), list)):
            raise ValueError("Untrusted historical model snapshot index")
        runs = index["runs"]
    pregame = _snapshot_rows(root, runs, active, now) if active else {}
    report = []
    for gid, event in active.items():
        if parse_time(event["source_observed_at_utc"]) > now:
            raise ValueError("Future observed scoreboard score")
        if event.get("state") != "in" or event.get("source") != "ESPN_SCOREBOARD_ACTUAL_SCORE_NOT_MODEL":
            raise ValueError("Non-live score masquerading as active")
        report.append({**event, "pregame": pregame.get(gid),
                       "has_archived_pregame_model": gid in pregame,
                       "in_game_model_update": None,
                       "in_game_model_validated": False})
    report.sort(key=lambda g:(g["kickoff_utc"], g["game_id"]))
    board["live_games"] = report
    board["live_display"] = {
        "status": STATUS, "source": "ESPN public scoreboard",
        "observed_at_utc": now.isoformat(),
        "live_game_count": len(report),
        "live_with_archived_pregame": len(pregame),
        "in_game_model_updates_available": False,
        "scoreboard_refresh_is_deployment_based": True,
        "original_pregame_forecasts_changed": False,
        "historical_grades_changed": False,
        "model_promoted": False,
        "betting_status": "PASS_UNVALIDATED"}
    if json.dumps(board["prospective_records"],sort_keys=True) != originals:
        raise ValueError("Live information altered cumulative historical grades")
    return board


def run(dashboard, history_root, now=None, fetcher=fetch_day):
    now = parse_time(now or dt.datetime.now(dt.timezone.utc).isoformat())
    file = Path(dashboard)
    board = json.loads(file.read_text())
    today = now.astimezone(ET).date()
    dates = [today-dt.timedelta(days=offset) for offset in range(MAX_FETCH_DAYS)]
    day_results, errors = [], []
    for day in dates:
        try:day_results.append((day.isoformat(),fetcher(day,now)))
        except Exception as exc:errors.append({"date":day.isoformat(),"reason":type(exc).__name__})
    board=overlay(board,Path(history_root),day_results,now.isoformat())
    board["live_display"]["fetch_failures"] = errors
    board["live_display"]["queried_days"] = len(dates)
    file.write_text(json.dumps(board,indent=2,allow_nan=False)+"\n")
    print(json.dumps(board["live_display"],sort_keys=True))
    return board


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dashboard",required=True)
    p.add_argument("--archive-root",required=True)
    a=p.parse_args()
    run(a.dashboard,a.archive_root)

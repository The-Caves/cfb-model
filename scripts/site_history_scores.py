"""Best-effort ESPN *completed* final score on historical PRESSBOX cards.

Independently settled final records retain priority. A matched ESPN result is
only a promptly observed display result, never an authenticated final-grade
archive, odds source, revised forecast, or simulated in-game estimate.
"""
import argparse
import datetime as dt
import json
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.free_market_capture import BASE
from scripts.game_context import parse_time
from scripts.site_history import _grade

ET = ZoneInfo("America/New_York")
STATUS = "ESPN_COMPLETED_SCORE_DISPLAY_NOT_ARCHIVED_GRADE"
SOURCE = "ESPN_PUBLIC_SCOREBOARD_COMPLETED"


def _score(raw):
    if type(raw) is int:
        return raw if 0 <= raw <= 200 else None
    if isinstance(raw, str) and raw.isdigit() and 0 <= int(raw) <= 200:
        return int(raw)
    return None


def capture(payload, observed_utc):
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError("Invalid ESPN completed scoreboard")
    matches = {}
    for event in payload["events"]:
        gid = str(event.get("id", ""))
        if not gid.isdigit():
            continue
        status = event.get("status") or {}
        state = status.get("type") or {}
        if state.get("state") != "post" or state.get("completed") is not True:
            continue
        competitions = event.get("competitions") or []
        if len(competitions) != 1:
            continue
        comp = competitions[0]
        teams = comp.get("competitors") or []
        home = [x for x in teams if x.get("homeAway") == "home"]
        away = [x for x in teams if x.get("homeAway") == "away"]
        if len(home) != 1 or len(away) != 1:
            continue
        h, a = home[0], away[0]
        home_score, away_score = _score(h.get("score")), _score(a.get("score"))
        kickoff = comp.get("date") or event.get("date")
        if not (h.get("team", {}).get("displayName") and a.get("team", {}).get("displayName")
                and home_score is not None and away_score is not None and kickoff):
            continue
        if parse_time(kickoff) >= parse_time(observed_utc):
            continue
        rec = {"game_id": gid, "home_team": h["team"]["displayName"],
               "away_team": a["team"]["displayName"], "kickoff_utc": kickoff,
               "home_score": home_score, "away_score": away_score,
               "observed_at_utc": observed_utc, "source": SOURCE}
        previous = matches.get(gid)
        if previous and previous != rec:
            raise ValueError("Conflicting ESPN completed score for identical game ID")
        matches[gid] = rec
    return matches


def apply(board, observations, observed_utc):
    if (board.get("schema_version") != 2 or
        board.get("betting_status") != "PASS_UNVALIDATED" or
        board.get("history_display", {}).get("status") !=
        "ARCHIVED_PREKICKOFF_V04_WITH_INDEPENDENT_FINAL"):
        raise ValueError("Unverified historical card export")
    frozen_scores = json.dumps([g.get("model_home_margin") for g in board["games"]])
    performance = json.dumps(board.get("prospective_records"), sort_keys=True)
    attached = 0
    for g in board.get("history_games", []):
        if g.get("final") is not None:
            continue
        event = observations.get(str(g["game_id"]))
        if not event:
            continue
        kick = parse_time(g["kickoff_utc"])
        if (event["home_team"] != g["home_team"] or
            event["away_team"] != g["away_team"] or
            abs((kick - parse_time(event["kickoff_utc"])).total_seconds()) > 900 or
            parse_time(event["observed_at_utc"]) < kick or
            parse_time(event["observed_at_utc"]) > parse_time(observed_utc)):
            continue
        final = {"home_score": event["home_score"], "away_score": event["away_score"],
                 "source": SOURCE, "outcome_known_at_utc": observed_utc}
        g["final"] = final
        row = {
            "v04_direct_home_margin": g.get("model_home_margin"),
            "v04_research_ats_side": g.get("ats_pick"),
            "v04_research_ou_side": g.get("ou_pick"),
            "market_home_spread": g.get("market_home_spread"),
            "market_total": g.get("market_total"),
        }
        g["outcomes"] = _grade(row, final, g.get("archived_model") == "V04")
        g["outcomes_display_only"] = True
        attached += 1
    board["history_display"]["espn_provisional_display_finals"] = attached
    board["history_display"]["settled_archive_finals"] = board["history_display"].get("verified_finals", 0)
    board["history_display"]["display_finals"] = sum(g.get("final") is not None
                                                     for g in board.get("history_games", []))
    board["history_display"]["display_score_source"] = STATUS
    if (json.dumps([g.get("model_home_margin") for g in board["games"]]) != frozen_scores or
        json.dumps(board.get("prospective_records"), sort_keys=True) != performance):
        raise ValueError("ESPN scoreboard changed frozen model or permanent grades")
    return board


def fetch_date(day, now, opener=urllib.request.urlopen):
    request = urllib.request.Request(
        BASE + "?dates=" + day.strftime("%Y%m%d") + "&limit=500&groups=80",
        headers={"User-Agent": "CFB-PRESSBOX-completed-display/2026",
                 "Accept": "application/json"})
    with opener(request, timeout=12) as response:
        return capture(json.load(response), now)


def run(dashboard, now=None, fetcher=fetch_date):
    file = Path(dashboard)
    board = json.loads(file.read_text())
    observed = parse_time(now or dt.datetime.now(dt.timezone.utc).isoformat())
    pending = [g for g in board.get("history_games", [])
               if g.get("final") is None and
               parse_time(g["kickoff_utc"]) <= observed and
               (observed - parse_time(g["kickoff_utc"])).days <= 3]
    dates = sorted(set(parse_time(g["kickoff_utc"]).astimezone(ET).date() for g in pending))
    reports, errors = {}, []
    for day in dates[:4]:
        try:
            events = fetcher(day, observed.isoformat())
            for gid, record in events.items():
                if gid in reports and reports[gid] != record:
                    raise ValueError("Conflicting completed events between date feeds")
                reports[gid] = record
        except (OSError, TimeoutError, ValueError, TypeError, KeyError) as exc:
            errors.append({"date": day.isoformat(), "error": type(exc).__name__})
    board = apply(board, reports, observed.isoformat())
    board["history_display"]["completed_scoreboard_fetch_failures"] = errors
    file.write_text(json.dumps(board, indent=2, allow_nan=False) + "\n")
    print(json.dumps(board["history_display"], sort_keys=True))
    return board


if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    arg.add_argument("--dashboard", required=True)
    args = arg.parse_args()
    run(args.dashboard)

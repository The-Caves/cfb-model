"""Pull completed 2026 college-football scoreboard finals with ET kickoff dates.

Event timestamps are UTC. Date-only score ledgers use America/New_York (ET),
not the first 10 characters of the UTC timestamp. Raw ESPN payloads and capture
manifests remain available for auditing; no advanced stats are inferred.
"""
import argparse
import csv
import datetime as dt
import json
import time
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
ET = ZoneInfo("America/New_York")
FIELDS = ["game_id", "date", "away", "home", "away_score", "home_score", "neutral", "kickoff_utc"]


def fetch_day(day):
    url = URL + "?dates=" + day.strftime("%Y%m%d") + "&limit=500&groups=80"
    request = urllib.request.Request(url, headers={
        "User-Agent": "cfb-model-research/0.2", "Accept": "application/json"
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload.get("events"), list):
        raise RuntimeError("ESPN scoreboard response lacked events list")
    return payload


def parse_event(event):
    comps = event.get("competitions") or []
    if not comps:
        return None
    competition = comps[0]
    sides = competition.get("competitors") or []
    home = next((item for item in sides if item.get("homeAway") == "home"), None)
    away = next((item for item in sides if item.get("homeAway") == "away"), None)
    if not home or not away or not event.get("status", {}).get("type", {}).get("completed"):
        return None
    try:
        a = int(away["score"])
        h = int(home["score"])
        kickoff = dt.datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        if kickoff.tzinfo is None:
            raise ValueError("No UTC offset on kickoff")
        utc = kickoff.astimezone(dt.timezone.utc)
        gid = str(event["id"])
    except (ValueError, TypeError, KeyError, OverflowError):
        return None
    return {
        "game_id": gid,
        "date": utc.astimezone(ET).date().isoformat(),
        "away": away.get("team", {}).get("displayName", ""),
        "home": home.get("team", {}).get("displayName", ""),
        "away_score": a,
        "home_score": h,
        "neutral": bool(competition.get("neutralSite", False)),
        "kickoff_utc": utc.isoformat().replace("+00:00", "Z")
    }


def ingest(start, end, output):
    if end > dt.date.today():
        end = dt.date.today()
    if end < start:
        raise ValueError("End date before start date")
    output.mkdir(parents=True, exist_ok=True)
    raw = output / "raw"
    raw.mkdir(exist_ok=True)
    games = {}
    failures = []
    day = start
    calls = 0
    while day <= end:
        try:
            payload = fetch_day(day)
            calls += 1
            (raw / (day.isoformat() + ".json")).write_text(json.dumps({
                "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "payload": payload
            }))
            for event in payload["events"]:
                row = parse_event(event)
                if row and row["away"] and row["home"]:
                    games[row["game_id"]] = row
        except Exception as err:
            failures.append({"date": str(day), "error": str(err)})
        day += dt.timedelta(days=1)
        time.sleep(.05)
    with (output / "games_2026.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(sorted(games.values(), key=lambda row: (row["date"], row["game_id"])))
    manifest = {
        "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "requested_start": str(start), "requested_end": str(end),
        "days_fetched": calls, "completed_games": len(games),
        "scoreboard_date_timezone": "America/New_York",
        "kickoff_utc_preserved": True,
        "failures": failures,
        "status": "SUCCESS" if games and not failures else "INCOMPLETE"
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if manifest["status"] != "SUCCESS":
        raise SystemExit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-08-01")
    parser.add_argument("--end", default=dt.date.today().isoformat())
    parser.add_argument("--output", default="data")
    args = parser.parse_args()
    ingest(dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end), Path(args.output))

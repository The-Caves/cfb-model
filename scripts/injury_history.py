"""As-of 2026 player-availability observations, not diagnoses or participation.

Game-team slots are intentionally complete even when no publisher report exists.
Missing or unlisted players are UNKNOWN. Quarantined evidence is never exported
as an accepted status. Published, captured, context and observation times are
all separate, explicit trust boundaries.
"""
import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from scripts.game_context import parse_time

STATUS = "INJURY_HISTORY_RESEARCH_ONLY"
COVERAGE = {"VERIFIED_REPORT_REVIEWED", "UNKNOWN"}
KINDS = {"INJURY", "AVAILABILITY"}
DESIGNATIONS = {"AVAILABLE", "PROBABLE", "QUESTIONABLE", "DOUBTFUL",
                "OUT", "SUSPENDED", "LIMITED", "GAME_TIME_DECISION", "UNKNOWN"}
POSITIONS = {"QB", "RB", "WR", "TE", "OL", "DL", "EDGE", "LB", "CB",
             "DB", "S", "K", "P", "OTHER"}


def _time(value):
    return parse_time(value)


def _source_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and bool(url.hostname)
                and not url.username and not url.password)
    except ValueError:
        return False


def _reason(row, reason):
    # Do not store the rejected status or future publication timestamp: doing
    # so would expose knowledge that was not safe to use at observation time.
    return {"player": str(row.get("player") or "")[:100], "reason": reason}


def _slot(game, team, opponent, when, context_asof):
    kickoff = _time(game["kickoff_utc"])
    mapping = game.get("injury_coverage_by_team") or {}
    coverage = mapping.get(team, "UNKNOWN") if isinstance(mapping, dict) else "UNKNOWN"
    if coverage not in COVERAGE:
        coverage = "UNKNOWN"
    record = {"game_id": str(game["game_id"]), "team": team,
              "opponent": opponent, "kickoff_utc": game["kickoff_utc"],
              "observed_at_utc": when.isoformat(), "coverage_status": coverage,
              "reported_players": [], "quarantined_evidence": [],
              "unlisted_players_status": "UNKNOWN",
              "diagnosis_verified": False, "participation_verified": False}
    # injury_reports and availability_reports alias the *same* upstream rows.
    # Reading both would manufacture conflicts and double-count the feed.
    rows = game.get("injury_reports")
    if rows is None:
        rows = game.get("availability_reports") or []
    if not isinstance(rows, list):
        record["quarantined_evidence"].append({"player": "", "reason": "INVALID_REPORT_CONTAINER"})
        return record
    by_player = defaultdict(list)
    for raw in rows:
        if not isinstance(raw, dict):
            record["quarantined_evidence"].append({"player": "", "reason": "INVALID_SOURCE_ROW"})
            continue
        if raw.get("team") != team:
            continue
        player = raw.get("player")
        position = raw.get("position")
        kind = raw.get("signal_kind")
        reported = raw.get("status")
        if (not isinstance(player, str) or not 2 <= len(player.strip()) <= 100
            or position not in POSITIONS or kind not in KINDS
            or reported not in DESIGNATIONS or not _source_url(raw.get("source_url"))):
            record["quarantined_evidence"].append(_reason(raw, "UNSUPPORTED_OR_UNSOURCED_STATUS"))
            continue
        try:
            pub = _time(raw["published_at_utc"])
            capture = _time(raw["captured_at_utc"])
        except (KeyError, ValueError, TypeError, OverflowError):
            record["quarantined_evidence"].append({"player": "", "reason": "INVALID_SOURCE_TIME"})
            continue
        if not (pub <= capture <= context_asof <= when < kickoff):
            record["quarantined_evidence"].append({"player": "", "reason": "SOURCE_OUTSIDE_ASOF_WINDOW"})
            continue
        item = {"player": player.strip(), "position": position,
                "signal_kind": kind, "reported_status": reported,
                "published_at_utc": raw["published_at_utc"],
                "captured_at_utc": raw["captured_at_utc"],
                "observed_at_utc": when.isoformat(),
                "source_url": raw["source_url"]}
        by_player[player.strip().casefold()].append(item)
    for group in by_player.values():
        # Same publication with competing designations is ambiguous even if
        # captured at different times. Do not pick whichever happened to win.
        publications = defaultdict(set)
        for item in group:
            publications[_time(item["published_at_utc"])].add(
                (item["reported_status"], item["position"]))
        if any(len(values) > 1 for values in publications.values()):
            record["quarantined_evidence"].append(
                {"player": group[0]["player"], "reason": "CONTRADICTORY_DESIGNATIONS"})
            continue
        ordered = sorted(group, key=lambda r: (_time(r["published_at_utc"]),
                                               _time(r["captured_at_utc"])))
        if any(_time(b["captured_at_utc"]) < _time(a["captured_at_utc"])
               for a, b in zip(ordered, ordered[1:])):
            record["quarantined_evidence"].append(
                {"player": group[0]["player"], "reason": "NONMONOTONIC_SOURCE_TIMES"})
            continue
        record["reported_players"].append(ordered[-1])
    record["reported_players"].sort(key=lambda r: (r["player"].casefold(), r["position"]))
    record["quarantined_evidence"].sort(key=lambda r: (r["player"].casefold(), r["reason"]))
    return record


def observe(context, observed_at):
    when = _time(observed_at)
    context_asof = _time(context["asof_utc"])
    capture = _time(context["captured_at_utc"])
    if not context_asof <= capture <= when:
        raise ValueError("Context source newer than injury observation")
    if context.get("betting_status", "PASS_UNVALIDATED") != "PASS_UNVALIDATED":
        raise ValueError("Unexpected context betting status")
    rows = []
    seen = set()
    for game in sorted(context.get("games", []),
                       key=lambda g: (g["kickoff_utc"], str(g["game_id"]))):
        game_id = str(game["game_id"])
        if game_id in seen:
            raise ValueError("Duplicate ESPN game ID")
        seen.add(game_id)
        if _time(game["kickoff_utc"]) <= when:
            continue
        home, away = game["home"], game["away"]
        if not home or not away or home == away:
            raise ValueError("Invalid game opponent identity")
        rows.extend((_slot(game, home, away, when, context_asof),
                     _slot(game, away, home, when, context_asof)))
    if not rows:
        raise ValueError("No pregame injury slots available")
    snapshot = {"status": STATUS, "season": 2026,
                "observed_at_utc": when.isoformat(),
                "context_asof_utc": context_asof.isoformat(),
                "context_captured_at_utc": capture.isoformat(),
                "rows": rows,
                "summary": {
                    "game_team_slots": len(rows),
                    "verified_team_reports": sum(r["coverage_status"] == "VERIFIED_REPORT_REVIEWED" for r in rows),
                    "unknown_team_reports": sum(r["coverage_status"] == "UNKNOWN" for r in rows),
                    "reported_player_designations": sum(len(r["reported_players"]) for r in rows),
                    "quarantined_source_rows": sum(len(r["quarantined_evidence"]) for r in rows)},
                "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"}
    verify_observation(snapshot)
    return snapshot


def verify_observation(snapshot):
    if (snapshot.get("status") != STATUS or snapshot.get("season") != 2026
        or snapshot.get("safe_for_betting") is not False
        or snapshot.get("betting_status") != "PASS_UNVALIDATED"):
        raise ValueError("Untrusted injury-history observation")
    when = _time(snapshot["observed_at_utc"])
    asof = _time(snapshot["context_asof_utc"])
    captured = _time(snapshot["context_captured_at_utc"])
    if not asof <= captured <= when:
        raise ValueError("Future-sourced injury observation")
    rows = snapshot.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Empty injury observation")
    ids = set()
    matchup = defaultdict(dict)
    for row in rows:
        game_id, team = str(row["game_id"]), row["team"]
        key = (game_id, team)
        if not team or key in ids:
            raise ValueError("Duplicate or empty game/team injury observation")
        ids.add(key)
        if (_time(row["observed_at_utc"]) != when
            or _time(row["kickoff_utc"]) <= when):
            raise ValueError("Postkickoff or mismatched injury observation")
        if (row["coverage_status"] not in COVERAGE
            or row.get("unlisted_players_status") != "UNKNOWN"
            or row.get("diagnosis_verified") is not False
            or row.get("participation_verified") is not False):
            raise ValueError("Unsupported injury-health or coverage inference")
        opponent = row["opponent"]
        if not opponent or opponent == team:
            raise ValueError("Invalid injury opponent")
        matchup[game_id][team] = (opponent, _time(row["kickoff_utc"]))
        names = set()
        for item in row["reported_players"]:
            name = item["player"]
            if not isinstance(name, str) or not 2 <= len(name.strip()) <= 100:
                raise ValueError("Invalid injury player")
            name_key = name.casefold()
            if name_key in names:
                raise ValueError("Duplicate injury player designation")
            names.add(name_key)
            if (item.get("signal_kind") not in KINDS
                or item.get("position") not in POSITIONS
                or item.get("reported_status") not in DESIGNATIONS
                or item.get("observed_at_utc") != row["observed_at_utc"]
                or not _source_url(item.get("source_url"))):
                raise ValueError("Unsupported injury designation provenance")
            if not (_time(item["published_at_utc"]) <= _time(item["captured_at_utc"]) <= asof):
                raise ValueError("Future-sourced injury designation")
        for issue in row["quarantined_evidence"]:
            if not isinstance(issue.get("reason"), str) or not issue["reason"]:
                raise ValueError("Invalid quarantine reason")
            if any(k in issue for k in ("reported_status", "published_at_utc", "captured_at_utc")):
                raise ValueError("Quarantine must not reveal future statuses")
    if any(len(pair) != 2 or any(
        pair.get(opp, (None,))[0] != team or pair[team][1] != pair[opp][1]
        for team, (opp, _) in pair.items()) for pair in matchup.values()):
        raise ValueError("Two-team injury coverage integrity check failed")
    expected = {"game_team_slots": len(rows),
                "verified_team_reports": sum(r["coverage_status"] == "VERIFIED_REPORT_REVIEWED" for r in rows),
                "unknown_team_reports": sum(r["coverage_status"] == "UNKNOWN" for r in rows),
                "reported_player_designations": sum(len(r["reported_players"]) for r in rows),
                "quarantined_source_rows": sum(len(r["quarantined_evidence"]) for r in rows)}
    if snapshot.get("summary") != expected:
        raise ValueError("Injury snapshot summary integrity mismatch")
    return True


def lookup(snapshots, game_id, team, decision_utc, player=None):
    """Read a player/team as reported at decision time; no status carryover.

    A later, newly published AVAILABLE after OUT is a *reported transition*,
    not evidence of recovery. Conflicting same-publication claims are withheld.
    """
    decision = _time(decision_utc)
    observed = []
    for snapshot in snapshots:
        verify_observation(snapshot)
        if _time(snapshot["observed_at_utc"]) > decision:
            continue
        for row in snapshot["rows"]:
            if (str(row["game_id"]) == str(game_id) and row["team"] == team
                and decision < _time(row["kickoff_utc"])):
                observed.append(row)
    if not observed:
        return {"status": "UNKNOWN", "reason": "NO_PREDECISION_OBSERVATION",
                "betting_status": "PASS_UNVALIDATED"}
    observed.sort(key=lambda r: _time(r["observed_at_utc"]))
    latest = observed[-1]
    base = {"asof_utc": latest["observed_at_utc"],
            "coverage_status": latest["coverage_status"],
            "observations_considered": len(observed),
            "betting_status": "PASS_UNVALIDATED"}
    if player is None:
        return {**base, "status": "REPORTED_AVAILABILITY_ONLY",
                "reported_players": latest["reported_players"],
                "unlisted_players_status": "UNKNOWN"}
    key = player.strip().casefold()
    latest_player = next((r for r in latest["reported_players"]
                          if r["player"].casefold() == key), None)
    if any(q["player"].casefold() == key for q in latest["quarantined_evidence"]):
        return {**base, "status": "UNKNOWN", "reason": "CONFLICT_REQUIRES_REVIEW"}
    if latest_player is None:
        return {**base, "status": "UNKNOWN", "reason": "PLAYER_UNLISTED_IN_LATEST_OBSERVATION"}
    appearances = []
    for row in observed:
        p = next((r for r in row["reported_players"]
                  if r["player"].casefold() == key), None)
        if p is not None:
            appearances.append(p)
    changes = []
    for previous, current in zip(appearances, appearances[1:]):
        if previous["reported_status"] == current["reported_status"]:
            continue
        if (_time(current["published_at_utc"]) <= _time(previous["published_at_utc"])
            or _time(current["captured_at_utc"]) < _time(previous["captured_at_utc"])):
            return {**base, "status": "UNKNOWN", "reason": "CONFLICT_REQUIRES_REVIEW"}
        changes.append({"from_reported_status": previous["reported_status"],
                        "to_reported_status": current["reported_status"],
                        "published_at_utc": current["published_at_utc"],
                        "interpretation": "REPORTED_DESIGNATION_CHANGE_ONLY"})
    return {**base, "status": latest_player["reported_status"],
            "player": latest_player["player"], "source": latest_player,
            "reported_transitions": changes,
            "diagnosis_verified": False, "participation_verified": False}


def run(context_path, output_path, now=None):
    context = json.loads(Path(context_path).read_text())
    observed = _time(now or dt.datetime.now(dt.timezone.utc).isoformat())
    result = observe(context, observed)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"]))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.context, args.output)

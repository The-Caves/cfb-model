"""Predecision CFB personnel truth table: game, team, position and source clocks.

This is an *observed evidence* intake, not a medical diagnosis or automatic
starter finder. Missing official reports never imply healthy athletes. It
reconciles the existing official conference injury-history snapshot, the
reviewed university season-OUT registry, and strict game-specific QB review.
No player impact, prop line, or score forecast is trained or altered here.
"""
import argparse
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

from scripts.game_context import parse_time
from scripts.injury_history import observe as injury_observe
from scripts.official_longterm_qb_absences import apply as add_longterm_out
from scripts.qb_expected_starters import STATUS as QB_EXPECTED

STATUS = "CFB_PREGAME_PERSONNEL_EVIDENCE_BOARD_V1"
UNAVAILABLE = {"OUT", "OUT_FIRST_HALF", "SUSPENDED", "DOUBTFUL"}
UNCERTAIN = {"QUESTIONABLE", "LIMITED", "GAME_TIME_DECISION"}
SUPPORTED = UNAVAILABLE | UNCERTAIN | {"AVAILABLE", "PROBABLE", "UNKNOWN"}


def key(name):
    return re.sub(r"[^a-z0-9]", "", str(name or "").casefold())


def build(context, expected, registry, observed_at_utc):
    now = parse_time(observed_at_utc)
    if (expected.get("status") != QB_EXPECTED or
        expected.get("season") != 2026 or
        expected.get("betting_status") != "PASS_UNVALIDATED" or
        expected.get("model_promoted") is not False or
        context.get("betting_status", "PASS_UNVALIDATED") != "PASS_UNVALIDATED"):
        raise ValueError("Untrusted CFB personnel input")
    if not (parse_time(context["asof_utc"]) <=
            parse_time(context["captured_at_utc"]) <= now and
            parse_time(expected["observed_at_utc"]) <= now):
        raise ValueError("Pregame personnel input sourced after decision")
    injuries = injury_observe(context, now.isoformat())
    future = {}
    for g in context["games"]:
        gid = str(g["game_id"])
        if gid in future:
            raise ValueError("Duplicate context game ID")
        if parse_time(g["kickoff_utc"]) <= now:
            continue
        future[gid] = g
    qb_slots = {}
    for row in expected.get("games", []):
        gid, team = str(row["game_id"]), row["team"]
        slot = (gid, team)
        if slot in qb_slots:
            raise ValueError("Duplicate expected QB game/team")
        if parse_time(row["observed_at_utc"]) > now:
            raise ValueError("Future expected QB observation")
        g = future.get(gid)
        if g is None:
            # Games can begin during sequential GitHub pipeline steps. Never
            # rewrite an earlier frozen projection or reclassify after kickoff.
            if parse_time(row["kickoff_utc"]) <= now:
                continue
            raise ValueError("Expected QB is not a known future game")
        if (team not in (g["home"], g["away"]) or
            row["opponent"] != (g["away"] if team == g["home"] else g["home"]) or
            parse_time(row["kickoff_utc"]) != parse_time(g["kickoff_utc"])):
            raise ValueError("QB and official injury fixture identity mismatch")
        qb_slots[slot] = row

    # The existing source validator applies per-player first-use times,
    # university hostname checks and explicit source review requirements.
    source_board = {"schema_version": 2,
                    "betting_status": "PASS_UNVALIDATED", "games": []}
    for gid, g in sorted(future.items()):
        a = {"game_id": gid, "home_team": g["home"], "away_team": g["away"],
             "kickoff_utc": g["kickoff_utc"]}
        for side in ("home", "away"):
            qb = qb_slots.get((gid, g[side]), {})
            a["qb_" + side] = {
                "status": "CONFIRMED_OFFICIAL" if qb.get("is_confirmed_starter") is True
                          else "UNKNOWN",
                "player": qb.get("starter") if qb.get("is_confirmed_starter") is True else None}
        source_board["games"].append(a)
    source_board = add_longterm_out(source_board, registry, now.isoformat())
    outages = {str(g["game_id"]): g for g in source_board["games"]}
    injury_rows = {(str(x["game_id"]), x["team"]): x for x in injuries["rows"]}
    if set(injury_rows) != {(gid, g[side]) for gid, g in future.items()
                           for side in ("home", "away")}:
        raise ValueError("Injury snapshot and upcoming fixtures disagree")
    rows = []
    counts = Counter()
    positions = Counter()
    for gid, g in sorted(future.items(), key=lambda pair: (pair[1]["kickoff_utc"], pair[0])):
        for side in ("home", "away"):
            team, opponent = g[side], g["away" if side == "home" else "home"]
            injury = injury_rows[(gid, team)]
            q = qb_slots.get((gid, team))
            by_player = {}
            for item in injury["reported_players"]:
                who = key(item["player"])
                if not who or who in by_player:
                    raise ValueError("Duplicate official player designation")
                status = item["reported_status"]
                if status not in SUPPORTED:
                    raise ValueError("Unsupported official player designation")
                by_player[who] = {
                    "player": item["player"], "position": item["position"],
                    "status": status, "source_type": "OFFICIAL_GAME_AVAILABILITY",
                    "published_at_utc": item["published_at_utc"],
                    "captured_at_utc": item["captured_at_utc"],
                    "source_url": item["source_url"],
                    "participation_confirmed": False}
            reviewed = outages[gid].get("official_longterm_qb_absences_" + side, [])
            for absence in reviewed:
                who = key(absence["player"])
                prior = by_player.get(who)
                if prior and prior["position"] != "QB":
                    raise ValueError("Cross-source player position conflict")
                if prior and prior["status"] not in UNAVAILABLE:
                    prior["status"] = "CONFLICT_REVIEW"
                    prior["source_type"] = "OFFICIAL_SOURCE_CONFLICT"
                    prior["conflicting_university_source_url"] = absence["source_url"]
                elif prior:
                    prior["university_season_out_source_url"] = absence["source_url"]
                else:
                    by_player[who] = {
                        "player": absence["player"], "position": "QB",
                        "status": "OUT", "source_type": "OFFICIAL_UNIVERSITY_SEASON_OUT",
                        "published_at_utc": absence["published_date"],
                        "captured_at_utc": absence["first_eligible_at_utc"],
                        "source_url": absence["source_url"],
                        "participation_confirmed": False}
            candidate = q.get("starter") if q else None
            confirmed = bool(q and q.get("is_confirmed_starter") is True)
            # An accepted starter must come from the context's separately
            # reviewed, exact-game official claim, not a passer or chart.
            if confirmed:
                claim = (g.get("verified_qb_starters") or {}).get(team)
                if not isinstance(claim, dict) or key(claim.get("player")) != key(candidate):
                    raise ValueError("Confirmed QB not corroborated by reviewed game claim")
                clock = [parse_time(claim[x]) for x in
                         ("published_at_utc", "captured_at_utc", "reviewed_at_utc")]
                if not clock[0] <= clock[1] <= clock[2] <= parse_time(context["asof_utc"]):
                    raise ValueError("Confirmed QB source reviewed after context cutoff")
            player_status = by_player.get(key(candidate), {}).get("status") if candidate else None
            conflict = player_status in UNAVAILABLE or player_status == "CONFLICT_REVIEW"
            if conflict:
                counts["qb_starter_evidence_conflicts"] += 1
            if confirmed and not conflict:
                starter_evidence = "CONFIRMED_REVIEWED_THIS_GAME"
            elif conflict:
                starter_evidence = "CONFLICT_REVIEW"
            elif candidate:
                starter_evidence = "PROJECTED_NOT_CONFIRMED"
            else:
                starter_evidence = "UNKNOWN"
            observed_players = sorted(by_player.values(),
                                      key=lambda a: (a["position"], key(a["player"])))
            for item in observed_players:
                positions[(item["position"], item["status"])] += 1
            counts["game_team_slots"] += 1
            counts["official_game_report_slots"] += injury["coverage_status"] == "VERIFIED_REPORT_REVIEWED"
            counts["unknown_game_report_slots"] += injury["coverage_status"] == "UNKNOWN"
            counts["confirmed_qb_starter_slots"] += starter_evidence == "CONFIRMED_REVIEWED_THIS_GAME"
            counts["projected_unconfirmed_qb_slots"] += starter_evidence == "PROJECTED_NOT_CONFIRMED"
            counts["unknown_or_conflicted_qb_slots"] += starter_evidence in ("UNKNOWN", "CONFLICT_REVIEW")
            counts["official_player_designations"] += len(observed_players)
            counts["quarantined_rows"] += len(injury["quarantined_evidence"])
            rows.append({
                "game_id": gid, "team": team, "opponent": opponent, "side": side,
                "kickoff_utc": g["kickoff_utc"], "observed_at_utc": now.isoformat(),
                "report_coverage": injury["coverage_status"],
                "unlisted_player_status": "UNKNOWN",
                # Only directly reviewed THIS-game starter evidence may
                # populate the model-eligible starter field. The separate
                # historical/chart candidate remains a scenario, never a
                # factual answer to "who starts?".
                "current_qb_candidate": candidate if confirmed and not conflict else None,
                "historical_or_chart_qb_scenario": candidate if
                    starter_evidence == "PROJECTED_NOT_CONFIRMED" else None,
                "current_qb_evidence": starter_evidence,
                "confirmed_qb_starter": bool(confirmed and not conflict),
                "starter_eligible_for_model_input": bool(confirmed and not conflict),
                "qb_candidate_not_participation_confirmation": True,
                "players": observed_players,
                "quarantined_evidence": injury["quarantined_evidence"],
                "no_inferred_healthy_players": True,
                "injury_points_estimated": False})
    return {
        "status": STATUS, "season": 2026,
        "observed_at_utc": now.isoformat(),
        "source_context_asof_utc": context["asof_utc"],
        "source_expected_qb_observed_at_utc": expected["observed_at_utc"],
        "summary": dict(counts),
        "position_status_counts": [
            {"position": p, "status": s, "reported_players": n}
            for (p, s), n in sorted(positions.items())],
        "games": rows, "safe_for_betting": False,
        "betting_status": "PASS_UNVALIDATED",
        "model_promoted": False, "original_scores_changed": False,
        "unconfirmed_starter_inferred": False}


def run(context_path, expected_path, registry_path, output_path, now=None):
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    result = build(context, expected, registry,
                   now or dt.datetime.now(dt.timezone.utc).isoformat())
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(result["summary"], sort_keys=True))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--context", required=True)
    p.add_argument("--expected", required=True)
    p.add_argument("--registry", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    run(args.context, args.expected, args.registry, args.output)

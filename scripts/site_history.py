"""Read immutable pregame displayed V04 selections and independently observed finals.

No hindsight scoring, inferred missing market quotes, or post-kickoff forecast recompute.
The source state is the context-state branch checked out read-only by the site workflow.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time

ET = ZoneInfo("America/New_York")
ARCHIVE_STATUS = "IMMUTABLE_DISPLAYED_RESEARCH_MARKET_SNAPSHOT"
FINAL_STATUS = "ASOF_OUTCOME_ARCHIVE_RESEARCH_ONLY"
STATUS = "ARCHIVED_PREKICKOFF_V04_WITH_INDEPENDENT_FINAL"
INDEX = "research_2026/site_board_snapshots/index.json"
FINALS = "research_2026/outcome_index.json"


def _number(value, lo, hi):
    return type(value) in (float, int) and math.isfinite(value) and lo <= value <= hi


def _load(root, rel):
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts or not str(path).startswith(
            "research_2026/site_board_snapshots/") or path.suffixes != [".json", ".gz"]:
        raise ValueError("Invalid archived CFB pregame path")
    raw = gzip.decompress((root / path).read_bytes())
    return json.loads(raw)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     default=str).encode()).hexdigest()


def _pick_state(pred, actual):
    if pred is None or actual is None:
        return "UNAVAILABLE"
    if pred == "PASS":
        return "PASS"
    if actual == "PUSH":
        return "PUSH"
    if pred == actual:
        return "WIN"
    if pred in ("HOME", "AWAY", "OVER", "UNDER") and actual in ("HOME", "AWAY", "OVER", "UNDER"):
        return "LOSS"
    return "UNAVAILABLE"


def _grade(row, final, is_v04):
    if not final:
        return {"su": "PENDING", "ats": "PENDING", "ou": "PENDING"}
    actual_margin = final["home_score"] - final["away_score"]
    projected_margin = row["v04_direct_home_margin"] if is_v04 else None
    winner = ("HOME" if projected_margin > 0 else "AWAY" if projected_margin < 0
              else None) if projected_margin is not None else None
    real_winner = "HOME" if actual_margin > 0 else "AWAY" if actual_margin < 0 else "PUSH"
    spread = row.get("market_home_spread")
    total = row.get("market_total")
    covered = ("HOME" if actual_margin + spread > 0 else
               "AWAY" if actual_margin + spread < 0 else "PUSH") if _number(spread, -80, 80) else None
    real_total = final["home_score"] + final["away_score"]
    ou = ("OVER" if real_total > total else "UNDER" if real_total < total else "PUSH"
          ) if _number(total, 1, 150) else None
    return {
        "su": _pick_state(winner, real_winner),
        "ats": _pick_state(row.get("v04_research_ats_side") if is_v04 else None, covered),
        "ou": _pick_state(row.get("v04_research_ou_side") if is_v04 else None, ou),
    }


def build(root, now=None, days=21):
    root = Path(root)
    now = parse_time(now or dt.datetime.now(dt.timezone.utc).isoformat())
    if days < 1 or days > 90:
        raise ValueError("Historical site lookback exceeds the supported range")
    index = json.loads((root / INDEX).read_text())
    finals = json.loads((root / FINALS).read_text())
    if (index.get("status") != ARCHIVE_STATUS or index.get("schema_version") != 1
        or finals.get("status") != FINAL_STATUS or finals.get("season") != 2026
        or finals.get("safe_for_betting") is not False
        or not isinstance(finals.get("games"), dict)
        or not isinstance(index.get("runs"), list)):
        raise ValueError("Untrusted historical performance evidence")
    cutoff = now - dt.timedelta(days=days)
    selected = {}
    inspected = 0
    for receipt in index["runs"]:
        captured = parse_time(receipt["capture_utc"])
        if captured > now or captured < cutoff - dt.timedelta(days=7):
            continue
        snapshot = _load(root, receipt["path"])
        if _digest(snapshot) != receipt["sha256"]:
            raise ValueError("Historical pregame snapshot digest mismatch")
        if (snapshot.get("status") != ARCHIVE_STATUS
            or snapshot.get("betting_status") != "PASS_UNVALIDATED"
            or snapshot.get("capture_utc") != receipt["capture_utc"]
            or str(snapshot.get("dashboard_run_id")) != str(receipt["run_id"])):
            raise ValueError("Tampered pregame snapshot")
        inspected += 1
        for row in snapshot.get("rows", []):
            kickoff = parse_time(row["kickoff_utc"])
            if (not cutoff <= kickoff <= now or captured >= kickoff
                or str(row.get("game_id", "")) == ""
                or row.get("home") == row.get("away")):
                continue
            gid = str(row["game_id"])
            has_v04 = (row.get("v04_research_not_promoted") is True
                       and row.get("home_bias_quarantined") is True
                       and row.get("v04_direct_source_no_v03_total_reuse") is True
                       and all(_number(row.get(k), -150, 160) for k in
                               ("v04_direct_home_points", "v04_direct_away_points",
                                "v04_direct_home_margin", "v04_direct_total_points"))
                       and abs(row["v04_direct_home_points"] -
                               row["v04_direct_away_points"] -
                               row["v04_direct_home_margin"]) < .05
                       and abs(row["v04_direct_home_points"] +
                               row["v04_direct_away_points"] -
                               row["v04_direct_total_points"]) < .05)
            rank = (int(has_v04), captured)
            old = selected.get(gid)
            if old and old["rank"] >= rank:
                continue
            selected[gid] = {"row": row, "rank": rank, "capture": captured,
                             "is_v04": has_v04}
    games = []
    for gid, candidate in selected.items():
        row = candidate["row"]
        kickoff = parse_time(row["kickoff_utc"])
        record = finals["games"].get(gid)
        final = None
        if record:
            final_kick = parse_time(record["kickoff_utc"])
            final_time = parse_time(record["outcome_known_at_utc"])
            if (str(record.get("game_id")) == gid and record.get("home") == row["home"]
                and record.get("away") == row["away"]
                and abs((final_kick - kickoff).total_seconds()) <= 900
                and kickoff < final_time <= now
                and type(record.get("home_score")) is int and 0 <= record["home_score"] <= 200
                and type(record.get("away_score")) is int and 0 <= record["away_score"] <= 200):
                final = {"home_score": record["home_score"],
                         "away_score": record["away_score"],
                         "outcome_known_at_utc": record["outcome_known_at_utc"]}
        is_v04 = candidate["is_v04"]
        has_market = (row.get("market_provider") and row.get("market_observed_utc")
                      and parse_time(row["market_observed_utc"]) < kickoff
                      and parse_time(row["market_observed_utc"]) <= candidate["capture"])
        market_spread = row.get("market_home_spread") if has_market and _number(
            row.get("market_home_spread"), -79.5, 79.5) else None
        market_total = row.get("market_total") if has_market and _number(
            row.get("market_total"), 1, 149.5) else None
        def _money(k):
            v = row.get(k)
            return v if type(v) is int and 100 <= abs(v) <= 10000 and has_market else None
        games.append({
            "game_id": gid, "home_team": row["home"], "away_team": row["away"],
            "kickoff_utc": row["kickoff_utc"], "archive_captured_utc": candidate["capture"].isoformat(),
            "forecast_observed_utc": row.get("frozen_forecast_observed_utc"),
            "archived_model": "V04" if is_v04 else "V03_QUARANTINED",
            "home_bias_quarantined": row.get("home_bias_quarantined") is True,
            "model_home_points": row.get("v04_direct_home_points") if is_v04 else None,
            "model_away_points": row.get("v04_direct_away_points") if is_v04 else None,
            "model_home_margin": row.get("v04_direct_home_margin") if is_v04 else None,
            "model_total": row.get("v04_direct_total_points") if is_v04 else None,
            "market_home_spread": market_spread,
            "market_total": market_total,
            "market_provider": row.get("market_provider") if has_market else None,
            "market_observed_utc": row.get("market_observed_utc") if has_market else None,
            "market_home_moneyline": _money("market_home_moneyline"),
            "market_away_moneyline": _money("market_away_moneyline"),
            "ats_pick": row.get("v04_research_ats_side") if is_v04 else None,
            "ou_pick": row.get("v04_research_ou_side") if is_v04 else None,
            "final": final, "outcomes": _grade(
                dict(row, market_home_spread=market_spread, market_total=market_total),
                final, is_v04),
            "historical_market_quote_not_in_play": True,
            "pregame_snapshot_verified": True,
        })
    games.sort(key=lambda g: (g["kickoff_utc"], g["game_id"]))
    return {
        "status": STATUS, "betting_status": "PASS_UNVALIDATED",
        "generated_at_utc": now.isoformat(),
        "history_games": games,
        "summary": {"games": len(games), "verified_finals": sum(bool(g["final"]) for g in games),
                    "model_v04_games": sum(g["archived_model"] == "V04" for g in games),
                    "archived_snapshots_checked": inspected},
        "source_note": "Immutable pre-kickoff site receipts and independently observed final archive; no postgame model refit",
    }


def run(root, dashboard, now=None):
    path = Path(dashboard)
    board = json.loads(path.read_text())
    if board.get("schema_version") != 2 or board.get("betting_status") != "PASS_UNVALIDATED":
        raise ValueError("Unexpected CFB board")
    forecast_before = json.dumps([g.get("v04_direct_scores") for g in board["games"]], sort_keys=True)
    grade_before = json.dumps(board.get("prospective_records"), sort_keys=True)
    history = build(root, now)
    board["history_games"] = history["history_games"]
    board["history_display"] = {**history["summary"], "status": STATUS,
                                "generated_at_utc": history["generated_at_utc"],
                                "source_note": history["source_note"],
                                "pre_kickoff_only": True}
    assert json.dumps([g.get("v04_direct_scores") for g in board["games"]], sort_keys=True) == forecast_before
    assert json.dumps(board.get("prospective_records"), sort_keys=True) == grade_before
    path.write_text(json.dumps(board, indent=2, allow_nan=False) + "\n")
    print(json.dumps(board["history_display"], sort_keys=True))
    return board


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--archive-root", required=True)
    p.add_argument("--dashboard", required=True)
    a = p.parse_args()
    run(a.archive_root, a.dashboard)

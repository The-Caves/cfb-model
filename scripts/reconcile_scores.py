"""Audit unverified v0.9 score history against fetched ESPN completed games.

This tool does NOT silently replace or import unmatched archived results. A
name mapping is explicit and reviewable, and every date/side/score is checked.
Missing archived matches never become training inputs. Live ESPN game IDs are
used for canonical records, while score sources stay traceable.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

FIELDS = ["date", "archive_away", "archive_home", "archive_away_score", "archive_home_score",
          "live_game_id", "live_away", "live_home", "live_away_score", "live_home_score", "status", "reason"]


def load_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def load_aliases(path):
    mapping = {}
    seen = set()
    for row in load_csv(path):
        old = row["archived_team"].strip()
        new = row["espn_display_name"].strip()
        if not old or not new or old in mapping or new in seen:
            raise ValueError(f"Invalid or duplicate alias mapping: {old!r} => {new!r}")
        mapping[old] = new
        seen.add(new)
    return mapping


def game_key(record):
    return record["date"], record["away"], record["home"]


def audit(archive, live, aliases):
    if not archive or not live:
        raise ValueError("Reconciliation requires both a nonempty archive and live dataset")
    normalized_archive = set()
    seen_live_ids = set()
    by_key = defaultdict(list)
    for game in live:
        gid = game.get("game_id", "")
        if not gid or gid in seen_live_ids:
            raise ValueError(f"Missing or duplicate live game ID: {gid!r}")
        seen_live_ids.add(gid)
        by_key[game_key(game)].append(game)
    rows = []
    claimed_live_ids = set()
    for old in archive:
        oldkey = game_key(old)
        if oldkey in normalized_archive:
            raise ValueError(f"Duplicate archived game: {oldkey!r}")
        normalized_archive.add(oldkey)
        missing_names = [x for x in (old["away"], old["home"]) if x not in aliases]
        candidates = (by_key.get((old["date"], aliases[old["away"]], aliases[old["home"]]), [])
                      if not missing_names else [])
        row = {
            "date": old["date"], "archive_away": old["away"], "archive_home": old["home"],
            "archive_away_score": old.get("away_score", ""),
            "archive_home_score": old.get("home_score", ""),
            "live_game_id": "", "live_away": "", "live_home": "",
            "live_away_score": "", "live_home_score": "", "status": "", "reason": ""
        }
        if missing_names:
            row.update(status="MISSING_TEAM_ALIAS", reason="/".join(missing_names))
        elif len(candidates) == 0:
            row.update(status="ARCHIVE_UNMATCHED", reason="No ESPN final with identical date, home and away")
        elif len(candidates) > 1:
            row.update(status="AMBIGUOUS_LIVE_MATCH", reason=f"{len(candidates)} candidates")
        else:
            found = candidates[0]
            row.update(live_game_id=found["game_id"], live_away=found["away"],
                       live_home=found["home"], live_away_score=found["away_score"],
                       live_home_score=found["home_score"])
            try:
                archived_scores = int(old["away_score"]), int(old["home_score"])
                live_scores = int(found["away_score"]), int(found["home_score"])
                if archived_scores == live_scores:
                    row["status"] = "SCORE_MATCH"
                    row["reason"] = "Game and final scores agree; historical as-of availability not established"
                else:
                    row["status"] = "SCORE_MISMATCH"
                    row["reason"] = "Final scores disagree; archive quarantined"
            except (ValueError, TypeError, KeyError):
                row.update(status="INVALID_SCORE", reason="Non-integer score")
            claimed_live_ids.add(found["game_id"])
        rows.append(row)
    for found in live:
        if found["game_id"] in claimed_live_ids:
            continue
        rows.append({"date": found["date"], "archive_away": "", "archive_home": "",
                     "archive_away_score": "", "archive_home_score": "", "live_game_id": found["game_id"],
                     "live_away": found["away"], "live_home": found["home"],
                     "live_away_score": found["away_score"], "live_home_score": found["home_score"],
                     "status": "LIVE_ONLY", "reason": "No validated corresponding archived row"})
    counts = dict(sorted(Counter(r["status"] for r in rows).items()))
    problem_states = ("SCORE_MISMATCH", "INVALID_SCORE", "MISSING_TEAM_ALIAS", "AMBIGUOUS_LIVE_MATCH", "ARCHIVE_UNMATCHED")
    has_problems = any(counts.get(name, 0) for name in problem_states)
    summary = {"archive_game_count": len(archive), "live_game_count": len(live),
               "counts": counts, "status": "REVIEW_REQUIRED" if has_problems else "SCORES_MATCH_FOR_ARCHIVED_ROWS",
               "archive_training_cleared": False,
               "reason": "Historical as-of/provenance unresolved; unmatched archive excluded and advanced pregame data unavailable",
               "audit_definition": "Exact date, away, home after explicit alias mapping; final scores compared",
               "note": "LIVE_ONLY includes games outside the archived 138-team registry (including FCS). No matches inferred by scores alone."}
    return rows, summary


def run(archive, live, aliases, output):
    archived = load_csv(archive)
    fetched = load_csv(live)
    name_map = load_aliases(aliases)
    result, summary = audit(archived, fetched, name_map)
    summary["audited_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    summary["archive_sha256"] = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    summary["live_sha256"] = hashlib.sha256(Path(live).read_bytes()).hexdigest()
    summary["aliases_sha256"] = hashlib.sha256(Path(aliases).read_bytes()).hexdigest()
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "reconciliation_rows.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(result)
    (out / "reconciliation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", default="data/archive/2026_v09_scores_unverified.csv")
    parser.add_argument("--live", default="data/games_2026.csv")
    parser.add_argument("--aliases", default="data/archive/2026_team_aliases.csv")
    parser.add_argument("--output", default="data/reconciliation")
    parser.add_argument("--fail-on-unresolved", action="store_true")
    args = parser.parse_args()
    report = run(args.archive, args.live, args.aliases, args.output)
    if args.fail_on_unresolved and report["status"] == "REVIEW_REQUIRED":
        raise SystemExit(2)

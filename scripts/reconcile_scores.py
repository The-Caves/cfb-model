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
    known_archive = set()
    seen_live_ids = set()
    by_key = defaultdict(list)
    by_pair = defaultdict(list)
    for game in live:
        gid = game.get("game_id", "")
        if not gid or gid in seen_live_ids:
            raise ValueError(f"Missing or duplicate live game ID: {gid!r}")
        seen_live_ids.add(gid)
        by_key[game_key(game)].append(game)
        by_pair[frozenset((game["away"], game["home"]))].append(game)

    def neutral(value):
        return str(value).strip().lower() in ("true", "1", "yes")

    rows = []
    claimed_live_ids = set()
    for old in archive:
        oldkey = game_key(old)
        if oldkey in known_archive:
            raise ValueError(f"Duplicate archived game: {oldkey!r}")
        known_archive.add(oldkey)
        missing_names = [name for name in (old["away"], old["home"]) if name not in aliases]
        row = {
            "date": old["date"], "archive_away": old["away"], "archive_home": old["home"],
            "archive_away_score": old.get("away_score", ""),
            "archive_home_score": old.get("home_score", ""),
            "live_game_id": "", "live_away": "", "live_home": "",
            "live_away_score": "", "live_home_score": "", "status": "", "reason": ""
        }
        if missing_names:
            row.update(status="MISSING_TEAM_ALIAS", reason="/".join(missing_names))
            rows.append(row)
            continue

        away = aliases[old["away"]]
        home = aliases[old["home"]]
        exact = by_key.get((old["date"], away, home), [])
        if len(exact) > 1:
            row.update(status="AMBIGUOUS_LIVE_MATCH", reason=f"{len(exact)} identical live matchups")
            rows.append(row)
            continue

        matches = exact
        relationship = "EXACT"
        if not matches:
            pair = by_pair[frozenset((away, home))]
            same_sides_nearby = [game for game in pair if game["away"] == away and game["home"] == home
                                 and abs((dt.date.fromisoformat(game["date"]) - dt.date.fromisoformat(old["date"])).days) <= 1]
            if same_sides_nearby:
                relationship = "DATE_SHIFT"
                matches = same_sides_nearby
            else:
                reversed_nearby = [game for game in pair if game["away"] == home and game["home"] == away
                                   and abs((dt.date.fromisoformat(game["date"]) - dt.date.fromisoformat(old["date"])).days) <= 1]
                if reversed_nearby:
                    relationship = "REVERSED_SIDES"
                    matches = reversed_nearby
        if len(matches) > 1:
            row.update(status="AMBIGUOUS_LIVE_MATCH", reason=f"{len(matches)} {relationship} candidates")
            rows.append(row)
            continue
        if not matches:
            row.update(status="ARCHIVE_UNMATCHED", reason="No matching ESPN teams with matching sides and date ±1")
            rows.append(row)
            continue

        found = matches[0]
        claimed_live_ids.add(found["game_id"])
        row.update(live_game_id=found["game_id"], live_away=found["away"],
                   live_home=found["home"], live_away_score=found["away_score"],
                   live_home_score=found["home_score"])
        try:
            archived_scores = (int(old["away_score"]), int(old["home_score"]))
            live_scores = (int(found["away_score"]), int(found["home_score"]))
        except (ValueError, TypeError, KeyError):
            row.update(status="INVALID_SCORE", reason="Non-integer score")
            rows.append(row)
            continue
        neutral_mismatch = neutral(old.get("neutral", False)) != neutral(found.get("neutral", False))
        if relationship == "EXACT":
            if archived_scores != live_scores:
                row.update(status="SCORE_MISMATCH", reason="Same game and sides, final scores differ")
            elif neutral_mismatch:
                row.update(status="NEUTRAL_SITE_MISMATCH", reason="Game and scores match but archived neutral flag differs")
            else:
                row.update(status="SCORE_MATCH", reason="Game/date/sides/scores/neutral agree; historical as-of still unverified")
        elif relationship == "DATE_SHIFT":
            row.update(status="DATE_SHIFT_MATCH" if archived_scores == live_scores and not neutral_mismatch
                       else "DATE_SHIFT_CONFLICT",
                       reason=f"Archived local date {old['date']}; ESPN ET date {found['date']}; "
                              f"scores_equal={archived_scores == live_scores}; neutral_equal={not neutral_mismatch}")
        else:
            # After swapping sides, team-correct scores must swap as well.
            team_scores_agree = archived_scores == (live_scores[1], live_scores[0])
            row.update(status="HOME_AWAY_REVERSED" if team_scores_agree and not neutral_mismatch
                       else "HOME_AWAY_SCORE_CONFLICT",
                       reason=f"ESPN assigns opposite teams to home/away; team_scores_equal={team_scores_agree}; "
                              f"neutral_equal={not neutral_mismatch}; ESPN_ET_date={found['date']}")
        rows.append(row)
    for found in live:
        if found["game_id"] in claimed_live_ids:
            continue
        rows.append({"date": found["date"], "archive_away": "", "archive_home": "",
                     "archive_away_score": "", "archive_home_score": "", "live_game_id": found["game_id"],
                     "live_away": found["away"], "live_home": found["home"],
                     "live_away_score": found["away_score"], "live_home_score": found["home_score"],
                     "status": "LIVE_ONLY", "reason": "No matched corresponding archived row"})
    counts = dict(sorted(Counter(row["status"] for row in rows).items()))
    status = "SCORES_MATCH_FOR_ARCHIVED_ROWS" if (counts.get("SCORE_MATCH", 0) == len(archive)) else "REVIEW_REQUIRED"
    summary = {
        "archive_game_count": len(archive), "live_game_count": len(live),
        "counts": counts, "status": status, "archive_training_cleared": False,
        "reason": "Historical as-of/provenance unresolved; conflicting archive entries quarantined",
        "audit_definition": "Explicit school aliases, Eastern Time kickoff date, home/away and final scores plus neutral-site flag",
        "note": "A one-day date shift or reversed home/away is classified, never silently treated as a verified game. Live-only can include FCS."
    }
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

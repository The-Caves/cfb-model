"""Observed per-game passing/receiving box-stat budget reconciliation.

A matched per-game completion/yard total is a quality-control indicator,
NOT proof all eligible players (including DNPs or zero-stat categories) appear.
Never use a retrospectively published season box to backfill a pregame role.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from scripts.player_prop_history import STATUS as HISTORY

STATUS="PLAYER_GAME_TEAM_STAT_BUDGET_AUDIT_RESEARCH_ONLY"

def audit(snapshot):
    if (snapshot.get("status")!=HISTORY or
        snapshot.get("retrospective_first_publication_authenticated") is not False or
        snapshot.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Untrusted player box history")
    groups=defaultdict(list);seen=set()
    for row in snapshot.get("rows",[]):
        if row.get("source_status")!="RETROSPECTIVE_REVISED_PLAYER_BOX_ONLY":
            raise ValueError("Unreviewed historical player category")
        key=(str(row["game_id"]),str(row["team_id"]),str(row["player_id"]))
        if key in seen:
            raise ValueError("Duplicate game/team/player box row")
        seen.add(key)
        groups[(key[0],key[1])].append(row)
    rows=[]
    for (gid,team),players in sorted(groups.items()):
        def aggregate(field):
            vals=[p["values"].get(field) for p in players]
            known=[x for x in vals if x is not None]
            if not known:return None
            if any(type(x) is not int for x in known):
                raise ValueError("Noninteger recorded player box stat")
            return sum(known)
        passing_attempts=aggregate("passing_attempts")
        completions=aggregate("passing_completions")
        passing_yards=aggregate("passing_yards")
        receptions=aggregate("receptions")
        receiving_yards=aggregate("receiving_yards")
        rush_attempts=aggregate("rushing_attempts")
        recorded_pass_catch=(completions is not None and receptions is not None)
        recorded_pass_yards=(passing_yards is not None and receiving_yards is not None)
        if passing_attempts is not None and completions is not None and completions>passing_attempts:
            raise ValueError("Player box completions exceed attempts")
        rows.append({
            "game_id":gid,"team_id":team,
            "observed_player_ids":len(players),
            "reported_passing_attempts":passing_attempts,
            "reported_passing_completions":completions,
            "reported_receiving_catches":receptions,
            "reported_passing_yards":passing_yards,
            "reported_receiving_yards":receiving_yards,
            "reported_rushing_attempts":rush_attempts,
            "completion_minus_receptions":completions-receptions if recorded_pass_catch else None,
            "passing_minus_receiving_yards":passing_yards-receiving_yards if recorded_pass_yards else None,
            "observed_completion_reception_exact_match":completions==receptions if recorded_pass_catch else None,
            "observed_passing_receiving_yard_exact_match":passing_yards==receiving_yards if recorded_pass_yards else None,
            "all_player_participation_verified":False,
            "season_pregame_roster_coverage_verified":False,
        })
    checked_catches=[r for r in rows if r["observed_completion_reception_exact_match"] is not None]
    checked_yards=[r for r in rows if r["observed_passing_receiving_yard_exact_match"] is not None]
    return {"status":STATUS,"season":2026,
        "source_observed_at_utc":snapshot["observed_at_utc"],
        "summary":{
            "observed_team_game_slots":len(rows),
            "slots_with_both_completion_reception_categories":len(checked_catches),
            "slots_completion_reception_reconcile":sum(
                r["observed_completion_reception_exact_match"] for r in checked_catches),
            "slots_with_both_pass_receiving_yard_categories":len(checked_yards),
            "slots_passing_receiving_yards_reconcile":sum(
                r["observed_passing_receiving_yard_exact_match"] for r in checked_yards),
            "slots_with_reported_rushing_attempts":sum(
                r["reported_rushing_attempts"] is not None for r in rows),
            "all_players_participation_verified":0,
            "historical_point_in_time_verified":False,
        },
        "per_team_game":rows,
        "pass_yards_and_receptions_reconciled_is_not_complete_player_list":True,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

def run(input,output):
    report=audit(json.loads(Path(input).read_text(encoding="utf-8")))
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(report["summary"]))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    args=p.parse_args();run(args.input,args.output)

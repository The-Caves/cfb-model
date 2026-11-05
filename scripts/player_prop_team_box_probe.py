"""Low-cost read-only live probe of ESPN-derived team workload data.

It emits a source-coverage receipt, not a player pick, and never writes to
context-state or the website. Explicit original-publication caveat retained.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time
from scripts.nextgen_source_readiness import fetch_asset
from scripts.player_prop_team_budget import prepare
from scripts.player_prop_team_box_source import (
    BOX_URL,DRIVES_URL,SCHEDULE_URL,BOX_COLS,DRIVE_COLS,SCHED_COLS,
    _load,assemble)

ET=ZoneInfo("America/New_York")
STATUS="SOURCE_OBSERVED_TEAM_WORKLOAD_COVERAGE_PROBE_ONLY"


def probe(at,fetcher=fetch_asset,max_games=12):
    now=parse_time(at)
    box,boxsha=_load(BOX_URL,BOX_COLS,fetcher)
    drives,drivesha=_load(DRIVES_URL,DRIVE_COLS,fetcher)
    schedule,schedulesha=_load(SCHEDULE_URL,SCHED_COLS,fetcher)
    future=[]
    for g in schedule:
        if (int(g.get("season") or 0)!=2026 or
            g.get("completed") is not False or
            g.get("fbs_participant") is not True or
            g.get("start_time_tbd") is not False):
            continue
        try:kick=parse_time(g["start_date"])
        except (KeyError,ValueError,TypeError):continue
        if kick<=now or not g.get("home_team") or not g.get("away_team"):
            continue
        future.append((kick,g))
    future.sort(key=lambda v:(v[0],str(v[1]["game_id"])))
    report=[]
    for kick,g in future[:max_games]:
        target={
            "game_id":str(g["game_id"]),
            "date":kick.astimezone(ET).date().isoformat(),
            "kickoff_utc":kick.isoformat(),
            "home":g["home_team"],"away":g["away_team"],
            "team_ids":{"home":str(g["home_id"]),"away":str(g["away_id"])}}
        bundle,possessions,summary=assemble(box,drives,schedule,target,at)
        byside,status=prepare(bundle,target,possessions["rows"],at)
        report.append({
            "game_id":target["game_id"],"home":target["home"],
            "away":target["away"],"kickoff_utc":target["kickoff_utc"],
            "historical_team_attempt_rows":summary["historical_team_rows"],
            "historical_paired_game_ids":summary["matched_historical_games_for_target"],
            "team_budget_readiness":status,
            "qualified_both_sides":byside is not None,
            "player_participation_confirmed":False})
    return {"status":STATUS,"observed_at_utc":now.isoformat(),
        "upcoming_games_examined":len(report),
        "matched_both_side_history":sum(r["qualified_both_sides"] for r in report),
        "source_sha256":{"team_box":boxsha,"drives":drivesha,"schedule":schedulesha},
        "games":report,
        "historical_source_first_publication_authenticated":False,
        "not_a_pregame_source_for_dates_before_observation":True,
        "player_snap_participation_confirmed":False,
        "no_game_scores_or_bets_computed":True,
        "market_edge_validated":False,"model_promoted":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}


def run(output,now=None,fetcher=fetch_asset):
    result=probe(now or dt.datetime.now(dt.timezone.utc).isoformat(),fetcher)
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({
        "upcoming_games_examined":result["upcoming_games_examined"],
        "matched_both_side_history":result["matched_both_side_history"],
        "model_promoted":False},sort_keys=True))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.output)

"""Capture free 2024/2025 ESPN player-game box scores and schedules as observed.

Uses the provider's YEAR-labelled season, not kickoff calendar year, so
January 2026 postseason belongs to 2025. Athletes use stable ESPN athlete
IDs. A different prior-team association is not proof of transfer status,
eligibility or actual playing time on an earlier date.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path

from scripts.game_context import parse_time
from scripts.nextgen_source_readiness import SOURCE,fetch_asset
from scripts.player_prop_history import from_box_rows,NEEDED,_id

STATUS="SOURCE_OBSERVED_2024_2025_PLAYER_GAME_FORM_RESEARCH_ONLY"
SEASONS=(2024,2025)
SCHEDULE_COLS={"game_id","season","start_date","start_time_tbd","completed",
               "home_id","away_id","home_team","away_team","fbs_participant"}

def make_schedule(rows,season,observed_at_utc):
    now=parse_time(observed_at_utc)
    games={};skipped=defaultdict(int)
    for item in rows:
        if item.get("season")!=season:
            skipped["WRONG_FOOTBALL_SEASON"]+=1;continue
        if item.get("completed") is not True:
            skipped["UNCOMPLETED_GAME"]+=1;continue
        if item.get("fbs_participant") is not True:
            skipped["NO_VERIFIED_FBS_PARTICIPANT"]+=1;continue
        if item.get("start_time_tbd") is True:
            skipped["UNVERIFIED_KICKOFF_CLOCK"]+=1;continue
        gid,home,away=_id(item.get("game_id")),_id(item.get("home_id")),_id(item.get("away_id"))
        if not gid or not home or not away or home==away:
            skipped["UNVERIFIED_TEAM_GAME_IDENTITY"]+=1;continue
        kick=parse_time(item["start_date"])
        if kick>=now:
            skipped["GAME_NOT_FINISHED_BY_CAPTURE"]+=1;continue
        if gid in games:raise ValueError("Duplicate same-season ESPN fixture")
        games[gid]={"game_id":gid,"date":kick.date().isoformat(),
                    "kickoff_utc":kick.isoformat(),
                    "home":item["home_team"],"away":item["away_team"],
                    "home_id":home,"away_id":away,
                    "football_season":season}
    return games,dict(skipped)

def assemble(box_by_season,schedules_by_season,asof_utc,source_shas=None):
    now=parse_time(asof_utc)
    if set(box_by_season)!=set(SEASONS) or set(schedules_by_season)!=set(SEASONS):
        raise ValueError("Both past football seasons are required")
    output={};athletes=defaultdict(lambda:defaultdict(set));summaries={}
    for season in SEASONS:
        games,excluded=make_schedule(schedules_by_season[season],season,asof_utc)
        ledger=from_box_rows(box_by_season[season],games,asof_utc,season=season)
        if ledger["season"]!=season:
            raise ValueError("Wrong ESPN football season on box output")
        for row in ledger["rows"]:
            athletes[str(row["player_id"])][season].add(str(row["team_id"]))
        output[str(season)]={"season":season,"observed_at_utc":now.isoformat(),
            "source_box_uri":SOURCE+"/espn_cfb_player_box/player_box_"+str(season)+".parquet",
            "source_schedule_uri":SOURCE+"/cfb_schedules/cfb_schedules_"+str(season)+".parquet",
            "source_sha256":(source_shas or {}).get(season),
            "games_with_matched_completed_fixture":len(games),
            "player_game_rows":ledger["recorded_player_games"],
            "skipped_schedule_rows":excluded,
            "skipped_player_stat_rows":ledger["rejected_by_reason"],
            "player_game_ledger":ledger["rows"]}
    repeat=0;changed=0;examples=[]
    for athlete,season_map in sorted(athletes.items()):
        if len(season_map)!=2:continue
        repeat+=1
        first=season_map[2024];second=season_map[2025]
        if first!=second:
            changed+=1
            if len(examples)<50:
                examples.append({"player_id":athlete,
                    "team_ids_2024":sorted(first),
                    "team_ids_2025":sorted(second),
                    "transfer_eligibility_verified":False})
    return {"status":STATUS,"seasons":list(SEASONS),
        "source_observed_at_utc":now.isoformat(),
        "summary":{"2024_player_games":output["2024"]["player_game_rows"],
                   "2025_player_games":output["2025"]["player_game_rows"],
                   "2024_matched_games":output["2024"]["games_with_matched_completed_fixture"],
                   "2025_matched_games":output["2025"]["games_with_matched_completed_fixture"],
                   "athletes_observed_both_seasons":repeat,
                   "athletes_with_changed_team_ids":changed},
        "by_season":output,
        "changed_team_association_examples":examples,
        "athlete_id_same_between_years_verified_by_recorded_id":True,
        "prior_team_change_is_not_verified_transfer_eligibility":True,
        "historical_first_publication_authenticated":False,
        "future_use_requires_actual_pregame_archive_observation":True,
        "all_player_participation_verified":False,
        "no_prop_bookmaker_lines_implied":True,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

def run(output):
    import pyarrow.parquet as pq
    season_boxes={};season_schedules={};source_shas={}
    for year in SEASONS:
        box_uri=SOURCE+"/espn_cfb_player_box/player_box_"+str(year)+".parquet"
        schedule_uri=SOURCE+"/cfb_schedules/cfb_schedules_"+str(year)+".parquet"
        box_bytes=fetch_asset(box_uri,max_bytes=150_000_000)
        schedule_bytes=fetch_asset(schedule_uri,max_bytes=150_000_000)
        box_file=pq.ParquetFile(io.BytesIO(box_bytes))
        schedule_file=pq.ParquetFile(io.BytesIO(schedule_bytes))
        if not NEEDED.issubset(set(box_file.schema_arrow.names)):
            raise ValueError("Missing actual prior-season player stat schema for "+str(year))
        if not SCHEDULE_COLS.issubset(set(schedule_file.schema_arrow.names)):
            raise ValueError("Missing actual ESPN fixture schema for "+str(year))
        season_boxes[year]=box_file.read(columns=sorted(NEEDED)).to_pylist()
        season_schedules[year]=schedule_file.read(columns=sorted(SCHEDULE_COLS)).to_pylist()
        source_shas[year]={"box":hashlib.sha256(box_bytes).hexdigest(),
                           "schedule":hashlib.sha256(schedule_bytes).hexdigest()}
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    result=assemble(season_boxes,season_schedules,now,source_shas)
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":STATUS,"summary":result["summary"],
          "validated_prop_betting_lines":0,"model_promoted":False}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    run(p.parse_args().output)

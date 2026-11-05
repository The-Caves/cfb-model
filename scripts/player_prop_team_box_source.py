"""SportsDataverse ESPN 2026 team-box + drive research source adapter.

Uses the no-key ESPN-derived release assets to avoid guessing a team's
offensive plays from a few player stats. Both teams and their own game IDs
must reconcile against a completed ESPN schedule. Source observed *now*
is NOT proof of what ESPN published in past weeks; same-day finals are
embargoed. A recorded drive is an observed possession count, not proof
that every ESPN drive or attributed point was independently audited.

Output is for the non-promoted, optional simulation only.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import re
from collections import Counter,defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time
from scripts.nextgen_source_readiness import SOURCE,fetch_asset
from scripts.player_prop_team_budget import STATUS as TEAM_STATUS
from scripts.player_prop_joint_simulation import POS_SOURCE

ET=ZoneInfo("America/New_York")
BOX_URL=SOURCE+"/espn_cfb_team_box/team_box_2026.parquet"
DRIVES_URL=SOURCE+"/espn_cfb_drives/drives_2026.parquet"
SCHEDULE_URL=SOURCE+"/cfb_schedules/cfb_schedules_2026.parquet"
BOX_COLS={"game_id","team_id","season","home_away","completionAttempts","rushingAttempts"}
DRIVE_COLS={"game_id","team_id","season","drive_id"}
SCHED_COLS={"game_id","season","completed","fbs_participant","start_time_tbd",
            "start_date","home_id","away_id","home_team","away_team"}
STATUS="ESPN_TEAM_BOX_AND_DRIVE_SOURCE_OBSERVED_RESEARCH_ONLY"


def _id(v):
    s=str(v or "")
    return s if s.isdigit() and int(s)>0 else None


def _attempts(row):
    p=str(row.get("completionAttempts") or "")
    r=str(row.get("rushingAttempts") or "")
    m=re.fullmatch(r"(\d+)/(\d+)",p)
    if not m or not re.fullmatch(r"\d+",r):return None
    comps,passes=int(m.group(1)),int(m.group(2))
    rushes=int(r)
    if not (0<=comps<=passes<=110 and 0<=rushes<=110
            and 0<passes+rushes<=140):
        return None
    return passes,rushes


def assemble(box_rows,drives_rows,schedule_rows,target,now):
    instant=parse_time(now)
    if (instant>=parse_time(target["kickoff_utc"]) or
        target.get("date")!=parse_time(target["kickoff_utc"]).astimezone(ET).date().isoformat()):
        raise ValueError("Target football date or decision cutoff invalid")
    schedule={};skipped=Counter()
    for g in schedule_rows:
        if int(g.get("season") or 0)!=2026:continue
        gid=_id(g.get("game_id"))
        if not gid or gid in schedule:
            raise ValueError("Repeated or invalid ESPN schedule game")
        schedule[gid]=g
    gid=_id(target.get("game_id"))
    current=schedule.get(gid)
    if (not current or current.get("completed") is not False or
        current.get("start_time_tbd") is not False or
        current.get("fbs_participant") is not True or
        parse_time(current["start_date"])!=parse_time(target["kickoff_utc"]) or
        current["home_team"]!=target["home"] or
        current["away_team"]!=target["away"] or
        str(current["home_id"])!=str(target["team_ids"]["home"]) or
        str(current["away_id"])!=str(target["team_ids"]["away"])):
        raise ValueError("Future target ESPN team-game identity not authenticated")
    eligible={}
    for gameid,g in schedule.items():
        if (g.get("completed") is not True or
            g.get("fbs_participant") is not True or
            g.get("start_time_tbd") is not False):
            continue
        kick=parse_time(g["start_date"])
        if (kick>=instant or
            kick.astimezone(ET).date()>=instant.astimezone(ET).date() or
            kick.astimezone(ET).date()>=parse_time(target["kickoff_utc"]).astimezone(ET).date()):
            continue
        home=_id(g.get("home_id"));away=_id(g.get("away_id"))
        if not home or not away or home==away:
            skipped["INVALID_TEAM_IDS"]+=1;continue
        eligible[gameid]=(g,kick,home,away)
    boxes=defaultdict(list)
    for row in box_rows:
        if int(row.get("season") or 0)!=2026:continue
        boxid=_id(row.get("game_id"))
        if boxid in eligible:boxes[boxid].append(row)
    drives=defaultdict(list)
    for row in drives_rows:
        if int(row.get("season") or 0)!=2026:continue
        driveid=_id(row.get("game_id"))
        if driveid in eligible:drives[driveid].append(row)
    outbox=[];outposs=[]
    allowed_ids={str(target["team_ids"]["home"]),str(target["team_ids"]["away"])}
    for gameid,(game,kick,home,away) in eligible.items():
        rows=boxes.get(gameid,[])
        unique={}
        for row in rows:
            team=_id(row.get("team_id"))
            if team not in (home,away) or team in unique or row.get("home_away") not in ("home","away"):
                unique={};break
            if row["home_away"]!=("home" if team==home else "away"):
                unique={};break
            counts=_attempts(row)
            if counts is None:
                unique={};break
            unique[team]=counts
        if len(unique)!=2:
            skipped["INVALID_OR_INCOMPLETE_TWO_SIDED_TEAM_BOX"]+=1;continue
        # Source provides drive identifiers; missing/ambiguous team drive
        # records are not imputed from final points or player totals.
        ds=drives.get(gameid,[])
        byteam=defaultdict(set)
        invalid=False
        for x in ds:
            team=_id(x.get("team_id"));drive=str(x.get("drive_id") or "")
            if team not in (home,away) or not drive or drive in byteam[team]:
                invalid=True;break
            byteam[team].add(drive)
        if invalid or not all(1<=len(byteam[team])<=24 for team in (home,away)):
            skipped["INCOMPLETE_OR_AMBIGUOUS_DRIVE_IDS"]+=1;continue
        for team in (home,away):
            if team not in allowed_ids:continue
            side="home" if team==home else "away"
            passatt,rushatt=unique[team]
            outbox.append({
                "game_id":gameid,"team_id":team,
                "kickoff_utc":kick.isoformat(),
                # Conservative first-known timestamp; never backdate finals.
                "outcome_known_at_utc":instant.isoformat(),
                "captured_at_utc":instant.isoformat(),
                "passing_attempts":passatt,
                "rushing_attempts":rushatt,
                "complete_team_attempts_reviewed":True,
                "source_url":BOX_URL})
            outposs.append({
                "game_id":gameid,"team_id":team,
                "team_possessions":len(byteam[team]),
                "observed_at_utc":instant.isoformat(),
                "source_url":DRIVES_URL})
    budget={"status":TEAM_STATUS,"season":2026,
        "target_game_id":gid,"target_kickoff_utc":target["kickoff_utc"],
        "observed_at_utc":instant.isoformat(),
        "rows":sorted(outbox,key=lambda r:(r["kickoff_utc"],r["team_id"])),
        "betting_status":"PASS_UNVALIDATED",
        "safe_for_betting":False,"model_promoted":False,
        "source_revision_first_published_before_decision":False,
        "team_totals_complete_two_sided_source_rows":True,
        "not_independently_reconciled_official_gamebook":True}
    possession={"status":POS_SOURCE,
        "observed_at_utc":instant.isoformat(),
        "rows":sorted(outposs,key=lambda r:(r["game_id"],r["team_id"])),
        "historical_drives_complete_universally_verified":False,
        "source_revision_first_published_before_decision":False}
    summary={"status":STATUS,"observed_at_utc":instant.isoformat(),
        "matched_historical_games_for_target":len(set(x["game_id"] for x in outbox)),
        "historical_team_rows":len(outbox),
        "skipped_by_reason":dict(skipped),
        "full_game_scores_and_picks_changed":False,
        "historical_publication_time_authenticated":False,
        "valid_only_for_forecasts_observed_after_this_capture":True,
        "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}
    return budget,possession,summary


def _load(url,columns,fetcher):
    import pyarrow.parquet as pq
    blob=fetcher(url,max_bytes=150_000_000)
    p=pq.ParquetFile(io.BytesIO(blob))
    missing=columns-set(p.schema_arrow.names)
    if missing:
        raise ValueError("Missing ESPN-derived source schema: "+str(sorted(missing)))
    return p.read(columns=sorted(columns)).to_pylist(),hashlib.sha256(blob).hexdigest()


def run(target_path,budget_path,pos_path,summary_path,now=None,fetcher=fetch_asset):
    instant=now or dt.datetime.now(dt.timezone.utc).isoformat()
    target=json.loads(Path(target_path).read_text(encoding="utf-8"))
    box,boxsha=_load(BOX_URL,BOX_COLS,fetcher)
    drives,drivesha=_load(DRIVES_URL,DRIVE_COLS,fetcher)
    schedule,schedulesha=_load(SCHEDULE_URL,SCHED_COLS,fetcher)
    budget,poss,summary=assemble(box,drives,schedule,target,instant)
    summary["source_sha256"]={"team_box":boxsha,"drives":drivesha,"schedule":schedulesha}
    for output,obj in ((budget_path,budget),(pos_path,poss),(summary_path,summary)):
        p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
        with p.open("x",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps(summary,sort_keys=True))
    return budget,poss,summary


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for arg in ("target","budget","possessions","summary"):
        p.add_argument("--"+arg,required=True)
    p.add_argument("--asof")
    a=p.parse_args()
    run(a.target,a.budget,a.possessions,a.summary,a.asof)

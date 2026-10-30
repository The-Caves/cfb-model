"""Fit honest drive-outcome frequency tables for the research simulator.

Requires COMPLETE, independently source-reviewed historical game drives with
actual scoring attributed to offense. This module cannot infer touchdown drive
results from final scores or provider's incompletely documented drive ids.
"""
import argparse
import json
from collections import Counter,defaultdict
from pathlib import Path

from scripts.game_context import parse_time
from scripts.game_simulation_research import SOURCE, POINTS

STATUS="SOURCE_REVIEWED_HISTORICAL_DRIVE_FIT_READINESS"
SOURCE_STATUS="OFFICIAL_POSTGAME_DRIVES_REVIEWED_RESEARCH_ONLY"
ZONES={"own_deep","own_half","midfield","opponent_half","red_zone"}


def validate_record(record,decision):
    gid=str(record.get("game_id",""))
    home,away=record.get("home"),record.get("away")
    if not gid or not home or not away or home==away:
        raise ValueError("Invalid game and team mapping")
    kickoff=parse_time(record["kickoff_utc"])
    known=parse_time(record["outcome_known_at_utc"])
    captured=parse_time(record["source_captured_at_utc"])
    if not kickoff<known<=captured<=decision:
        raise ValueError("Non-historical or backdated drive source")
    if (record.get("complete_drives_reviewed") is not True
        or record.get("source_status")!=SOURCE_STATUS
        or not str(record.get("source_url","")).startswith("https://")):
        raise ValueError("Incomplete or unsourced drive history")
    seen=set();counts={home:0,away:0}
    for drive in record["drives"]:
        team=drive.get("team")
        key=(team,str(drive.get("drive_id","")))
        if team not in (home,away) or not key[1] or key in seen:
            raise ValueError("Unmapped or duplicated drive")
        seen.add(key);counts[team]+=1
        if (drive.get("field_zone") not in ZONES or type(drive.get("points")) is not int
            or drive["points"] not in POINTS or type(drive.get("explosive")) is not bool):
            raise ValueError("Unsupported starting field zone or actual scoring")
    if not all(1<=n<=24 for n in counts.values()):
        raise ValueError("Missing or implausible two-sided game possessions")
    return counts


def fit(bundle,game,decision_utc,minimum_games=3,minimum_drives=25):
    when=parse_time(decision_utc)
    if bundle.get("status")!=SOURCE_STATUS or bundle.get("season")!=2026:
        raise ValueError("Unreviewed drive event bundle")
    if (bundle.get("betting_status")!="PASS_UNVALIDATED"
        or bundle.get("safe_for_betting") is not False):
        raise ValueError("Drive source must be research-only")
    if type(minimum_games) is not int or minimum_games<2 or (
        type(minimum_drives) is not int or minimum_drives<4):
        raise ValueError("Invalid coverage threshold")
    home,away=game["home"],game["away"]
    if not home or not away or home==away or when>=parse_time(game["kickoff_utc"]):
        raise ValueError("Missing or started target game")
    records=[];seen=set()
    for row in bundle.get("games",[]):
        gid=str(row.get("game_id",""))
        if gid in seen: raise ValueError("Duplicate historical game record")
        seen.add(gid)
        counts=validate_record(row,when)
        records.append((row,counts))
    sides={}
    for side,team in (("home",home),("away",away)):
        relevant=[r for r,c in records if team in (r["home"],r["away"])]
        drives=[d for r in relevant for d in r["drives"] if d["team"]==team]
        sides[side]={"game_count":len(relevant),"drives":len(drives),"rows":drives}
    ready=all(v["game_count"]>=minimum_games and v["drives"]>=minimum_drives
              for v in sides.values())
    zone_counts=Counter(d["field_zone"] for s in sides.values() for d in s["rows"])
    missing_zone=[]
    if ready:
        for side,s in sides.items():
            for zone in zone_counts:
                if not any(d["field_zone"]==zone for d in s["rows"]):
                    missing_zone.append((side,zone))
    result={
        "status":STATUS,"game_id":str(game["game_id"]),"home":home,"away":away,
        "kickoff_utc":game["kickoff_utc"],"decision_utc":when.isoformat(),
        "historical_games_considered":len(records),
        "sample_summary":{side:{"games":s["game_count"],"drives":s["drives"]}
                          for side,s in sides.items()},
        "missing_conditional_zones":[{"side":side,"zone":zone} for side,zone in missing_zone],
        "simulator_input":None,
        "ready":ready and not missing_zone and bool(zone_counts),
        "market_lines_invented":False,"model_promoted":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"
    }
    if not result["ready"]:
        result["reason"]="INSUFFICIENT_VERIFIED_PAST_DRIVE_COVERAGE"
        return result
    # Historical game possession counts preserve pairwise home/away drive totals.
    observed=[(r,c) for r,c in records if home in (r["home"],r["away"])
              or away in (r["home"],r["away"])]
    pairs=Counter((c[r["home"]],c[r["away"]]) for r,c in observed)
    possession=[{"home_count":h,"away_count":a,"weight":n}
                for (h,a),n in sorted(pairs.items())]
    outcomes={}
    for side,s in sides.items():
        outcomes[side]={}
        for zone in sorted(zone_counts):
            values=Counter((d["points"],d["explosive"]) for d in s["rows"]
                           if d["field_zone"]==zone)
            outcomes[side][zone]=[
                {"points":points,"explosive":explosive,"weight":n}
                for (points,explosive),n in sorted(values.items())
            ]
    last_capture=max(parse_time(r["source_captured_at_utc"]) for r,c in observed)
    result["simulator_input"]={
        "status":SOURCE,"game_id":str(game["game_id"]),
        "home":home,"away":away,"kickoff_utc":game["kickoff_utc"],
        "trained_through_utc":last_capture.isoformat(),
        "source_captured_at_utc":last_capture.isoformat(),
        "distributions":{
            "possessions":possession,
            "field_position":[{"zone":z,"weight":n} for z,n in sorted(zone_counts.items())],
            "outcomes":outcomes,
        },
        "source_provenance":"OFFICIAL_COMPLETED_DRIVE_ROWS_REVIEWED",
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"
    }
    return result


def run(input_path,game_path,decision,output_path):
    result=fit(json.loads(Path(input_path).read_text()),
               json.loads(Path(game_path).read_text()),decision)
    target=Path(output_path);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--input",required=True)
    p.add_argument("--game",required=True);p.add_argument("--decision",required=True)
    p.add_argument("--output",required=True);a=p.parse_args()
    run(a.input,a.game,a.decision,a.output)

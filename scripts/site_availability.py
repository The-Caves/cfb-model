"""Overlay time-verified *official* all-position availability reports on the CFB board.

Availability designations are NOT game-specific starter confirmations, and
do not update already-frozen model coefficients, picks, or training data.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time
from scripts.official_availability import fetch_and_match

ET=ZoneInfo("America/New_York")
VALID={"OUT","OUT_FIRST_HALF","QUESTIONABLE","DOUBTFUL","PROBABLE","AVAILABLE",
       "GAME_TIME_DECISION","LIMITED","SUSPENDED"}
POSITIONS={"QB","RB","WR","TE","OL","DL","EDGE","LB","CB","DB","S","K","P"}


def merge(board,rows,now,manifest=None):
    if board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Invalid QB board")
    indexed={str(g["game_id"]):g for g in board["games"]}
    picked={}
    for row in rows:
        if row.get("kind")!="AVAILABILITY" or row.get("position") not in POSITIONS:
            continue
        gid=str(row.get("game_id",""));g=indexed.get(gid)
        if not g:continue
        team=row.get("team")
        if team not in (g["home_team"],g["away_team"]):continue
        status=row.get("status")
        name=row.get("player")
        if status not in VALID or not isinstance(name,str) or not 2<=len(name)<=100:
            continue
        try:
            pub=parse_time(row["published_at_utc"])
            captured=parse_time(row["captured_at_utc"])
            kickoff=parse_time(row["kickoff_utc"])
        except (ValueError,KeyError,TypeError):continue
        if (kickoff!=parse_time(g["kickoff_utc"]) or
            not pub<=captured<=now<kickoff or
            (captured-pub).total_seconds()>36*3600 or
            not str(row.get("source_url") or "").startswith("https://")):
            continue
        position=row["position"]
        key=(gid,team,name.casefold(),position)
        record={"player":name,"position":position,"status":status,"published_at_utc":row["published_at_utc"],
                "observed_at_utc":row["captured_at_utc"],
                "source_url":row["source_url"],
                "source_type":"OFFICIAL_CONFERENCE_AVAILABILITY",
                "not_starter_confirmation":True}
        prev=picked.get(key)
        if prev and parse_time(prev["published_at_utc"])==pub and prev["status"]!=status:
            # Same-time contradictory statuses: quarantine rather than pick one.
            picked[key]={**record,"status":"CONFLICT_REVIEW"}
        elif (prev is None or (prev["status"]!="CONFLICT_REVIEW" and
                 (pub,captured)>(parse_time(prev["published_at_utc"]),
                                  parse_time(prev["observed_at_utc"])) )):
            picked[key]=record
    counts={"official_all_position_designations":0,
            "actionable_non_qb_designations":0,
            "games_with_actionable_non_qb_reports":0,
            "official_qb_designations":0,"actionable_qb_designations":0,
            "games_with_qb_designations":0,"games_with_actionable_qb_designations":0,
            "starter_conflicts":0}
    for g in board["games"]:
        has_qb=False
        non_qb=False
        for side in ("home","away"):
            team=g[side+"_team"]
            all_designations=sorted(
                (v for (gid,t,_,position),v in picked.items()
                 if gid==str(g["game_id"]) and t==team and position=="QB"),
                key=lambda r:(r["player"],r["status"]))
            # Do not flood cards with all listed backup QBs marked AVAILABLE.
            # Available/probable is not confirmation of QB1 or even playing time.
            designations=[r for r in all_designations
                          if r["status"] not in ("AVAILABLE","PROBABLE")]
            g["qb_availability_"+side]=designations
            all_players=sorted(
                (v for (gid,t,_,position),v in picked.items()
                 if gid==str(g["game_id"]) and t==team and position!="QB"),
                key=lambda r:(r["position"],r["player"],r["status"]))
            # Keep only actionable non-QB reports on the display, never
            # infer that omission or AVAILABLE guarantees playing time.
            actionable=[r for r in all_players if r["status"] not in
                        ("AVAILABLE","PROBABLE")]
            g["player_availability_"+side]=actionable
            counts["official_all_position_designations"]+=len(all_designations)+len(all_players)
            counts["actionable_non_qb_designations"]+=len(actionable)
            non_qb |= bool(actionable)
            counts["official_qb_designations"]+=len(all_designations)
            counts["actionable_qb_designations"]+=len(designations)
            has_qb|=bool(all_designations)
            if designations:g.setdefault("_qb_has_actionable",True)
            claimed=g.get("qb_"+side) or {}
            if claimed.get("status")=="CONFIRMED_OFFICIAL":
                if any(d["player"].casefold()==claimed["player"].casefold()
                       and d["status"] in ("OUT","SUSPENDED","DOUBTFUL","CONFLICT_REVIEW")
                       for d in designations):
                    g["qb_"+side]={**claimed,"status":"CONFLICT_REVIEW",
                                   "description":"New official availability conflicts with an earlier starter confirmation"}
                    counts["starter_conflicts"]+=1
        counts["games_with_actionable_non_qb_reports"]+=int(non_qb)
        counts["games_with_qb_designations"]+=int(has_qb)
        counts["games_with_actionable_qb_designations"]+=int(g.pop("_qb_has_actionable",False))
    board["qb_availability_display"]={
        **counts,
        "source":"Official SEC/Big Ten/ACC/Big 12 published availability reporting",
        "observed_at_utc":now.isoformat(),
        "evidence_is_game_specific":True,
        "confirms_starting_qb":False,
        "all_player_positions_covered_when_officially_published":True,
        "not_listed_player_is_assumed_available":False,
        "not_a_medical_diagnosis":True,
        "changes_frozen_model_picks":False,
        "warning":"Source-reviewed current official reports for ALL player positions, not only QB; not a starter or health clearance. An unlisted player remains UNKNOWN. Questionable does not mean OUT; reports may postdate frozen scores.",
        "fetch_status":{k:{"status":v.get("status","FETCHED"),
                          "accepted_reports":v.get("official_reports_accepted",0),
                          "card_decisions":sorted([
                            {"match":str(card.get("game_match","UNKNOWN")),
                             "published":str(card.get("publication_status","UNVERIFIED")),
                             "reason":str(card.get("error",""))[:130]}
                            for card in v.get("report_cards",[]) if
                            card.get("publication_status")=="ACCEPTED_VERIFIED_OFFICIAL_REPORT"
                            or card.get("game_match")!="NO_UNIQUE_ESPN_GAME_MATCH"
                          ],key=lambda x:(x["match"],x["published"]))[:15],
                          "total_cards":v.get("card_count",0)}
                        for k,v in (manifest or {}).get("feeds",{}).items()}}
    return board

def run(dashboard_path,aliases="data/archive/2026_team_aliases.csv",now=None,fetcher=fetch_and_match):
    path=Path(dashboard_path)
    board=json.loads(path.read_text())
    now_was_omitted=now is None
    now=now or dt.datetime.now(dt.timezone.utc)
    upcoming=[{"game_id":str(g["game_id"]),"home":g["home_team"],
       "away":g["away_team"],"kickoff_utc":g["kickoff_utc"],
       "date_et":parse_time(g["kickoff_utc"]).astimezone(ET).date().isoformat()}
       for g in board["games"] if parse_time(g["kickoff_utc"])>now]
    with TemporaryDirectory() as tmp:
        rows,manifest=fetcher(upcoming,aliases,Path(tmp)/"reports")
    # Fetcher records its actual collection time *during* these calls.
    # A pre-fetch cutoff would wrongly discard every freshly captured row.
    # Always advance the observation instant after collection in real runs;
    # keep explicit now for deterministic fixture-based tests.
    verified_cutoff=dt.datetime.now(dt.timezone.utc) if now_was_omitted else now
    result=merge(board,rows,verified_cutoff,manifest)
    diagnostics={}
    for item in rows:
        if item.get("kind")!="AVAILABILITY":continue
        pos=str(item.get("position") or "MISSING")
        diagnostics[pos]=diagnostics.get(pos,0)+1
    result["qb_availability_display"]["publisher_player_rows_by_position"]=diagnostics
    result["qb_availability_display"]["publisher_total_player_rows"]=sum(diagnostics.values())
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result["qb_availability_display"]))
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--dashboard",required=True)
    args=parser.parse_args()
    run(args.dashboard)

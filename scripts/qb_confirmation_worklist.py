"""Prioritized source-review worklist for 2026 game-specific QB confirmations.

This is a triage table, NOT starting-QB evidence. A source homepage, RSS
feed, discovered game note or depth chart is never silently a confirmed QB1.
"""
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlsplit
from scripts.game_context import parse_time

STATUS="QB_STARTER_MANUAL_REVIEW_WORKLIST_RESEARCH_ONLY"
FIELDS=("game_id","kickoff_utc","team","opponent","review_priority",
        "starter_status","feed_status","candidate_count","official_rss_url",
        "official_athletics_homepage","homepage_verified","game_notes_url",
        "game_notes_verified","personnel_evidence_verified","source_followup",
        "source_verification_status")

def build(queue,source_registry):
    if (queue.get("status")!="QB_REVIEW_RESEARCH_ONLY" or
        queue.get("betting_status")!="PASS_UNVALIDATED" or
        source_registry.get("status")!="SOURCE_CANDIDATES_WITH_CONNECTIVITY_AUDIT_NOT_PERSONNEL_VERIFIED"):
        raise ValueError("Untrusted QB queue/school source inventory")
    idx={}
    for school in source_registry["schools"]:
        team=school["team"]
        if team in idx:raise ValueError("Duplicate canonical school")
        idx[team]=school
    ranked=[];seen=set()
    for row in queue["rows"]:
        gid=str(row["game_id"]);team=row["team"];kickoff=parse_time(row["kickoff_utc"])
        key=(gid,team)
        if key in seen:raise ValueError("Duplicate QB roster slot")
        seen.add(key)
        school=idx.get(team)
        if school is None:raise ValueError("Team missing national source registry")
        source=school.get("official_rss_url")
        homepage=school.get("official_athletics_homepage")
        notes=school.get("game_notes_url")
        for url in (source,homepage,notes):
            if url is None:continue
            p=urlsplit(url)
            if p.scheme!="https" or not p.hostname or p.username or p.password:
                raise ValueError("Source URL invalid")
        # Document links are leads to be actually read, not claims of QB1.
        if row.get("starter_status")=="VERIFIED_SOURCE":
            follow="AUDIT_PREEXISTING_REVIEWED_CLAIM"
        elif row.get("candidate_count",0)>0:
            follow="REVIEW_DATED_OFFICIAL_QB_NEWS_CANDIDATES"
        elif school.get("official_rss_registry_reviewed") is True:
            follow="CHECK_SCHEDULED_OFFICIAL_ARTICLES_AND_GAME_NOTES"
        else:
            follow="FIND_AND_REVIEW_CURRENT_SCHOOL_GAME_NOTES_OR_COACH_STATEMENT"
        ranked.append({
            "game_id":gid,"kickoff_utc":kickoff.isoformat(),"team":team,
            "opponent":row["opponent"],"review_priority":row.get("review_priority","UNKNOWN_NEEDS_SOURCE"),
            "starter_status":row.get("starter_status","UNKNOWN"),
            "feed_status":row.get("feed_status","NOT_CONFIGURED"),
            "candidate_count":row.get("candidate_count",0),
            "official_rss_url":source,"official_athletics_homepage":homepage,
            "homepage_verified":school.get("homepage_verified") is True,
            "game_notes_url":notes,
            "game_notes_verified":school.get("personnel_evidence_verified") is True and bool(notes),
            "personnel_evidence_verified":school.get("personnel_evidence_verified") is True,
            "source_followup":follow,
            "source_verification_status":"SOURCE_CANDIDATE_ONLY_NO_GAME_SPECIFIC_STARTER_CONFIRMATION"
        })
    ranked.sort(key=lambda row:(row["kickoff_utc"],-int(row["candidate_count"]>0),row["game_id"],row["team"]))
    if len(ranked)!=2*len({r["game_id"] for r in ranked}):
        raise ValueError("Expected one QB review slot for both schools in every matchup")
    n=len(ranked)
    return {"status":STATUS,"season":2026,"betting_status":"PASS_UNVALIDATED",
        "asof_utc":queue["asof_utc"],"safe_for_betting":False,
        "game_specific_QB_confirmations_added":0,"trained_replacement_points":False,
        "summary":{"future_games":n//2,"team_slots":n,
                   "unreviewed_or_unknown_slots":sum(r["starter_status"]!="VERIFIED_SOURCE" for r in ranked),
                   "school_homepage_candidates":sum(bool(r["official_athletics_homepage"]) for r in ranked),
                   "rss_school_links":sum(bool(r["official_rss_url"]) for r in ranked),
                   "prioritized_official_news_candidates":sum(r["candidate_count"]>0 for r in ranked)},
        "rows":ranked,"manual_acceptance_requirements":[
            "Read an explicit game-specific official coach/school QB starter declaration",
            "Verify exact ESPN game identity, teams and originally published instant",
            "Record real capture and independent review timestamps before kickoff",
            "Apply qb_starter_review evidence gate; do not invent old capture clocks"]}

def run(queue_path,source_path,output,review_csv=None):
    board=build(json.loads(Path(queue_path).read_text()),json.loads(Path(source_path).read_text()))
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():raise FileExistsError("Refuse overwrite QB worklist")
    dest.write_text(json.dumps(board,indent=2,allow_nan=False)+"\n")
    if review_csv:
        p=Path(review_csv);p.parent.mkdir(parents=True,exist_ok=True)
        with p.open("x",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(board["rows"])
    print(json.dumps(board["summary"]))
    return board
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--queue",required=True)
    p.add_argument("--registry",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--review-csv")
    args=p.parse_args()
    run(args.queue,args.registry,args.output,args.review_csv)

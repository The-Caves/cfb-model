"""Prioritized source-review worklist for 2026 game-specific QB confirmations.

This is a triage table, NOT starting-QB evidence. A source homepage, RSS
feed, discovered game note or depth chart is never silently a confirmed QB1.
"""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit
from scripts.game_context import parse_time

STATUS="QB_STARTER_MANUAL_REVIEW_WORKLIST_RESEARCH_ONLY"
FIELDS=("game_id","kickoff_utc","team","opponent","review_priority",
        "starter_status","feed_status","candidate_count","official_rss_url",
        "official_athletics_homepage","homepage_verified","game_notes_url",
        "game_notes_verified","personnel_evidence_verified",
        "reviewed_official_preview_url","reviewed_game_notes_link",
        "reviewed_gameweek_source_status","contextual_qb_player",
        "contextual_qb_evidence_type","contextual_qb_reliability",
        "contextual_qb_summary","contextual_qb_source_url",
        "source_followup",
        "source_verification_status")

def _gameweek_index(config):
    if config is None:return {}
    if (config.get("status")!="REVIEWED_OFFICIAL_GAMEWEEK_LINKS_NOT_QB_STARTERS" or
        config.get("season")!=2026 or not isinstance(config.get("entries"),list)):
        raise ValueError("Untrusted gameweek document registry")
    index={}
    for e in config["entries"]:
        if (not isinstance(e,dict) or e.get("starter_confirmed") is not False or
            e.get("evidence_type")!="OFFICIAL_GAMEWEEK_PREVIEW_NO_QB1_CLAIM"):
            raise ValueError("Gameweek release cannot imply confirmed starter")
        key=(str(e.get("game_id")),e.get("team"))
        if key in index:raise ValueError("Duplicate official gameweek source")
        date=dt.date.fromisoformat(e["published_date"])
        if date.year!=2026:raise ValueError("Stale gameweek release")
        ctx=e.get("qb_context")
        if ctx is not None:
            if (not isinstance(ctx,dict) or ctx.get("mention_type") not in
                {"RETURNED_FROM_INJURY_IN_PREVIOUS_GAME","PREVIOUS_TWO_GAMES_STARTED",
                 "SEASON_PASSING_PRODUCTION"} or
                not isinstance(ctx.get("player"),str) or not 4<=len(ctx["player"])<=90 or
                not isinstance(ctx.get("summary"),str) or not 20<=len(ctx["summary"])<=300 or
                not isinstance(ctx.get("quote"),str) or not 5<=len(ctx["quote"])<=180 or
                ctx.get("source_url")!=e.get("preview_url") or
                any(term in ctx["summary"].casefold() for term in
                    ("confirmed starter","will start tomorrow","starts this game"))):
                raise ValueError("Contextual quarterback mention is not a verified starter")
        index[key]=e
    return index

def _validated_source_link(url,expected_host,notes=False):
    if url is None:return None
    parsed=urlsplit(url)
    if parsed.scheme!="https" or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError("Untrusted official document URL")
    if parsed.hostname==expected_host:
        return url
    if (notes and parsed.hostname=="s3.us-east-2.amazonaws.com" and
        parsed.path.startswith("/sidearm.nextgen.sites/"+expected_host+"/documents/2026/")):
        return url
    raise ValueError("Gameweek source publisher does not match canonical school")

def build(queue,source_registry,gameweek_sources=None):
    if (queue.get("status")!="QB_REVIEW_RESEARCH_ONLY" or
        queue.get("betting_status")!="PASS_UNVALIDATED" or
        source_registry.get("status")!="SOURCE_CANDIDATES_WITH_CONNECTIVITY_AUDIT_NOT_PERSONNEL_VERIFIED"):
        raise ValueError("Untrusted QB queue/school source inventory")
    idx={}
    for school in source_registry["schools"]:
        team=school["team"]
        if team in idx:raise ValueError("Duplicate canonical school")
        idx[team]=school
    official_week=_gameweek_index(gameweek_sources)
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
        link=official_week.get((gid,team))
        reviewed_preview=None
        reviewed_notes=None
        if link:
            if (link["opponent"]!=row["opponent"] or
                link["kickoff_utc"]!=row["kickoff_utc"]):
                raise ValueError("Gameweek source belongs to different fixture")
            published=dt.date.fromisoformat(link["published_date"])
            age=(kickoff.date()-published).days
            if not 0<=age<=14:raise ValueError("Source not published during game week")
            published_host=urlsplit(homepage).hostname if homepage else None
            if not published_host:
                raise ValueError("No canonical official publisher to verify")
            reviewed_preview=_validated_source_link(link["preview_url"],published_host)
            reviewed_notes=_validated_source_link(link.get("game_notes_url"),published_host,True)
        qb_context=link.get("qb_context") if link else None
        # Document links are leads to be actually read, not claims of QB1.
        if row.get("starter_status")=="VERIFIED_SOURCE":
            follow="AUDIT_PREEXISTING_REVIEWED_CLAIM"
        elif row.get("candidate_count",0)>0:
            follow="REVIEW_DATED_OFFICIAL_QB_NEWS_CANDIDATES"
        elif reviewed_preview:
            follow="CHECK_REVIEWED_OFFICIAL_GAMEWEEK_RELEASE_FOR_EXPLICIT_QB1_UPDATE"
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
            "reviewed_official_preview_url":reviewed_preview,
            "reviewed_game_notes_link":reviewed_notes,
            "reviewed_gameweek_source_status":("OFFICIAL_GAME_MATCH_VERIFIED_NO_QB1_CLAIM" if link else "NO_REVIEWED_GAMEWEEK_SOURCE"),
            "contextual_qb_player":qb_context.get("player") if qb_context else None,
            "contextual_qb_evidence_type":qb_context.get("mention_type") if qb_context else None,
            "contextual_qb_reliability":"OFFICIAL_GAMEWEEK_CONTEXT_NOT_STARTER_CONFIRMED" if qb_context else "NOT_REVIEWED",
            "contextual_qb_summary":qb_context.get("summary") if qb_context else None,
            "contextual_qb_source_url":qb_context.get("source_url") if qb_context else None,
            "source_followup":follow,
            "source_verification_status":"SOURCE_CANDIDATE_ONLY_NO_GAME_SPECIFIC_STARTER_CONFIRMATION"
        })
    ranked.sort(key=lambda row:(row["kickoff_utc"],-int(row["candidate_count"]>0),row["game_id"],row["team"]))
    if len(ranked)!=2*len({r["game_id"] for r in ranked}):
        raise ValueError("Expected one QB review slot for both schools in every matchup")
    if official_week and set(official_week)-seen:
        raise ValueError("Gameweek registry contains stale or unrecognized future game")
    n=len(ranked)
    return {"status":STATUS,"season":2026,"betting_status":"PASS_UNVALIDATED",
        "asof_utc":queue["asof_utc"],"safe_for_betting":False,
        "game_specific_QB_confirmations_added":0,"trained_replacement_points":False,
        "summary":{"future_games":n//2,"team_slots":n,
                   "unreviewed_or_unknown_slots":sum(r["starter_status"]!="VERIFIED_SOURCE" for r in ranked),
                   "school_homepage_candidates":sum(bool(r["official_athletics_homepage"]) for r in ranked),
                   "rss_school_links":sum(bool(r["official_rss_url"]) for r in ranked),
                   "prioritized_official_news_candidates":sum(r["candidate_count"]>0 for r in ranked),
                   "reviewed_official_gameweek_preview_links":sum(bool(r["reviewed_official_preview_url"]) for r in ranked),
                   "linked_official_gameweek_notes":sum(bool(r["reviewed_game_notes_link"]) for r in ranked),
                   "official_contextual_qb_mentions_not_starting_confirmations":sum(bool(r["contextual_qb_player"]) for r in ranked)},
        "rows":ranked,"manual_acceptance_requirements":[
            "Read an explicit game-specific official coach/school QB starter declaration",
            "Verify exact ESPN game identity, teams and originally published instant",
            "Record real capture and independent review timestamps before kickoff",
            "Apply qb_starter_review evidence gate; do not invent old capture clocks"]}

def run(queue_path,source_path,output,review_csv=None,gameweek_sources=None):
    curated=(json.loads(Path(gameweek_sources).read_text()) if gameweek_sources else None)
    board=build(json.loads(Path(queue_path).read_text()),json.loads(Path(source_path).read_text()),curated)
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
    p.add_argument("--gameweek-sources")
    args=p.parse_args()
    run(args.queue,args.registry,args.output,args.review_csv,args.gameweek_sources)

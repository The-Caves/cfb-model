"""Build a research-only review queue for upcoming college-football QB sources."""
import argparse, datetime as dt, json
from pathlib import Path
from scripts.game_context import parse_time
from scripts.qb_official_news_watch import FEEDS

def summarize(rows):
    return {
        "team_game_slots":len(rows),
        "verified_starters":sum(r["starter_status"]=="VERIFIED_SOURCE" for r in rows),
        "unknown_starters":sum(r["starter_status"]=="UNKNOWN" for r in rows),
        "feed_monitored_slots":sum(r["feed_status"]=="FETCHED" for r in rows),
        "feed_failed_slots":sum(r["feed_status"]=="FETCH_FAILED" for r in rows),
        "no_feed_slots":sum(r["feed_status"]=="NOT_CONFIGURED" for r in rows),
        "candidate_mentions":sum(r["candidate_count"] for r in rows),
        "qb_availability_slots":sum(bool(r["qb_availability"]) for r in rows)}

def build_queue(context, news, now):
    issue=parse_time(now)
    if not isinstance(context.get("games"),list):
        raise ValueError("Missing upcoming-game context")
    meta=news.get("manifest",{})
    if meta.get("status")!="OFFICIAL_NEWS_REVIEW_ONLY" or parse_time(meta["asof_utc"])>issue:
        raise ValueError("Unsafe or future-dated news results")
    candidates=news.get("candidates",[])
    if not isinstance(candidates,list):
        raise ValueError("Invalid news candidates")
    feeds=meta.get("feed_status",{})
    rows=[];seen=set()
    for game in sorted(context["games"],key=lambda g:g["kickoff_utc"]):
        if parse_time(game["kickoff_utc"])<=issue:continue
        gid=str(game["game_id"])
        for team,opponent in ((game["home"],game["away"]),(game["away"],game["home"])):
            if (gid,team) in seen:raise ValueError("Duplicate game/team")
            seen.add((gid,team))
            qb=(game.get("verified_qb_starters") or {}).get(team)
            verified=isinstance(qb,dict) and bool(qb.get("player") and qb.get("source_url"))
            availability=[{"player":p.get("player"),"status":p.get("status"),
                           "signal_kind":p.get("signal_kind"),"source_url":p.get("source_url")}
                          for p in game.get("qb_availability_reports",[])
                          if isinstance(p,dict) and p.get("team")==team]
            relevant=[]
            for article in candidates:
                if not isinstance(article,dict) or article.get("team")!=team:
                    continue
                if article.get("status")!="UNREVIEWED_NEWS_CANDIDATE" or gid not in article.get("potential_game_ids",[]):
                    continue
                if parse_time(article["captured_at_utc"])>issue:continue
                published=article.get("published_at_utc")
                if published and parse_time(published)>issue:continue
                relevant.append({"title":article.get("title"),"source_url":article.get("source_url"),
                                 "published_at_utc":published,"status":"UNREVIEWED_NEWS_CANDIDATE"})
            feed=feeds.get(team,"UNKNOWN_FETCH_STATUS") if team in FEEDS else "NOT_CONFIGURED"
            priority=("REVIEW_QB_AVAILABILITY" if any(x["status"] not in ("AVAILABLE",None) for x in availability)
                      else "REVIEW_NEWS_CANDIDATE" if relevant else "CONFIRMED_SOURCE" if verified
                      else "UNKNOWN_NEEDS_SOURCE")
            rows.append({"game_id":gid,"kickoff_utc":game["kickoff_utc"],
                         "team":team,"opponent":opponent,"starter_status":"VERIFIED_SOURCE" if verified else "UNKNOWN",
                         "starter_player":qb.get("player") if verified else None,
                         "qb_availability":availability,"feed_status":feed,
                         "review_priority":priority,"candidate_count":len(relevant),
                         "news_candidates":relevant})
    return {"asof_utc":issue.isoformat(),"status":"QB_REVIEW_RESEARCH_ONLY",
            "rows":rows,"summary":summarize(rows),"safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED"}

def run(context_path,news_path,output_path):
    context=json.loads(Path(context_path).read_text())
    news=json.loads(Path(news_path).read_text())
    result=build_queue(context,news,dt.datetime.now(dt.timezone.utc).isoformat())
    path=Path(output_path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result["summary"]))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--context",required=True)
    p.add_argument("--news",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.context,a.news,a.output)

"""Season-wide source inventory. Never equate a source with verified player evidence."""
import argparse,csv,json
from pathlib import Path
from scripts.qb_official_news_watch import load_feed_registry

def inventory(aliases, registry=None):
    with Path(aliases).open(encoding="utf-8-sig",newline="") as stream:
        rows=list(csv.DictReader(stream))
    teams=[r["espn_display_name"].strip() for r in rows]
    if not teams or len(set(teams))!=len(teams):
        raise ValueError("Empty or duplicate canonical team names")
    feeds=load_feed_registry(registry)
    records=[{"team":t,"official_rss_url":feeds.get(t),
              "rss_configured":t in feeds,"rss_reachable":"NOT_TESTED",
              "starting_qb_verified":False,"injury_report_verified":False,
              "coverage_status":"UNKNOWN_UNTIL_GAME_SPECIFIC_EVIDENCE"}
             for t in sorted(teams)]
    missing=sorted(set(feeds)-set(teams))
    if missing:
        raise ValueError("Official RSS registry contains unmatched canonical teams: "+", ".join(missing))
    return {"season":2026,"inventory_team_count":len(records),
            "expected_fbs_team_count":138,
            "expected_count_matches":len(records)==138,
            "official_rss_configured":sum(r["rss_configured"] for r in records),
            "official_rss_unconfigured":sum(not r["rss_configured"] for r in records),
            "source_coverage_percent":round(100*sum(r["rss_configured"] for r in records)/len(records),2),
            "unmatched_registry_teams":missing,
            "source_presence_is_not_personnel_verification":True,
            "conference_reports":"GAME_SPECIFIC_SEPARATE_PIPELINE",
            "teams":records}

def run(aliases,output,registry=None,backlog=None):
    result=inventory(aliases,registry)
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    if backlog is not None:
        backlog_path=Path(backlog)
        backlog_path.parent.mkdir(parents=True,exist_ok=True)
        with backlog_path.open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=["team","official_rss_url","review_status","verification_required"])
            writer.writeheader()
            for row in result["teams"]:
                if not row["rss_configured"]:
                    writer.writerow({"team":row["team"],"official_rss_url":"",
                                     "review_status":"SOURCE_DISCOVERY_REQUIRED",
                                     "verification_required":"OFFICIAL_DOMAIN_AND_LIVE_FEED"})
    print(json.dumps({k:v for k,v in result.items() if k!="teams"}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--aliases",required=True)
    p.add_argument("--registry")
    p.add_argument("--output",required=True)
    p.add_argument("--backlog")
    a=p.parse_args()
    run(a.aliases,a.output,a.registry,a.backlog)

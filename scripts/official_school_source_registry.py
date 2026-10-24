"""Build an auditable 138-school source registry without inventing official URLs."""
import argparse,csv,json
from pathlib import Path
from scripts.qb_official_news_watch import load_feed_registry

def build(aliases,registry,discovery=None,athletics=None):
    with Path(aliases).open(newline="",encoding="utf-8-sig") as handle:
        teams=[row["espn_display_name"].strip() for row in csv.DictReader(handle)]
    if not teams or len(teams)!=len(set(teams)):
        raise ValueError("Invalid canonical team inventory")
    feeds=load_feed_registry(registry)
    unknown=set(feeds)-set(teams)
    if unknown:
        raise ValueError("Feed registry has unmatched teams: "+", ".join(sorted(unknown)))
    discovered={}
    if discovery:
        payload=json.loads(Path(discovery).read_text(encoding="utf-8"))
        if payload.get("status")!="REVIEW_REQUIRED_NOT_OFFICIAL_VERIFICATION":
            raise ValueError("Unexpected discovery evidence status")
        discovered={item["team"]:item for item in payload["teams"]}
        if set(discovered)!=set(teams):
            raise ValueError("Discovery teams differ from canonical inventory")
    sites={}
    if athletics:
        directory=json.loads(Path(athletics).read_text(encoding="utf-8"))
        if directory.get("status")!="EXTERNALLY_CROSS_REFERENCED_ATHLETICS_DIRECTORY_CANDIDATES_V1":
            raise ValueError("Unexpected athletics source registry status")
        sites={item["team"]:item for item in directory["schools"]}
        if len(sites)!=len(directory["schools"]) or set(sites)!=set(teams):
            raise ValueError("Athletics site candidates must exactly match canonical teams")
        if len({item["source_host"] for item in sites.values()})!=len(sites):
            raise ValueError("Athletics candidate hosts must be unique")
    records=[]
    for team in teams:
        hint=discovered.get(team,{})
        feed=feeds.get(team)
        site=sites.get(team,{})
        records.append({"team":team,"espn_team_id":hint.get("espn_team_id"),
            "official_rss_url":feed,"official_rss_registry_reviewed":bool(feed),
            "official_athletics_homepage":site.get("athletics_homepage"),
            "homepage_source":"EXTERNAL_DIRECTORY_CANDIDATE" if site else None,
            "homepage_verified":False,
            "game_notes_url":None,"depth_chart_url":None,"availability_url":None,
            "personnel_evidence_verified":False,
            "review_state":"HOMEPAGE_CANDIDATE_NEEDS_LIVE_CHECK" if site else "RSS_REVIEWED_HOMEPAGE_PENDING" if feed else "SOURCE_RESEARCH_REQUIRED"})
    return {"status":"PARTIAL_SOURCE_REGISTRY_REVIEW_REQUIRED","expected":len(teams),
            "official_rss_reviewed_count":sum(bool(x["official_rss_url"]) for x in records),
            "homepage_candidate_count":sum(bool(x["official_athletics_homepage"]) for x in records),
            "homepage_verified_count":0,"personnel_evidence_verified_count":0,
            "schools":records}

def run(aliases,registry,output,discovery=None,athletics=None):
    result=build(aliases,registry,discovery,athletics)
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="schools"}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--aliases",required=True)
    p.add_argument("--registry",required=True)
    p.add_argument("--discovery")
    p.add_argument("--athletics")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.aliases,a.registry,a.output,a.discovery,a.athletics)

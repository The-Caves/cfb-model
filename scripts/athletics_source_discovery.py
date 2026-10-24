"""Generate review-only athletics-site candidates for all FBS teams.

ESPN metadata is a discovery hint, NOT verification of publisher ownership,
a working RSS endpoint, a QB starter, or an injury status.
"""
import argparse,csv,json,urllib.request
from pathlib import Path

API="https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=500&groups=80"

def discover(aliases,payload):
    with Path(aliases).open(newline="",encoding="utf-8-sig") as f:
        names=[r["espn_display_name"].strip() for r in csv.DictReader(f)]
    found={}
    by_id={}
    for sport in payload.get("sports",[]):
        for league in sport.get("leagues",[]):
            for item in league.get("teams",[]):
                team=item.get("team",{})
                name=team.get("displayName")
                if name and name in names:
                    links=[x.get("href") for x in team.get("links",[]) if isinstance(x,dict) and x.get("href")]
                    found[name]={"espn_team_id":str(team.get("id","")),"espn_links":links}
    if len(names)!=len(set(names)) or not names:
        raise ValueError("Canonical team registry empty or duplicated")
    return {"status":"REVIEW_REQUIRED_NOT_OFFICIAL_VERIFICATION",
            "expected":len(names),"matched":sum(n in found for n in names),
            "unmatched":[n for n in names if n not in found],
            "match_rate_percent":round(100*sum(n in found for n in names)/len(names),2),
            "teams":[{"team":n,**found.get(n,{"espn_team_id":None,"espn_links":[]}),
                      "official_athletics_domain":None,"official_feed_url":None,
                      "source_verified":False} for n in names]}

def run(aliases,output,payload=None):
    if payload:
        data=json.loads(Path(payload).read_text())
    else:
        req=urllib.request.Request(API,headers={"User-Agent":"cfb-model-research/0.2"})
        with urllib.request.urlopen(req,timeout=25) as response:
            data=json.load(response)
    result=discover(aliases,data)
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="teams"}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--aliases",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--payload")
    args=p.parse_args()
    run(args.aliases,args.output,args.payload)

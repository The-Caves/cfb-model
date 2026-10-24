"""Merge live connectivity evidence into school source registry without implying QB evidence."""
import argparse,json
from pathlib import Path
from urllib.parse import urlsplit

def merge(registry,connectivity):
    if registry.get("expected")!=len(registry.get("schools",[])):
        raise ValueError("Invalid school source registry")
    checks=connectivity.get("athletics_homepages")
    if not isinstance(checks,list):
        raise ValueError("No athletics homepage probe results")
    by_team={row["team"]:row for row in checks}
    if len(by_team)!=len(checks) or set(by_team)!={r["team"] for r in registry["schools"]}:
        raise ValueError("Probe coverage must match all canonical schools")
    for school in registry["schools"]:
        check=by_team[school["team"]]
        if check["url"]!=school["official_athletics_homepage"]:
            raise ValueError("Source probe URL mismatch: "+school["team"])
        school["homepage_reachable"]=bool(check["reachable"])
        school["homepage_connectivity_status"]="REACHABLE_NOT_OWNERSHIP_VERIFIED" if check["reachable"] else "UNREACHABLE_OR_BLOCKED"
        school["homepage_verified"]=False
        school["personnel_evidence_verified"]=False
    registry["homepage_reachable_count"]=sum(r["homepage_reachable"] for r in registry["schools"])
    registry["homepage_unreachable_or_blocked_count"]=len(registry["schools"])-registry["homepage_reachable_count"]
    registry["status"]="SOURCE_CANDIDATES_WITH_CONNECTIVITY_AUDIT_NOT_PERSONNEL_VERIFIED"
    registry["connectivity_checked_at_utc"]=connectivity.get("checked_at_utc")
    return registry

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True);p.add_argument("--connectivity",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    result=merge(json.loads(Path(a.registry).read_text()),json.loads(Path(a.connectivity).read_text()))
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="schools"}))

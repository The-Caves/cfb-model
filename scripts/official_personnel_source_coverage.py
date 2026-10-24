"""Validate per-school official football source coverage and expose unresolved gaps."""
import argparse,csv,json
from pathlib import Path

CATEGORIES=("game_notes","depth_chart","injury_report")
STATES=("CANDIDATES_FOUND_REVIEW_REQUIRED","NO_CANDIDATE_LOCATED",
        "CRAWL_INCOMPLETE")

def evaluate(data):
    schools=data.get("schools",[])
    if data.get("expected_teams")!=138 or len(schools)!=138:
        raise ValueError("Coverage audit must include 138 canonical teams")
    if len({x["team"] for x in schools})!=138:
        raise ValueError("Duplicate canonical team")
    rows=[]
    for school in schools:
        row={"team":school["team"],"football_page":school.get("football_page"),
             "crawl_status":school.get("crawl_status"),
             "game_specific_player_evidence_verified":False}
        for category in CATEGORIES:
            candidates=school.get(category,[])
            if not isinstance(candidates,list):raise ValueError("Invalid source candidates")
            if any(x.get("game_specific_evidence_verified") for x in candidates):
                raise ValueError("Unreviewed discovery cannot promote player evidence")
            row[category+"_candidate_count"]=len(candidates)
            row[category+"_status"]=(
                "CRAWL_INCOMPLETE" if school.get("crawl_status")!="AUDITED" else
                "CANDIDATES_FOUND_REVIEW_REQUIRED" if candidates else
                "NO_CANDIDATE_LOCATED")
            row[category+"_candidate_urls"]=[x["url"] for x in candidates]
        rows.append(row)
    counts={c:{state:sum(r[c+"_status"]==state for r in rows) for state in STATES}
            for c in CATEGORIES}
    unresolved=[{"team":r["team"],"football_page":r["football_page"],
                 "missing_candidate_types":[c for c in CATEGORIES if r[c+"_candidate_count"]==0],
                 "crawl_status":r["crawl_status"]} for r in rows
                if r["crawl_status"]!="AUDITED" or any(r[c+"_candidate_count"]==0 for c in CATEGORIES)]
    return {"status":"SOURCE_TYPE_DISCOVERY_AUDIT_NOT_PERSONNEL_VERIFICATION",
            "expected_teams":138,"schools_audited":sum(r["crawl_status"]=="AUDITED" for r in rows),
            "source_type_counts":counts,"personnel_verified_count":0,
            "missing_source_not_equivalent_to_unpublished":True,
            "source_type_review_backlog_count":len(unresolved),
            "source_type_review_backlog":unresolved,"schools":rows}

def run(source,output,csv_output=None):
    report=evaluate(json.loads(Path(source).read_text(encoding="utf-8")))
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    if csv_output:
        target=Path(csv_output);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open("w",encoding="utf-8",newline="") as f:
            fields=["team","football_page","crawl_status"]+[c+"_status" for c in CATEGORIES]+[c+"_candidate_count" for c in CATEGORIES]
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
            writer.writeheader();writer.writerows(report["schools"])
    print(json.dumps({k:v for k,v in report.items() if k not in ("schools","source_type_review_backlog")}))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True);p.add_argument("--output",required=True)
    p.add_argument("--csv-output")
    a=p.parse_args();run(a.source,a.output,a.csv_output)

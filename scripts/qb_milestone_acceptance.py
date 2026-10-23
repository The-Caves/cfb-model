"""Conservative acceptance report for real-game QB discovery and evidence coverage."""
import argparse,json
from pathlib import Path

def assess(news,queue,coverage):
    meta=news["manifest"]; summary=queue["summary"]; cov=coverage["summary"]
    if news.get("betting_status")!="PASS_UNVALIDATED" or queue.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Untrusted source reports")
    if meta["status"]!="OFFICIAL_NEWS_REVIEW_ONLY" or coverage["status"]!="STEP3H_PERSONNEL_COVERAGE_RESEARCH_ONLY":
        raise ValueError("Invalid audit status")
    slots=cov["team_slots"]
    if summary["team_game_slots"]!=slots:
        raise ValueError("Review queue and coverage audit disagree")
    missing=meta["unconfigured_upcoming_team_slots"]
    verified=cov["reviewed_qb_slots"]
    checks={"audit_integrity":True,
            "all_upcoming_teams_have_official_discovery_source":missing==0,
            "all_configured_feeds_read_successfully":meta["feeds_failed"]==0,
            "verified_starters_exist":verified>0,
            "every_upcoming_starter_verified":slots>0 and verified==slots}
    return {"status":"QB_MILESTONE_ACCEPTANCE","ready_for_milestone_2":all(checks.values()),
            "checks":checks,"observed":{"upcoming_team_slots":slots,
                "reviewed_qb_slots":verified,"qb_coverage_fraction":cov["qb_coverage_fraction"],
                "feeds_configured":meta["feeds_configured"],"feeds_read":meta["feeds_read"],
                "feeds_failed":meta["feeds_failed"],
                "unconfigured_upcoming_team_slots":missing,
                "candidate_articles":meta["candidate_count"]},
            "notes":"Zero coverage or unavailable sources must remain UNKNOWN; RSS candidate mentions are never starter confirmations.",
            "betting_status":"PASS_UNVALIDATED"}

def main():
    p=argparse.ArgumentParser()
    for name in ("news","queue","coverage","output"):p.add_argument("--"+name,required=True)
    a=p.parse_args()
    report=assess(*[json.loads(Path(getattr(a,n)).read_text()) for n in ("news","queue","coverage")])
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report["observed"]))

if __name__=="__main__":main()

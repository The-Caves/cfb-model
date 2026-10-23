"""Fail-closed quarterback readiness assessment for frozen prospective forecasts.

This module never infers starters from rosters, news mentions, or availability.
It measures verified evidence and explicitly blocks a verified-personnel label
when either team lacks reviewed game-specific starting-QB evidence.
"""
import argparse
import json
from pathlib import Path
from scripts.personnel_forecast import verify

def assess(record):
    verify(record)
    games=[]
    for g in record["games"]:
        count=g["reported_qb_coverage"]
        if not isinstance(count,int) or not 0<=count<=2:
            raise ValueError("Invalid reviewed QB evidence count")
        verified=count==2
        games.append({"game_id":g["game_id"],"home":g["home"],"away":g["away"],
                      "kickoff_utc":g["kickoff_utc"],"reviewed_qb_slots":count,
                      "missing_qb_slots":2-count,
                      "status":"QB_BOTH_CONFIRMED" if verified else "QB_EVIDENCE_INCOMPLETE",
                      "personnel_ready":verified,
                      "prediction_status":"PASS_QB_UNVERIFIED" if not verified else "RESEARCH_ONLY"})
    n=len(games)
    full=sum(g["personnel_ready"] for g in games)
    return {"status":"QB_READINESS_AUDIT","forecast_observed_utc":record["forecast_observed_utc"],
            "summary":{"games":n,"both_qbs_confirmed_games":full,
                       "games_with_unverified_qbs":n-full,
                       "qb_slot_coverage_fraction":round(sum(g["reviewed_qb_slots"] for g in games)/(2*n),5) if n else None,
                       "fully_confirmed_fraction":round(full/n,5) if n else None},
            "games":games,"safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--forecast",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    record=json.loads(Path(a.forecast).read_text())["record"]
    report=assess(record)
    dest=Path(a.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report["summary"]))

if __name__=="__main__":
    main()

"""Export observed injury evidence as a triage CSV, without inventing statuses."""
import argparse
import csv
import json
from pathlib import Path
from scripts.injury_history import verify_observation

FIELDS=("game_id","kickoff_utc","team","opponent","coverage_status",
        "player","position","reported_status","published_at_utc",
        "source_url","review_priority","quarantined_count")

def export(snapshot, destination):
    verify_observation(snapshot)
    rows=[]
    for slot in snapshot["rows"]:
        common={k:slot[k] for k in ("game_id","kickoff_utc","team","opponent","coverage_status")}
        quarantined=len(slot["quarantined_evidence"])
        if not slot["reported_players"]:
            rows.append({**common,"player":"","position":"","reported_status":"UNKNOWN",
                         "published_at_utc":"","source_url":"",
                         "review_priority":"REVIEW_QUARANTINED" if quarantined else "MISSING_VERIFIED_REPORT",
                         "quarantined_count":quarantined})
        for player in slot["reported_players"]:
            status=player["reported_status"]
            priority=("REVIEW_QB" if player["position"]=="QB" and status!="AVAILABLE"
                      else "REVIEW_OUT_OR_DOUBTFUL" if status in ("OUT","DOUBTFUL","SUSPENDED")
                      else "REVIEW_UNCERTAIN" if status in ("QUESTIONABLE","GAME_TIME_DECISION","LIMITED","UNKNOWN")
                      else "REPORTED_STATUS")
            rows.append({**common,"player":player["player"],"position":player["position"],
                         "reported_status":status,"published_at_utc":player["published_at_utc"],
                         "source_url":player["source_url"],"review_priority":priority,
                         "quarantined_count":quarantined})
    path=Path(destination)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return {"rows":len(rows),"unknown_team_slots":sum(
        r["coverage_status"]=="UNKNOWN" for r in snapshot["rows"])}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    print(json.dumps(export(json.loads(Path(args.snapshot).read_text()),args.output)))

"""Export a verified archived prospective forecast into a minimal static-site snapshot.

No network requests, sportsbook lines, user data, or retrospective picks.
A forecast can only be published when its original observation predates kickoff.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from scripts.personnel_forecast import verify
from scripts.game_context import parse_time

def export(record, generated_at_utc):
    verify(record)
    generated=parse_time(generated_at_utc)
    rows=[]
    for g in record["games"]:
        observed=parse_time(g["forecast_observed_utc"])
        kickoff=parse_time(g["kickoff_utc"])
        if observed>=kickoff:
            raise ValueError("Refusing forecast captured at or after kickoff")
        p=g["projection"]
        margin=p["predicted_home_margin"]
        total=p["predicted_total_points"]
        if (margin is None)!=(total is None):
            raise ValueError("Partial projection is not publishable")
        rows.append({
            "game_id":g["game_id"],"away_team":g["away"],"home_team":g["home"],
            "kickoff_utc":g["kickoff_utc"],
            "forecast_observed_utc":g["forecast_observed_utc"],
            "model_home_margin":margin,"model_total":total,
            "market_home_spread":None,
            "prediction_status":p["prediction_status"],
            "qb_coverage":g["reported_qb_coverage"],
            "injury_report_coverage":g["verified_team_report_coverage"]})
    return {
        "schema_version":1,
        "generated_at_utc":generated.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z"),
        "forecast_observed_utc":record["forecast_observed_utc"],
        "model":record["model_training"]["model"],
        "research_only":True,
        "market_status":"NOT_CAPTURED",
        "games":rows,
        "prospective_records":{}
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--forecast",required=True,help="Existing verified immutable forecast JSON")
    p.add_argument("--output",required=True)
    args=p.parse_args()
    payload=json.loads(Path(args.forecast).read_text(encoding="utf-8"))
    record=payload.get("record",payload)
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    result=export(record,now)
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":"RESEARCH_SITE_EXPORT","games":len(result["games"]),
                      "market_quotes_exported":0,"betting_status":"PASS_UNVALIDATED"}))

if __name__=="__main__":
    main()

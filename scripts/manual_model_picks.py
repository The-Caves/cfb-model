"""Select requested matchups from a current research forecast."""
import argparse
import json
from pathlib import Path
from scripts.personnel_forecast import verify

def select(record, requested):
    verify(record)
    tokens=[x.strip() for x in requested.splitlines() if x.strip()]
    if not tokens or len(tokens)>30:
        raise ValueError("Enter between 1 and 30 matchups")
    output=[]
    for token in tokens:
        key=token.casefold()
        matches=[g for g in record["games"] if
                 str(g["game_id"])==token or
                 key in (f'{g["away"]} at {g["home"]}'.casefold(),
                         f'{g["away"]} vs {g["home"]}'.casefold())]
        if len(matches)!=1:
            raise ValueError(f"Matchup {token!r} matched {len(matches)} games; use exact team names or ESPN game ID")
        g=matches[0]
        if g["game_id"] in {r["game_id"] for r in output}:
            raise ValueError("Duplicate selected game")
        p=g["projection"]
        margin=p["predicted_home_margin"]
        output.append({"game_id":g["game_id"],"away":g["away"],"home":g["home"],
                       "kickoff_utc":g["kickoff_utc"],
                       "pick":g["home"] if margin is not None and margin>0 else
                       g["away"] if margin is not None and margin<0 else None,
                       "home_points":p["predicted_home_points"],
                       "away_points":p["predicted_away_points"],
                       "home_margin":margin,"total":p["predicted_total_points"],
                       "home_win_probability":p["research_home_win_probability"],
                       "prediction_status":p["prediction_status"],
                       "qb_coverage":g["reported_qb_coverage"],
                       "report_coverage":g["verified_team_report_coverage"]})
    return {"status":"UNVALIDATED_RESEARCH_PICKS",
            "forecast_observed_utc":record["forecast_observed_utc"],
            "model":record["model_training"]["model"],
            "games":output,"betting_status":"PASS_UNVALIDATED"}

def run(forecast,requested,out):
    record=json.loads(Path(forecast).read_text())["record"]
    report=select(record,requested)
    dest=Path(out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2)+"\n")
    lines=["# Requested model picks (unvalidated research)","",
           "Forecast: "+report["forecast_observed_utc"],"",
           "| Game | Winner | Away score | Home score | Home margin | Total | Home win probability |",
           "|---|---|---:|---:|---:|---:|---:|"]
    for g in report["games"]:
        fmt=lambda v:"PASS" if v is None else str(round(v,2))
        lines.append(f'| {g["away"]} at {g["home"]} | {g["pick"] or "PASS"} | '
                     f'{fmt(g["away_points"])} | {fmt(g["home_points"])} | '
                     f'{fmt(g["home_margin"])} | {fmt(g["total"])} | '
                     f'{fmt(g["home_win_probability"])} |')
    lines.append("\nNo verified sportsbook lines; not validated for betting.")
    dest.with_suffix(".md").write_text("\n".join(lines)+"\n")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--forecast",required=True)
    p.add_argument("--requested",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.forecast,a.requested,a.output)

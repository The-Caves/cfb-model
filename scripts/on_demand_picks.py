"""Fast, read-only matchup report from latest immutable prospective model forecast."""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from scripts import context_archive as store
from scripts.personnel_forecast import INDEX, verify

def norm(s):
    s=str(s).casefold().replace("&","and")
    s=re.sub(r"[^a-z0-9]+"," ",s).strip()
    return " ".join(s.split())

ALIASES={"jmu":"james madison","app state":"appalachian state",
         "appalachian st":"appalachian state","ecu":"east carolina",
         "kennesaw st":"kennesaw state","memphis tigers":"memphis"}

def team(s):
    n=norm(s)
    return ALIASES.get(n,n)

def choose(record, requests, now=None):
    verify(record)
    now=now or dt.datetime.now(dt.timezone.utc)
    out=[]
    for line in requests.splitlines():
        raw=line.strip()
        if not raw:continue
        parts=re.split(r"\s+(?:at|@|vs\.?|versus)\s+",raw,flags=re.I)
        matches=[]
        for g in record["games"]:
            if raw==str(g["game_id"]) or (len(parts)==2 and
                team(parts[0])==team(g["away"]) and team(parts[1])==team(g["home"])):
                matches.append(g)
        if len(matches)!=1:
            out.append({"requested":raw,"status":"NOT_FOUND_OR_AMBIGUOUS",
                        "reason":"Not present in this archived forecast; could be a name alias, outside its horizon, or already kicked off"})
            continue
        g=matches[0]
        kickoff=dt.datetime.fromisoformat(g["kickoff_utc"].replace("Z","+00:00"))
        if kickoff<=now:
            out.append({"requested":raw,"status":"KICKOFF_PASSED",
                        "kickoff_utc":g["kickoff_utc"]})
            continue
        p=g["projection"]
        m=p["predicted_home_margin"]
        out.append({"requested":raw,"status":p["prediction_status"],
                    "game_id":g["game_id"],"kickoff_utc":g["kickoff_utc"],
                    "home":g["home"],"away":g["away"],
                    "winner":g["home"] if m is not None and m>0 else g["away"] if m is not None and m<0 else None,
                    "predicted_home_points":p["predicted_home_points"],
                    "predicted_away_points":p["predicted_away_points"],
                    "home_margin":m,"total":p["predicted_total_points"],
                    "research_home_win_probability":p["research_home_win_probability"],
                    "qb_coverage":g["reported_qb_coverage"],
                    "team_report_coverage":g["verified_team_report_coverage"]})
    if not out:raise ValueError("No requested matchups")
    return {"status":"ARCHIVED_PROSPECTIVE_RESEARCH_REPORT",
            "forecast_observed_utc":record["forecast_observed_utc"],
            "model":record["model_training"].get("model"),
            "betting_status":"PASS_UNVALIDATED",
            "warning":"Existing archived research forecast, not a new model fit; no verified market odds, no betting validation",
            "games":out}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--request",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    idx=store.get_blob_file(INDEX)
    if idx is None:raise ValueError("No archived forecast index")
    runs=json.loads(idx)["runs"]
    if not runs:raise ValueError("No archived forecasts")
    # Prefer newest verified archive; never modify the frozen forecast.
    record=store.unpack(store.get_blob_file(runs[-1]["path"]))
    report=choose(record,Path(a.request).read_text())
    path=Path(a.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+"\n")
    lines=["# On-demand CFB model research report","",
           "Forecast originally captured: "+report["forecast_observed_utc"],"",
           "| Requested game | Status | Winner | Away points | Home points | Home margin | Total |",
           "|---|---|---|---:|---:|---:|---:|"]
    for g in report["games"]:
        fmt=lambda v: "—" if v is None else str(round(v,2))
        lines.append("| "+g["requested"]+" | "+g["status"]+" | "+
                     str(g.get("winner") or "—")+" | "+
                     fmt(g.get("predicted_away_points"))+" | "+
                     fmt(g.get("predicted_home_points"))+" | "+
                     fmt(g.get("home_margin"))+" | "+
                     fmt(g.get("total"))+" |")
    lines.extend(["","Unvalidated research projections. No sportsbook spreads or totals were ingested."])
    path.with_suffix(".md").write_text("\n".join(lines)+"\n")
    print(json.dumps({"status":report["status"],"games":len(report["games"])}))

if __name__=="__main__":
    main()

"""Export only checksum-verified, pre-kickoff, research model projections."""
import argparse,datetime as dt,gzip,json
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.personnel_forecast import STATUS,checksum,t,verify
INDEX=Path("research_2026/forecast_index.json")

def export_record(record,entry,now):
    verify(record)
    if str(record["run_id"])!=str(entry["run_id"]) or checksum(record)!=entry["forecast_sha256"]:
        raise ValueError("Frozen forecast checksum/identity mismatch")
    observed=t(record["forecast_observed_utc"])
    if observed!=t(entry["forecast_observed_utc"]) or observed>now:
        raise ValueError("Invalid observation timestamp")
    if entry.get("actual_market_quotes")!=0:
        raise ValueError("Do not publish private sportsbook quotes")
    games=[]
    for g in record["games"]:
        if t(g["kickoff_utc"])<=now:continue
        p=g["projection"]
        if (g["betting_status"]!="PASS_UNVALIDATED" or g["safe_for_betting"] is not False or
            g["market"]["actual_quote_count"]!=0):
            raise ValueError("Unexpected market/betting clearance")
        games.append({
            "game_id":g["game_id"],"away_team":g["away"],"home_team":g["home"],
            "kickoff_utc":g["kickoff_utc"],"model_home_margin":p["predicted_home_margin"],
            "model_total":p["predicted_total_points"],"model_home_points":p["predicted_home_points"],
            "model_away_points":p["predicted_away_points"],
            "research_home_win_probability":p["research_home_win_probability"],
            "prediction_status":p["prediction_status"],
            "qb_starters_verified":g["reported_qb_coverage"],
            "official_team_reports_verified":g["verified_team_report_coverage"],
            "market_home_spread":None,"market_total":None,
            "policy_24_to_72h_eligible":g["policy_24_to_72h_eligible"]})
    games.sort(key=lambda g:(g["kickoff_utc"],g["game_id"]))
    return {"schema_version":2,"status":"FROZEN_RESEARCH_PROJECTIONS_NOT_BETTING_PICKS",
        "betting_status":"PASS_UNVALIDATED","generated_at_utc":now.isoformat(),
        "forecast_observed_utc":record["forecast_observed_utc"],
        "forecast_run_id":record["run_id"],"forecast_sha256":entry["forecast_sha256"],
        "model":record["model_training"]["model"],
        "data_limitations":["Not validated for betting; win probabilities are uncalibrated.",
            "2026 historical PBP publication timing remains unverified.",
            "Official QB and availability coverage remain incomplete.",
            "No verified sportsbook spreads or totals; ATS/O-U edges unavailable."],
        "prospective_records":{"su":None,"ats":None,"ou":None},"games":games}

def read_latest(root):
    idx=json.loads((root/INDEX).read_text())
    if idx.get("season")!=2026 or idx.get("status")!=STATUS or idx.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Wrong model index")
    runs=idx.get("runs",[])
    if not runs:raise ValueError("No archived forecast")
    entry=runs[-1]
    path=Path(entry.get("path",""))
    if (path.is_absolute() or ".." in path.parts or len(path.parts)!=6 or
        path.parts[:2]!=("research_2026","forecasts") or path.suffixes!=[".json",".gz"]):
        raise ValueError("Invalid forecast path")
    return json.loads(gzip.decompress((root/path).read_bytes())),entry

def run(root,output,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    record,entry=read_latest(Path(root))
    result=export_record(record,entry,now)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    zone=ZoneInfo("America/New_York")
    print(json.dumps({"forecast_run_id":result["forecast_run_id"],"future_games":len(result["games"]),
        "today_et":sum(t(g["kickoff_utc"]).astimezone(zone).date()==now.astimezone(zone).date() for g in result["games"]),
        "numeric_projections":sum(g["model_home_margin"] is not None for g in result["games"]),
        "status":result["betting_status"]}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.archive_root,a.output)

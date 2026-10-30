"""Paired no-vig market vs source-frozen CFB player-prop probability research.

Only independently observed, complete pre-kickoff bookmaker market pairs and
verified player IDs. A SHA over JSON detects edits but DOES NOT by itself prove
a GitHub archival timestamp; promotion always remains blocked.
No DNP/no-stat zero inference or invented final settlement. Pushes excluded
from binary Brier/log-loss. Compare on the same settled prop cohort.
"""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from scripts.game_context import parse_time
from scripts.player_prop_history import STATS

STATUS="PROSPECTIVE_PLAYER_PROP_PAIRED_GRADE_RESEARCH_ONLY"
FORECAST_STATUS="FROZEN_PREKICKOFF_PLAYER_PROP_PROBABILITY_RESEARCH_ONLY"
FINAL_STATUS="OBSERVED_OFFICIAL_PLAYER_PROP_FINAL_RESEARCH_ONLY"

def digest(row):
    return hashlib.sha256(json.dumps({k:v for k,v in row.items()
        if k!="record_sha256"},sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def _num(x):
    return type(x) in (int,float) and math.isfinite(x)

def _url(s):
    try:
        u=urlsplit(s)
        return u.scheme=="https" and bool(u.hostname)
    except (ValueError,TypeError):return False

def _p(p):
    if not _num(p) or not 0<=p<=1:raise ValueError("Invalid forecast probability")
    return p

def _validate_frozen(row,now):
    if row.get("status")!=FORECAST_STATUS or row.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Untrusted research forecast")
    if row.get("record_sha256")!=digest(row):
        raise ValueError("Edited frozen prop record")
    if (not row.get("model_version") or not row.get("player_id")
        or row.get("metric") not in STATS or not row.get("game_id")
        or not row.get("bookmaker") or not row.get("quote_sha256")
        or len(row["quote_sha256"])!=64 or not _num(row.get("line"))):
        raise ValueError("Incomplete athlete/line/model identity")
    kickoff=parse_time(row["kickoff_utc"])
    issue=parse_time(row["issued_at_utc"])
    archive=parse_time(row["archive_observed_at_utc"])
    quote=parse_time(row["quote_observed_at_utc"])
    if not quote<=issue<=archive<kickoff or archive>now:
        raise ValueError("Forecast/market not independently archived prior to kickoff")
    _p(row["over_probability"])
    _p(row["bookmaker_over_no_vig"])
    if row.get("probabilities_conditional_on_playing") is not True:
        raise ValueError("Availability-conditioned research forecast required")

def _validate_final(row,now):
    if row.get("status")!=FINAL_STATUS or not row.get("game_id") or (
        not row.get("player_id") or row.get("metric") not in STATS or
        not _num(row.get("actual")) or not _url(row.get("source_url"))):
        raise ValueError("Unobserved or invalid player final")
    if not (parse_time(row["kickoff_utc"])<parse_time(row["observed_at_utc"])<=now):
        raise ValueError("Future or pregame final")
    if row.get("stat_category_recorded") is not True or row.get("participation_verified") is not True:
        raise ValueError("Do not treat missing category as observed zero")

def evaluate(forecasts,finals,evaluated_at_utc,min_pairs=50):
    now=parse_time(evaluated_at_utc)
    if type(min_pairs) is not int or min_pairs<2:raise ValueError("Invalid cohort threshold")
    actual={};counts=defaultdict(int)
    for row in finals:
        _validate_final(row,now)
        key=(str(row["game_id"]),str(row["player_id"]),row["metric"])
        if key in actual:raise ValueError("Duplicate official player final")
        actual[key]=row
    seen=set();baseline={};records=defaultdict(list)
    versions=set()
    for row in forecasts:
        _validate_frozen(row,now)
        key=(str(row["game_id"]),str(row["player_id"]),row["metric"],row["bookmaker"],
             float(row["line"]),row["quote_sha256"])
        ident=key+(row["model_version"],)
        if ident in seen:raise ValueError("Duplicate frozen model/prop")
        seen.add(ident);versions.add(row["model_version"])
        old=baseline.setdefault(key,row["bookmaker_over_no_vig"])
        if abs(old-row["bookmaker_over_no_vig"])>1e-7:
            raise ValueError("Inconsistent bookmaker quote across models")
        final=actual.get(key[:3])
        if not final:
            counts["NO_OFFICIAL_RECORDED_STAT_FINAL"]+=1
            continue
        if parse_time(final["kickoff_utc"])!=parse_time(row["kickoff_utc"]):
            raise ValueError("Bookmaker and actual ESPN game time disagree")
        if final["actual"]==row["line"]:
            counts["PUSH_EXCLUDED_FROM_BINARY_GRADE"]+=1
            continue
        label=int(final["actual"]>row["line"])
        forecast=row["over_probability"]
        market=row["bookmaker_over_no_vig"]
        eps=1e-8
        records[row["model_version"]].append({
            "game_id":key[0],"player_id":key[1],"metric":key[2],
            "bookmaker":key[3],"line":key[4],
            "actual":final["actual"],"over_won":label,
            "over_probability":forecast,"market_no_vig_over":market,
            "model_brier":(forecast-label)**2,
            "market_brier":(market-label)**2,
            "model_log_loss":-(label*math.log(max(eps,forecast))+
                               (1-label)*math.log(max(eps,1-forecast))),
            "market_log_loss":-(label*math.log(max(eps,market))+
                               (1-label)*math.log(max(eps,1-market))),
            "forecast_sha256":row["record_sha256"],
        })
    score={}
    for version in sorted(versions):
        rows=records[version];n=len(rows)
        def avg(field):return round(sum(x[field] for x in rows)/n,6) if n else None
        a=avg("model_brier");b=avg("market_brier")
        l1=avg("model_log_loss");l2=avg("market_log_loss")
        score[version]={
            "status":"SUFFICIENT_RESEARCH_GRADED_PAIRS_FOR_REVIEW" if n>=min_pairs
                     else "INSUFFICIENT_PROSPECTIVE_GRADED_PAIRS",
            "graded_nonpush_props":n,"model_brier":a,"market_no_vig_brier":b,
            "paired_brier_delta":round(a-b,6) if n else None,
            "model_log_loss":l1,"market_no_vig_log_loss":l2,
            "paired_log_loss_delta":round(l1-l2,6) if n else None,
            "grade_records":rows,"promotion_eligible":False,
        }
    return {"status":STATUS,"evaluated_at_utc":now.isoformat(),
        "source_recorded_finals":len(actual),
        "versions":score,"unsettled_or_push":dict(counts),
        "cross_model_comparisons_require_identical_prop_cohorts":True,
        "independent_external_archive_timestamp_authenticated":False,
        "player_availability_conditional_and_unverified":True,
        "actual_bet_returns_calculated":False,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

def run(forecasts,finals,decision,out):
    rows=json.loads(Path(forecasts).read_text(encoding="utf-8"))
    actual=json.loads(Path(finals).read_text(encoding="utf-8"))
    r=evaluate(rows,actual,decision)
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(r,indent=2,allow_nan=False)+"\n")
    return r

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--forecasts",required=True);p.add_argument("--finals",required=True)
    p.add_argument("--asof",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.forecasts,a.finals,a.asof,a.output)

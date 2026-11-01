"""Publish check-summed prospective CFB performance from observed archived evidence.

SU is the strict frozen Step3G 24–72-hour forecast scorecard. ATS/totals
are separate, FIRST AS-DISPLAYED research market decisions; lines may have
been observed after the model forecast, but all site captures predate kickoff.
Never add the two policies together, treat duplicate page loads as games, or
call research selections wagers/ROI.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import context_archive as store
from scripts.game_context import parse_time
from scripts.market_finals_archive import verify as verify_final_index
from scripts.personnel_forecast_grade import verify_prior_grade
from scripts.site_decision_archive import STATUS as BOARD_STATUS
from scripts.weekly_profiles import canonical
from scripts.v04_market_challenger import (
    decide as v04_decide, POLICY as V04_POLICY, STATUS as V04_STATUS)
from scripts.v04_direct_scores import MODEL as V04_SCORE_MODEL, STATUS as V04_SCORE_STATUS

GRADE_INDEX="research_2026/forecast_grades_index.json"
BOARD_INDEX="research_2026/site_board_snapshots/index.json"
FINAL_INDEX="research_2026/market_finals/index.json"
GRADE_PATTERN=r"research_2026/forecast_grades/(?:2026/\d{2}|2027/01)/\d{2}/\d+\.json\.gz"
BOARD_PATTERN=r"research_2026/site_board_snapshots/2026/\d{2}/\d{2}/run-\d+\.json\.gz"
FINAL_PATTERN=r"research_2026/market_finals/\d+\.json\.gz"
EASTERN=ZoneInfo("America/New_York")

def _file(root,path,pattern=None):
    if not isinstance(path,str) or (pattern is not None and re.fullmatch(pattern,path) is None):
        raise ValueError("Unsafe archived performance path")
    p=root/path
    if not p.is_file():raise ValueError("Missing archived performance evidence: "+path)
    return p.read_bytes()

def _json(root,path):
    return json.loads(_file(root,path).decode("utf-8"))

def _packed(root,path,pattern,sha,canonical_digest=False):
    blob=_file(root,path,pattern)
    if len(blob)>8_000_000:raise ValueError("Unbounded compressed evidence")
    data=json.loads(gzip.decompress(blob))
    if hashlib.sha256(canonical(data) if canonical_digest else store.encode(data)).hexdigest()!=sha:
        raise ValueError("Archived performance checksum mismatch: "+path)
    return data

def _stats(values):
    c=Counter(values)
    if set(c)-{"WIN","LOSS","PUSH"}:raise ValueError("Unknown grade")
    n=c["WIN"]+c["LOSS"]
    return {"wins":c["WIN"],"losses":c["LOSS"],"pushes":c["PUSH"],
            "decisions":n,"win_rate":round(c["WIN"]/n,5) if n else None}

def _week(kickoff):
    return parse_time(kickoff).astimezone(EASTERN).date().isocalendar()
def _label(kickoff):
    d=parse_time(kickoff).astimezone(EASTERN).date()
    return d.isoformat()+" ("+d.strftime("%a")+")"

def compute(root,now=None):
    root=Path(root)
    now=parse_time(now) if isinstance(now,str) else (now or dt.datetime.now(dt.timezone.utc))
    grade_index=_json(root,GRADE_INDEX)
    if (grade_index.get("season")!=2026 or grade_index.get("status")!=
            "STEP3G_OBSERVED_PROSPECTIVE_GRADING_RESEARCH_ONLY"
        or grade_index.get("safe_for_betting") is not False or
        grade_index.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Unverified Step3G grade index")
    grades={}
    for gid,entry in grade_index["games"].items():
        if not gid.isdigit():raise ValueError("Invalid grade game ID")
        grades[entry["path"]]=_packed(root,entry["path"],GRADE_PATTERN,entry["grade_sha256"],True)
    verify_prior_grade(grade_index,grades)

    su=[];su_by_week=defaultdict(list);margin_errors=[];total_errors=[]
    rows={}
    for gid,entry in grade_index["games"].items():
        record=grades[entry["path"]]
        if parse_time(record["final_observed_at_utc"])>now:continue
        if record["su_correct"] is not None:
            grade="WIN" if record["su_correct"]==1 else "LOSS"
            su.append(grade);su_by_week[_week(record["kickoff_utc"])].append(grade)
        else:grade=None
        margin_errors.append(record["margin_abs_error"])
        total_errors.append(record["total_abs_error"])
        rows[gid]={"game_id":gid,"home":record["home"],"away":record["away"],
                   "kickoff_utc":record["kickoff_utc"],
                   "score":str(record["actual_away_score"])+"–"+str(record["actual_home_score"]),
                   "su":grade,"ats":None,"ou":None,
                   "forecast_model":record["forecast_model"]}

    finals_index=_json(root,FINAL_INDEX)
    verify_final_index(finals_index)
    finals={}
    for gid,entry in finals_index["games"].items():
        final=_packed(root,entry["path"],FINAL_PATTERN,entry["sha256"])
        if (final.get("status")!="OBSERVED_INDEPENDENT_MARKET_FINAL" or
            final.get("betting_status")!="PASS_UNVALIDATED" or
            final.get("safe_for_betting") is not False or
            str(final.get("game_id"))!=gid or
            any(final.get(k)!=entry.get(k) for k in ("home","away","kickoff_utc","home_score","away_score")) or
            parse_time(final["kickoff_utc"])>=parse_time(final["outcome_known_at_utc"]) or
            parse_time(final["outcome_known_at_utc"])>parse_time(final["observed_at_utc"]) or
            len(final.get("scoreboard_sha256",""))!=64):
            raise ValueError("Invalid independent final record")
        if parse_time(final["observed_at_utc"])<=now:finals[gid]=final

    board_index=_json(root,BOARD_INDEX)
    if (board_index.get("status")!=BOARD_STATUS or board_index.get("schema_version")!=1
            or not isinstance(board_index.get("runs"),list)):
        raise ValueError("Invalid archived website snapshot index")
    first={};first_v04={};seen_runs=set();raw=Counter();mismatches=0;observed_games=set()
    for item in board_index["runs"]:
        runid=str(item["run_id"])
        if not runid.isdigit() or runid in seen_runs:raise ValueError("Repeated board run")
        seen_runs.add(runid)
        board=_packed(root,item["path"],BOARD_PATTERN,item["sha256"])
        captured=parse_time(board["capture_utc"])
        if (board.get("status")!=BOARD_STATUS or board.get("schema_version")!=1
            or board.get("betting_status")!="PASS_UNVALIDATED"
            or board.get("not_an_executed_bet") is not True
            or str(board["dashboard_run_id"])!=runid
            or board["capture_utc"]!=item["capture_utc"]
            or board.get("summary",{}).get("future_games")!=len(board.get("rows",[]))
            or captured>now):
            raise ValueError("Invalid archived as-displayed market board")
        if item["path"]!=("research_2026/site_board_snapshots/"+
                         captured.strftime("%Y/%m/%d")+"/run-"+runid+".json.gz"):
            raise ValueError("Market board index path mismatch")
        seen_games=set()
        for x in board["rows"]:
            gid=str(x["game_id"])
            if gid in seen_games:raise ValueError("Repeated game in displayed board")
            seen_games.add(gid)
            kickoff=parse_time(x["kickoff_utc"])
            observed=parse_time(x["frozen_forecast_observed_utc"])
            # Early Oct 24 snapshots predate the model-version schema
            # addition. Do not invent a version for them or reject genuine
            # immutable research decisions. Require matched presence in later
            # versions, but preserve the archived model digest in all cases.
            board_model=board.get("model_version")
            row_model=x.get("forecast_model_version")
            if ((board_model is None)!=(row_model is None) or
                (board_model is not None and
                 (not isinstance(board_model,str) or not board_model or
                  row_model!=board_model)) or
                not observed<=captured<kickoff or
                x["frozen_forecast_sha256"]!=board["model_forecast_sha256"] or
                not isinstance(x.get("frozen_forecast_run_id"),str) or
                not x["frozen_forecast_run_id"].isdigit()):
                raise ValueError("Invalid pregame website decision chronology")
            x["forecast_model_version"]=row_model or "LEGACY_MODEL_VERSION_NOT_CAPTURED"
            line_at=x.get("market_observed_utc")
            spread=x.get("market_home_spread");total=x.get("market_total")
            if spread is not None or total is not None:
                if not x.get("market_provider") or not line_at or not parse_time(line_at)<=captured:
                    raise ValueError("Missing as-observed market provenance")
                if parse_time(line_at)>=kickoff:raise ValueError("Late sportsbook quote")
            for market,line,selection in (("ats",spread,x.get("displayed_ats_side")),
                                          ("ou",total,x.get("displayed_ou_side"))):
                if line is None:
                    if selection is not None:raise ValueError("Selection without observed line")
                    continue
                if type(line) not in (int,float) or not math.isfinite(line):
                    raise ValueError("Nonfinite frozen market line")
                margin=x["frozen_forecast_home_margin"];pred_total=x["frozen_forecast_total"]
                if market=="ats":
                    if abs(line)>=80:raise ValueError("Invalid observed spread")
                    diff=margin+line
                    # Since 2026-10-31 the live page can explicitly suppress
                    # the unreliable V03 home-biased ATS research choice.
                    # This is a legitimate immutable *as displayed* PASS,
                    # not a retroactive rewrite of the original score.
                    if ("home_bias_quarantined" in x and
                        type(x["home_bias_quarantined"]) is not bool):
                        raise ValueError("Invalid home-bias quarantine provenance")
                    expected=("PASS" if x.get("home_bias_quarantined") is True
                              else "HOME" if diff>0 else
                              "AWAY" if diff<0 else "PASS")
                else:
                    if not 0<line<150:raise ValueError("Invalid observed game total")
                    diff=pred_total-line
                    expected="OVER" if diff>0 else "UNDER" if diff<0 else "PASS"
                if selection!=expected:raise ValueError("Archived website pick changed")
                if selection=="PASS":continue
                raw[market]+=1
                # Earliest eligible displayed selection, never choose a later
                # forecast/line in hindsight after knowing the result.
                key=(gid,market)
                priority=(captured,runid)
                if key not in first or priority<first[key][0]:
                    first[key]=(priority,x)
                observed_games.add(gid)

            # Only a newer archival schema records this prospective challenger.
            # Never reconstruct research picks for older snapshots in hindsight.
            if x.get("v04_research_policy") is not None:
                if (x.get("v04_research_policy")!=V04_POLICY or
                    x.get("v04_research_status")!=V04_STATUS or
                    x.get("v04_direct_score_model")!=V04_SCORE_MODEL or
                    x.get("v04_direct_source_no_v03_total_reuse") is not True or
                    x.get("v04_research_not_promoted") is not True or
                    x.get("home_bias_quarantined") is not True):
                    raise ValueError("Invalid V04 research source provenance")
                v04score={
                    "status":V04_SCORE_STATUS,"model":V04_SCORE_MODEL,
                    "home_margin":x.get("v04_direct_home_margin"),
                    "total_points":x.get("v04_direct_total_points"),
                    "home_points":x.get("v04_direct_home_points"),
                    "away_points":x.get("v04_direct_away_points"),
                    "direct_scoring_fit_uses_v03_total":False,
                    "no_market_lines_in_training":True,
                    "model_promoted":False}
                expected=v04_decide(
                    v04score,spread,total,x.get("market_provider"),line_at,
                    x["kickoff_utc"],board["capture_utc"],
                    x.get("qb_verified_at_forecast",0))
                mapping={
                    "status":"v04_research_status",
                    "policy":"v04_research_policy",
                    "ats_side":"v04_research_ats_side",
                    "ou_side":"v04_research_ou_side",
                    "ats_reason":"v04_research_ats_reason",
                    "ou_reason":"v04_research_ou_reason",
                    "raw_ats_model_market_gap":"v04_research_ats_gap",
                    "raw_ou_model_market_gap":"v04_research_ou_gap",
                    "market_anchored_home_margin":"v04_research_anchored_margin",
                    "market_anchored_total":"v04_research_anchored_total",
                    "missing_verified_qb_warning":"v04_research_qb_unknown"}
                if any(expected[k]!=x.get(v) for k,v in mapping.items()):
                    raise ValueError("Archived V04 selection changed")
                for m,line in (("ats",spread),("ou",total)):
                    if line is None:continue
                    key=(gid,m)
                    priority=(captured,runid)
                    if key not in first_v04 or priority<first_v04[key][0]:
                        first_v04[key]=(priority,x)
            elif any(x.get(k) is not None for k in (
                "v04_research_status","v04_research_ats_side",
                "v04_research_ou_side","v04_research_ats_gap",
                "v04_research_ou_gap")):
                raise ValueError("Partial V04 research receipt")

    by_market={"ats":[],"ou":[]};by_week=defaultdict(lambda:defaultdict(list))
    graded_by_game=defaultdict(dict);unsettled=set()
    for (gid,market),(_,x) in first.items():
        final=finals.get(gid)
        if final is None:
            unsettled.add(gid);continue
        if ((x["home"],x["away"],parse_time(x["kickoff_utc"]))!=
            (final["home"],final["away"],parse_time(final["kickoff_utc"]))):
            mismatches+=1
            continue
        if (parse_time(final["outcome_known_at_utc"])<=parse_time(x["kickoff_utc"])
            or parse_time(final["observed_at_utc"])<=parse_time(x["market_observed_utc"])):
            raise ValueError("Final was observed before the displayed market")
        h=final["home_score"];a=final["away_score"]
        if type(h) is not int or type(a) is not int or min(h,a)<0:
            raise ValueError("Untrusted final score")
        if market=="ats":
            value=h-a+x["market_home_spread"]
            if x["displayed_ats_side"]=="AWAY":value=-value
        else:
            value=h+a-x["market_total"]
            if x["displayed_ou_side"]=="UNDER":value=-value
        outcome="WIN" if value>0 else "LOSS" if value<0 else "PUSH"
        by_market[market].append(outcome)
        by_week[_week(x["kickoff_utc"])][market].append(outcome)
        graded_by_game[gid][market]=outcome
        row=rows.setdefault(gid,{"game_id":gid,"home":final["home"],
            "away":final["away"],"kickoff_utc":final["kickoff_utc"],
            "score":str(a)+"–"+str(h),"su":None,"ats":None,"ou":None,
            "forecast_model":x["forecast_model_version"]})
        row[market]=outcome

    # Earliest authenticated pre-kickoff V04 policy per game/market is fixed:
    # an early PASS remains a PASS, even if a later snapshot would have won.
    v04_graded={"ats":[],"ou":[]}
    v04_eligible=Counter()
    v04_pass=Counter()
    v04_week=defaultdict(lambda:defaultdict(list))
    v04_margin_errors=[];v04_market_margin_errors=[]
    v04_total_errors=[];v04_market_total_errors=[]
    v04_home_count=0;v04_winner_correct=0;v04_winner_count=0
    v04_favorite_correct=0;v04_favorite_count=0
    for (gid,market),(_,x) in first_v04.items():
        final=finals.get(gid)
        if final is None:continue
        if ((x["home"],x["away"],parse_time(x["kickoff_utc"]))!=
            (final["home"],final["away"],parse_time(final["kickoff_utc"]))):
            raise ValueError("V04 research final identity mismatch")
        if parse_time(final["observed_at_utc"])<=parse_time(x["market_observed_utc"]):
            raise ValueError("V04 final predates pregame quote")
        h=final["home_score"];a=final["away_score"]
        margin=h-a;actual_total=h+a
        v04_eligible[market]+=1
        if market=="ats":
            v04_pred=x["v04_direct_home_margin"]
            spread=x["market_home_spread"]
            v04_margin_errors.append(abs(margin-v04_pred))
            v04_market_margin_errors.append(abs(margin+spread))
            v04_home_count+=int(v04_pred>0)
            if margin!=0 and v04_pred!=0:
                v04_winner_count+=1
                v04_winner_correct+=int((margin>0)==(v04_pred>0))
            if margin!=0 and spread!=0:
                v04_favorite_count+=1
                v04_favorite_correct+=int((margin>0)==(-spread>0))
            selection=x["v04_research_ats_side"]
            value=margin+spread
            if selection=="AWAY":value=-value
        else:
            v04_total_errors.append(abs(actual_total-x["v04_direct_total_points"]))
            v04_market_total_errors.append(abs(actual_total-x["market_total"]))
            selection=x["v04_research_ou_side"]
            value=actual_total-x["market_total"]
            if selection=="UNDER":value=-value
        if selection=="PASS":
            v04_pass[market]+=1
            continue
        grade="WIN" if value>0 else "LOSS" if value<0 else "PUSH"
        v04_graded[market].append(grade)
        v04_week[_week(x["kickoff_utc"])][market].append(grade)

    keys=set(su_by_week)|set(by_week)
    weekly=[]
    for week in sorted(keys):
        weekly.append({"week":str(week.year)+"-W"+str(week.week).zfill(2),
                       "su":_stats(su_by_week[week]),
                       "ats":_stats(by_week[week]["ats"]),
                       "ou":_stats(by_week[week]["ou"])})
    output={
        "status":"ARCHIVED_PROSPECTIVE_MODEL_PERFORMANCE_RESEARCH_ONLY",
        "asof_utc":now.isoformat(),"betting_status":"PASS_UNVALIDATED",
        "model_validated":False,"profitability_calculated":False,
        "policies":{"su":"LATEST_QUALIFYING_FROZEN_FORECAST_24_TO_72H",
                    "ats_ou":"EARLIEST_PREKICKOFF_WEBSITE_DISPLAY_WITH_OBSERVED_MARKET"},
        "su":_stats(su),"ats":_stats(by_market["ats"]),
        "ou":_stats(by_market["ou"]),
        "scoring":{"margin_mae":round(sum(margin_errors)/len(margin_errors),3) if margin_errors else None,
                   "total_mae":round(sum(total_errors)/len(total_errors),3) if total_errors else None,
                   "frozen_games":len(grades),"verified_final_games":len(finals),
                   "website_runs":len(seen_runs),
                   "unsettled_site_market_games":len(unsettled),
                   "unmatched_final_identity":mismatches,
                   "duplicate_ats_snapshots_excluded":raw["ats"]-len({g for g,m in first if m=="ats"}),
                   "duplicate_ou_snapshots_excluded":raw["ou"]-len({g for g,m in first if m=="ou"})},
        "v04_challenger":{
            "status":"ARCHIVED_PREKICKOFF_V04_MARKET_RESEARCH_GRADES",
            "policy":V04_POLICY,
            "ats":_stats(v04_graded["ats"]),
            "ou":_stats(v04_graded["ou"]),
            "eligible_with_quote":{"ats":v04_eligible["ats"],"ou":v04_eligible["ou"]},
            "explicit_passes":{"ats":v04_pass["ats"],"ou":v04_pass["ou"]},
            "ats_selection_rate":round(len(v04_graded["ats"])/v04_eligible["ats"],5)
                if v04_eligible["ats"] else None,
            "ou_selection_rate":round(len(v04_graded["ou"])/v04_eligible["ou"],5)
                if v04_eligible["ou"] else None,
            "v04_margin_mae":round(sum(v04_margin_errors)/len(v04_margin_errors),3)
                if v04_margin_errors else None,
            "market_margin_mae_paired":round(sum(v04_market_margin_errors)/len(v04_market_margin_errors),3)
                if v04_market_margin_errors else None,
            "v04_total_mae":round(sum(v04_total_errors)/len(v04_total_errors),3)
                if v04_total_errors else None,
            "market_total_mae_paired":round(sum(v04_market_total_errors)/len(v04_market_total_errors),3)
                if v04_market_total_errors else None,
            "v04_su_correct":v04_winner_correct,
            "v04_su_comparable_games":v04_winner_count,
            "market_favorite_su_correct":v04_favorite_correct,
            "market_favorite_su_comparable_games":v04_favorite_count,
            "v04_home_predicted_with_spread":v04_home_count,
            "weekly":[{"week":str(w.year)+"-W"+str(w.week).zfill(2),
                       "ats":_stats(v04_week[w]["ats"]),
                       "ou":_stats(v04_week[w]["ou"])}
                      for w in sorted(v04_week)],
            "unsettled_excluded":len({gid for gid,m in first_v04 if gid not in finals}),
            "no_historical_retroactive_pick_filling":True,
            "model_promoted":False,
            "market_publication_at_model_forecast_authenticated":False,
            "validated_betting_edge":False,
            "note":"Earliest archived pre-kickoff V04 research selections, including abstentions. Only observed quotes; market provider publication time at the model forecast is not authenticated. Comparisons to market MAE are paired descriptive diagnostics, not betting ROI."
        },
        "weekly":weekly,
        "recent":sorted(rows.values(),key=lambda r:(r["kickoff_utc"],r["game_id"]),reverse=True)[:25],
        "note":"SU: frozen 24–72h model forecasts. ATS/totals: earliest pre-kickoff research picks actually displayed with an observed market. Different cohorts, not directly comparable. Odds source publication times are not independently attested. No wagering ROI."
    }
    return output

def run(root,dashboard,now=None):
    p=Path(dashboard)
    board=json.loads(p.read_text(encoding="utf-8"))
    if board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Unexpected site dashboard contract")
    board["prospective_records"]=compute(root,now)
    p.write_text(json.dumps(board,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    report=board["prospective_records"]
    print(json.dumps({"su":report["su"],"ats":report["ats"],"ou":report["ou"],
                      "scoring":report["scoring"]}))
    return board

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",required=True)
    p.add_argument("--dashboard",required=True)
    a=p.parse_args()
    run(a.archive_root,a.dashboard)

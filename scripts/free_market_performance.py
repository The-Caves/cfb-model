"""Milestone 4: reproducible prospective performance report, one game per market.

Selection policy: earliest archived eligible forecast, tie-break provider/run ID.
All provider quotes and subsequent forecasts remain in diagnostic counts, never
silently counted as independent games. Research only, not realized betting ROI.
"""
import argparse,datetime as dt,json
from collections import Counter,defaultdict
from pathlib import Path
from scripts.game_context import parse_time
from scripts.free_market_final_grade import outcome
from scripts.market_settlement import exact_score

def stats(values):
    c=Counter(values)
    if set(c)-{"WIN","LOSS","PUSH"}:raise ValueError("Invalid graded outcome")
    n=c["WIN"]+c["LOSS"]
    return {"wins":c["WIN"],"losses":c["LOSS"],"pushes":c["PUSH"],
            "decisions":n,"win_rate":round(c["WIN"]/n,5) if n else None}

def report(matches,grades,su_records=None):
    if (matches.get("status")!="VERIFIED_MARKET_FINAL_MATCH_RESEARCH_ONLY" or
        grades.get("status")!="VERIFIED_PROSPECTIVE_MARKET_GRADES_RESEARCH_ONLY" or
        matches.get("safe_for_betting") is not False or
        grades.get("safe_for_betting") is not False):
        raise ValueError("Invalid research evidence")
    lookup={}
    for r in matches["rows"]:
        key=(str(r["forecast_run_id"]),str(r["game_id"]),r["provider"])
        if key in lookup:raise ValueError("Duplicate matched source")
        lookup[key]=r
    grade_lookup={}
    for g in grades["rows"]:
        key=(str(g["forecast_run_id"]),str(g["game_id"]),g["provider"])
        if key in grade_lookup or key not in lookup:raise ValueError("Duplicate/unmatched grade")
        grade_lookup[key]=g
    if set(grade_lookup)!=set(lookup):raise ValueError("Missing settlement grade")
    selections={};raw=Counter()
    for key,g in grade_lookup.items():
        r=lookup[key]
        if g["match_status"]!=r["status"]:raise ValueError("Match/grade mismatch")
        for market in ("ats","total"):
            value=g[market]
            if value is None:continue
            if r["status"]!="MATCHED_VERIFIED_FINAL" or value not in ("WIN","LOSS","PUSH"):
                raise ValueError("Unverified settlement included")
            raw[market]+=1
            group=(key[1],market)
            # deterministic earliest eligible archived forecast; never prefer wins
            priority=(parse_time(r["forecast_observed_utc"]),parse_time(r["market_observed_utc"]),
                      key[2],int(key[0]))
            if group not in selections or priority<selections[group][0]:
                selections[group]=(priority,key,r,g)
    by_market=defaultdict(list);by_week=defaultdict(lambda:defaultdict(list))
    baseline=defaultdict(list);selected=[]
    for (gid,market),(priority,key,r,g) in sorted(selections.items()):
        actual=g[market]
        h=exact_score(r["home_score"]);a=exact_score(r["away_score"])
        if market=="ats":
            line=r["market_home_spread"]
            base=outcome(h-a+line)
            base_label="always_home"
        else:
            line=r["market_total"]
            base=outcome(h+a-line)
            base_label="always_over"
        kickoff=parse_time(r["kickoff_utc"])
        week=kickoff.strftime("%G-W%V")
        by_market[market].append(actual);by_week[week][market].append(actual)
        baseline[market].append(base)
        selected.append({"game_id":gid,"market":market,"provider":key[2],
            "forecast_run_id":key[0],"kickoff_utc":r["kickoff_utc"],
            "forecast_observed_utc":r["forecast_observed_utc"],
            "selection":r["ats_selection"] if market=="ats" else r["total_selection"],
            "grade":actual,"baseline_grade":base,"baseline_policy":base_label})
    su=list(su_records or [])
    if any(x not in (True,False) for x in su):raise ValueError("Invalid SU grade")
    su_stats=stats(["WIN" if x else "LOSS" for x in su])
    return {"status":"CUMULATIVE_PROSPECTIVE_PERFORMANCE_RESEARCH_ONLY",
        "asof_utc":grades["asof_utc"],
        "selection_policy":"EARLIEST_FROZEN_FORECAST_PER_GAME_AND_MARKET",
        "weekly_bucket":"UTC_ISO_WEEK",
        "summary":{"su":su_stats,
            "ats":stats(by_market["ats"]),"total":stats(by_market["total"]),
            "raw_provider_forecasts":{"ats":raw["ats"],"total":raw["total"]},
            "unique_games":{"ats":len(by_market["ats"]),"total":len(by_market["total"])},
            "duplicates_excluded":{"ats":raw["ats"]-len(by_market["ats"]),
                                   "total":raw["total"]-len(by_market["total"])}},
        "benchmarks":{"ats_always_home":stats(baseline["ats"]),
                      "total_always_over":stats(baseline["total"])},
        "weekly":{week:{market:stats(vals) for market,vals in sorted(markets.items())}
                  for week,markets in sorted(by_week.items())},
        "selected_grades":selected,
        "su_source":"INDEPENDENT_VERIFIED_STEP3G_ARCHIVE",
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
        "profitability_calculated":False,"model_validated":False}

def su_archive():
    from scripts.personnel_forecast_grade import read
    index,_,_,_,_,_,records=read()
    values=[]
    for gid in sorted(index["games"]):
        record=records[index["games"][gid]["path"]]
        v=record.get("su_correct")
        if type(v) is not bool:raise ValueError("Invalid archived SU grade")
        values.append(v)
    return values

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--matches",required=True)
    p.add_argument("--grades",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    result=report(json.loads(Path(a.matches).read_text()),
                  json.loads(Path(a.grades).read_text()),su_archive())
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result["summary"]))

"""Retrospective 2026 early-season player form versus prior-season shrinkage.

This measures a same-recorded-player cohort, not authentic frozen pregame
availability or stat-market edges. First one/two 2026 player-game observations
are compared to a predeclared prior-season shrinkage blend. Transfer cohorts
are ID association changes, not verified transfer eligibility.
"""
import argparse
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.player_prop_history import STATUS as CURRENT_STATUS
from scripts.player_prop_prior_seasons import STATUS as PAST_STATUS

STATUS="EARLY_SEASON_PLAYER_PRIOR_MATCHED_RETROSPECTIVE_RESEARCH_ONLY"
METRICS=("passing_yards","passing_attempts","rushing_yards","rushing_attempts",
         "receiving_yards","receptions","passing_touchdowns",
         "rushing_touchdowns","receiving_touchdowns","interceptions")
SAME_PRIOR=0.40
CHANGED_PRIOR=0.25
OLDER_SHARE=0.20

def _avg(a):
    return sum(a)/len(a) if a else None

def _validate(prior,current):
    if (prior.get("status")!=PAST_STATUS or
        prior.get("historical_first_publication_authenticated") is not False or
        prior.get("seasons")!=[2024,2025] or
        current.get("status")!=CURRENT_STATUS or
        current.get("season")!=2026 or
        current.get("retrospective_first_publication_authenticated") is not False or
        prior.get("betting_status")!="PASS_UNVALIDATED" or
        current.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Incorrect previous season or source evidence")
    for season in ("2024","2025"):
        if prior["by_season"][season]["season"]!=int(season):
            raise ValueError("Missing previous football season")
        for row in prior["by_season"][season]["player_game_ledger"]:
            if row.get("source_status")!="RETROSPECTIVE_REVISED_PLAYER_BOX_ONLY":
                raise ValueError("Untrusted prior athlete game")
    for row in current["rows"]:
        if row.get("source_status")!="RETROSPECTIVE_REVISED_PLAYER_BOX_ONLY":
            raise ValueError("Untrusted 2026 athlete game")

def evaluate(prior,current,first="2026-08-01",last="2026-11-01"):
    _validate(prior,current)
    beginning=dt.date.fromisoformat(first)
    end=dt.date.fromisoformat(last)
    if beginning>=end:raise ValueError("Invalid evaluation date interval")
    histories=defaultdict(lambda:defaultdict(list))
    teams_2025=defaultdict(set)
    for year in ("2024","2025"):
        seen=set()
        for row in prior["by_season"][year]["player_game_ledger"]:
            day=dt.date.fromisoformat(row["date"])
            key=(str(row["player_id"]),str(row["game_id"]),str(row["team_id"]))
            if key in seen:raise ValueError("Duplicate historical prior athlete game")
            seen.add(key)
            if day>=beginning:
                raise ValueError("Prior football season game occurred after evaluation begins")
            athlete=str(row["player_id"])
            if year=="2025":teams_2025[athlete].add(str(row["team_id"]))
            for stat in METRICS:
                val=row["values"].get(stat)
                if type(val) is int:
                    histories[year][(athlete,stat)].append((day,val))
    for year in ("2024","2025"):
        for rows in histories[year].values():rows.sort(key=lambda x:x[0])
    today=defaultdict(list)
    seen=set()
    for row in current["rows"]:
        key=(str(row["game_id"]),str(row["team_id"]),str(row["player_id"]))
        if key in seen:raise ValueError("Duplicate 2026 athlete game")
        seen.add(key)
        today[dt.date.fromisoformat(row["date"])].append(row)
    season_form=defaultdict(list)
    grades=defaultdict(list)
    coverage=defaultdict(lambda:defaultdict(int))
    for day in sorted(today):
        pending=[]
        for row in today[day]:
            athlete=str(row["player_id"])
            team=str(row["team_id"])
            prevteams=teams_2025.get(athlete,set())
            if not prevteams:cohort="NO_2025_PLAYER_STAT_TAPE"
            elif len(prevteams)>1:cohort="AMBIGUOUS_2025_TEAM"
            elif team in prevteams:cohort="SAME_RECORDED_TEAM_ID"
            else:cohort="DIFFERENT_RECORDED_TEAM_ID"
            for stat in METRICS:
                value=row["values"].get(stat)
                if type(value) is not int:continue
                key=(athlete,team,stat)
                existing=season_form[key]
                if beginning<=day<end:
                    coverage[(cohort,stat)]["observed_player_stat_categories"]+=1
                    if not 1<=len(existing)<=2:
                        coverage[(cohort,stat)]["NOT_1_TO_2_PRIOR_2026_GAMES"]+=1
                    elif cohort not in ("SAME_RECORDED_TEAM_ID","DIFFERENT_RECORDED_TEAM_ID"):
                        coverage[(cohort,stat)]["UNVERIFIED_2025_TEAM_ASSOCIATION"]+=1
                    else:
                        year2025=[x for _,x in histories["2025"].get((athlete,stat),[])]
                        if len(year2025)<2:
                            coverage[(cohort,stat)]["INSUFFICIENT_2025_PLAYER_METRIC"]+=1
                        else:
                            last2025=year2025[-6:]
                            year2024=[x for _,x in histories["2024"].get((athlete,stat),[])]
                            avg2025=_avg(last2025)
                            reference=(1-OLDER_SHARE)*avg2025+OLDER_SHARE*_avg(year2024[-6:]) if len(year2024)>=2 else avg2025
                            alpha=SAME_PRIOR if cohort=="SAME_RECORDED_TEAM_ID" else CHANGED_PRIOR
                            base=_avg(existing)
                            challenger=(1-alpha)*base+alpha*reference
                            grades[(cohort,stat)].append({
                                "date":day.isoformat(),"game_id":str(row["game_id"]),
                                "player_id":athlete,"team_id":team,
                                "actual":value,"current_only_prediction":round(base,6),
                                "prior_shrunk_prediction":round(challenger,6),
                                "current_only_abs_error":abs(value-base),
                                "prior_shrunk_abs_error":abs(value-challenger),
                                "n_previous_2026_recorded_games":len(existing),
                                "n_previous_2025_recorded_games":len(year2025),
                                "prior_shrinkage":alpha,
                                "recorded_team_change_only_not_verified_transfer":True})
                pending.append((key,value))
        for key,value in pending:season_form[key].append(value)
    summary={}
    for cohort in ("SAME_RECORDED_TEAM_ID","DIFFERENT_RECORDED_TEAM_ID"):
        summary[cohort]={}
        for stat in METRICS:
            rows=grades[(cohort,stat)]
            n=len(rows)
            base=round(sum(r["current_only_abs_error"] for r in rows)/n,6) if n else None
            model=round(sum(r["prior_shrunk_abs_error"] for r in rows)/n,6) if n else None
            summary[cohort][stat]={
                "matched_player_games":n,
                "current_season_only_mae":base,
                "with_prior_season_mae":model,
                "paired_mae_delta":round(model-base,6) if n else None,
                "excluded_or_unknown":dict(coverage[(cohort,stat)]),
                "eligible_for_live_promotion":False}
    return {"status":STATUS,"seasons":[2024,2025,2026],
        "research_window":{"first":first,"exclusive_last":last},
        "2025_previous_season_blend_for_same_team":SAME_PRIOR,
        "2025_previous_season_blend_for_different_team":CHANGED_PRIOR,
        "2024_share_when_multiple_older_games":OLDER_SHARE,
        "summary":summary,
        "paired_player_game_predictions":{a+"|"+b:x for (a,b),x in grades.items()},
        "source_observed_dates":{"prior":prior["source_observed_at_utc"],
                                 "current":current["observed_at_utc"]},
        "retrospective_player_stat_category_selection_bias":True,
        "past_pregame_source_publication_authenticated":False,
        "transfer_eligibility_proved":False,
        "real_bookmaker_player_prop_lines_used":0,
        "automatic_model_promotion":False,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

def run(prior,current,out):
    a=json.loads(Path(prior).read_text(encoding="utf-8"))
    b=json.loads(Path(current).read_text(encoding="utf-8"))
    r=evaluate(a,b)
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(r,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":STATUS,"stats":r["summary"],
          "model_promoted":False}))
    return r

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--prior",required=True);p.add_argument("--current",required=True)
    p.add_argument("--output",required=True);a=p.parse_args()
    run(a.prior,a.current,a.output)

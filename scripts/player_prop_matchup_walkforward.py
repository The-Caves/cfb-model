"""Retrospective prior-date opponent defense x player yard-form ablation.

Opponent passing/rushing defense is estimated from the previous games'
observed opposing player box category totals. We explicitly do not treat
the target game's stats as known when constructing either estimate.
The current revised 2026 box release is not a verified point-in-time archive.
"""
import argparse
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.player_prop_history import STATUS as HISTORY
from scripts.player_prop_walkforward import _predict

STATUS="CFB_PLAYER_PROPS_OPPONENT_MATCHUP_WALKFORWARD_RESEARCH_ONLY"
STATS={"passing_yards":"pass","receiving_yards":"pass","rushing_yards":"rush"}
FACT=.25  # predeclared fixed conservative shrink, NOT selected on heldout labels

def _avg(xs):
    return sum(xs)/len(xs) if xs else None

def evaluate(source,start="2026-09-26"):
    if (source.get("status")!=HISTORY or source.get("betting_status")!="PASS_UNVALIDATED"
        or source.get("retrospective_first_publication_authenticated") is not False):
        raise ValueError("Untrusted historical player-game source")
    first=dt.date.fromisoformat(start)
    byday=defaultdict(list);seen=set()
    for row in source["rows"]:
        key=(str(row["game_id"]),str(row["player_id"]),str(row["team_id"]))
        if key in seen:raise ValueError("Duplicate player-game")
        seen.add(key)
        byday[dt.date.fromisoformat(row["date"])].append(row)
    # All game/athlete stat identity evidence comes from the retrospectively
    # observed provider fixture. Needed later: independent pregame team IDs.
    players=defaultdict(list)
    defense=defaultdict(list)
    league=defaultdict(list)
    grade=defaultdict(list)
    skipped=defaultdict(lambda:defaultdict(int))
    for day in sorted(byday):
        entries=byday[day]
        bygame=defaultdict(list)
        for r in entries:bygame[str(r["game_id"])].append(r)
        opponent={}
        current_totals=[]
        for gid,rows in bygame.items():
            teams={str(r["team_id"]) for r in rows}
            if len(teams)!=2:
                continue
            a,b=sorted(teams)
            opponent[(gid,a)]=b;opponent[(gid,b)]=a
            totals=defaultdict(lambda:{"pass":[],"rush":[]})
            for r in rows:
                t=str(r["team_id"])
                for field,group in (("passing_yards","pass"),("rushing_yards","rush")):
                    x=r["values"].get(field)
                    if x is not None:totals[t][group].append(x)
            for own,other in ((a,b),(b,a)):
                for group in ("pass","rush"):
                    nums=totals[own][group]
                    if nums:
                        current_totals.append((own,other,group,sum(nums)))
        # Evaluate all today's games before ANY defensive/opponent profiles
        # are modified by today's final outcome.
        for r in entries:
            gid=str(r["game_id"]);team=str(r["team_id"])
            opp=opponent.get((gid,team))
            for field,side in STATS.items():
                actual=r["values"].get(field)
                if actual is None or day<first:continue
                historical=players[(team,str(r["player_id"]),field)]
                prediction=_predict(historical)
                if prediction is None:
                    skipped[field]["INSUFFICIENT_PRIOR_PLAYER_GAMES"]+=1;continue
                if opp is None:
                    skipped[field]["UNVERIFIED_TWO_SIDED_TARGET_FIXTURE"]+=1;continue
                allow=defense[(opp,side)]
                baseline=prediction[0]
                previous_league=league[side]
                if len(allow)<2 or len(previous_league)<25:
                    skipped[field]["INSUFFICIENT_PRIOR_OPPONENT_DEFENSE_OR_LEAGUE"]+=1;continue
                mean_allow=_avg(allow[-6:])
                league_base=_avg(previous_league[-2000:])
                if league_base is None or league_base<=0:
                    skipped[field]["NO_VALID_PRIOR_LEAGUE_DEFENSE"]+=1;continue
                edge=max(-.25,min(.25,mean_allow/league_base-1))
                adjusted=baseline*(1+FACT*edge)
                grade[field].append({"game_id":gid,"date":day.isoformat(),
                    "player_id":str(r["player_id"]),"team_id":team,"opponent_id":opp,
                    "actual":actual,"baseline":round(baseline,5),
                    "matchup_candidate":round(adjusted,5),
                    "prior_opponent_defensive_games":len(allow),
                    "defensive_style_edge":round(edge,5),
                    "baseline_error":abs(actual-baseline),
                    "candidate_error":abs(actual-adjusted)})
        for r in entries:
            team=str(r["team_id"])
            for field in STATS:
                value=r["values"].get(field)
                if value is not None:
                    players[(team,str(r["player_id"]),field)].append(value)
        for own,op,side,total in current_totals:
            defense[(op,side)].append(total)
            league[side].append(total)
    summary={}
    for stat in sorted(STATS):
        rows=grade[stat]
        n=len(rows)
        summary[stat]={"paired_recorded_player_games":n,
           "baseline_mae":round(sum(x["baseline_error"] for x in rows)/n,5) if n else None,
           "opponent_adjusted_mae":round(sum(x["candidate_error"] for x in rows)/n,5) if n else None,
           "opponent_adjusted_delta_mae":round(sum(
              x["candidate_error"]-x["baseline_error"] for x in rows)/n,5) if n else None,
           "excluded":dict(skipped[stat]),
           "source_status":"REVISED_PBP_AND_BOX_NOT_POINT_IN_TIME_VERIFIED",
           "eligible_for_live_model":False}
    return {"status":STATUS,"season":2026,"first_test_date":start,
       "fixed_matchup_shrinkage":FACT,"summary":summary,
       "paired_predictions":{k:v for k,v in grade.items()},
       "same_matchup_date_no_leakage":True,
       "fixture_team_id_source_is_retrospective_not_pregame_verified":True,
       "graded_only_recorded_stat_categories":True,
       "source_first_publication_verified":False,
       "model_promoted":False,"safe_for_betting":False,
       "betting_status":"PASS_UNVALIDATED"}

def run(path,out):
    r=evaluate(json.loads(Path(path).read_text()))
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(r,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":STATUS,
        "summary":r["summary"],"model_promoted":False}))
    return r

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.input,a.output)

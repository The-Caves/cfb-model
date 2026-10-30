"""Same-recorded-participation-cohort CFB prop hypotheses, chronological only.

Baseline = rolling four historical *recorded* appearances. Challenger =
recency-weighted six. No unavailable player is assumed to have played or
recorded zero. Market lines are NOT part of this revised-source backtest.
Most important limitation: evaluating players only when a box stat exists
creates participation selection bias. This is diagnostic, not an ATS/prop edge.
"""
import argparse
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.player_prop_history import STATUS as SOURCE_STATUS, STATS

STATUS="CFB_PROP_CHRONOLOGICAL_MATCHED_RESEARCH_ONLY"
RECENCY=.78

def _avg(xs):
    return sum(xs)/len(xs) if xs else None

def _predict(history):
    last=list(reversed(history[-6:]))
    base=history[-4:]
    if len(base)<3:return None
    weights=[RECENCY**i for i in range(len(last))]
    return (_avg(base),sum(w*v for w,v in zip(weights,last))/sum(weights))

def evaluate(snapshot,start="2026-09-26"):
    if (snapshot.get("status")!=SOURCE_STATUS or
        snapshot.get("betting_status")!="PASS_UNVALIDATED" or
        snapshot.get("retrospective_first_publication_authenticated") is not False):
        raise ValueError("Requires explicitly retrospective 2026 player-game observations")
    boundary=dt.date.fromisoformat(start)
    byday=defaultdict(list)
    seen=set()
    for r in snapshot["rows"]:
        day=dt.date.fromisoformat(r["date"])
        key=(str(r["game_id"]),r["player_id"],r["team_id"])
        if key in seen:raise ValueError("Duplicate ESPN player/game record")
        seen.add(key)
        if r["source_status"]!="RETROSPECTIVE_REVISED_PLAYER_BOX_ONLY":
            raise ValueError("Untrusted player box source")
        byday[day].append(r)
    histories=defaultdict(list)
    results=defaultdict(list)
    coverage=defaultdict(lambda:defaultdict(int))
    for day in sorted(byday):
        pending=[]
        for r in byday[day]:
            key=(r["player_id"],r["team_id"])
            for stat in STATS:
                actual=r["values"].get(stat)
                if actual is None:continue
                coverage[stat]["recorded_rows"]+=1
                history=histories[(key,stat)]
                if day>=boundary:
                    pred=_predict(history)
                    if pred is None:
                        coverage[stat]["insufficient_past_appearances"]+=1
                    else:
                        base,chall=pred
                        results[stat].append({"game_id":r["game_id"],
                            "player_id":r["player_id"],"team_id":r["team_id"],
                            "date":r["date"],"actual":actual,
                            "baseline_last4":round(base,5),
                            "recency_last6":round(chall,5),
                            "baseline_abs_error":abs(actual-base),
                            "recency_abs_error":abs(actual-chall),
                            "baseline_squared_error":(actual-base)**2,
                            "recency_squared_error":(actual-chall)**2})
                pending.append((key,stat,actual))
        # Predictions for all same-date games preceded ANY updates from today.
        for key,stat,actual in pending:
            histories[(key,stat)].append(actual)
    graded={}
    for stat in STATS:
        sample=results[stat];n=len(sample)
        graded[stat]={"paired_recorded_player_games":n,
            "status":"RETROSPECTIVE_SAME_COHORT_ONLY" if n else "NO_PAIRED_OBSERVATIONS",
            "baseline_mae":round(sum(r["baseline_abs_error"] for r in sample)/n,5) if n else None,
            "recency_mae":round(sum(r["recency_abs_error"] for r in sample)/n,5) if n else None,
            "recency_delta_mae":round(sum(r["recency_abs_error"]-r["baseline_abs_error"]
                                          for r in sample)/n,5) if n else None,
            "baseline_rmse":round(math.sqrt(sum(r["baseline_squared_error"] for r in sample)/n),5)
               if n else None,
            "recency_rmse":round(math.sqrt(sum(r["recency_squared_error"] for r in sample)/n),5)
               if n else None,
            "source_coverage":dict(coverage[stat]),
            "prospective_player_prop_validation":False,
            "independent_pregame_line_comparison":None}
    return {"status":STATUS,"season":2026,
        "asof_source_observed_at_utc":snapshot["observed_at_utc"],
        "experiment_start":start,"models":["rolling_last4","recency_last6"],
        "summary":graded,"recorded_player_game_pairs":{k:v for k,v in results.items()},
        "source_first_publication_verified":False,
        "player_participation_selection_bias_present":True,
        "absent_unlisted_players_never_zero_filled":True,
        "true_prop_market_coverage":0,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}

def run(input,output):
    x=json.loads(Path(input).read_text(encoding="utf-8"))
    result=evaluate(x)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":STATUS,"paired":{k:v["paired_recorded_player_games"]
                  for k,v in result["summary"].items()},
                  "model_promoted":False}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--input",required=True)
    p.add_argument("--output",required=True);a=p.parse_args()
    run(a.input,a.output)

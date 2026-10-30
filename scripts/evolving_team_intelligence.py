"""As-of opponent-corrected team trajectory with evidence-limited change signals.

Accepts time-stamped, already sourced two-sided postgame team metric records.
Only past, observed games are inputs for a target date. Signals are descriptive,
not proof of structural change. Historical source publication must be audited.
"""
import argparse
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

from scripts.game_context import parse_time

STATUS="EVOLVING_TEAM_INTELLIGENCE_RESEARCH_ONLY"
METRICS=("pass_off","run_off","pass_def_allowed","run_def_allowed")
MIN_OPP=2


def _numeric(x):
    return type(x) in (int,float) and math.isfinite(x)


def _mean(rows,key):
    values=[r[key] for r in rows if r.get(key) is not None]
    return sum(values)/len(values) if values else None


def _profile(history):
    last=history[-6:]
    raw={k:_mean(last,k) for k in METRICS}
    for kind in ("pass","run"):
        for end in ("off_adj","def_adj"):
            raw[kind+"_"+end]=_mean(last,kind+"_"+end)
    raw["prior_games"]=len(history)
    raw["adjusted_games"]={key:sum(x.get(key) is not None for x in last)
                           for key in ("pass_off_adj","run_off_adj","pass_def_adj","run_def_adj")}
    trend={}
    for key in ("pass_off_adj","run_off_adj","pass_def_adj","run_def_adj"):
        values=[x[key] for x in last if x.get(key) is not None]
        if len(values)<6:
            trend[key]={"status":"INSUFFICIENT_PRIOR_OPPONENT_ADJUSTED_GAMES",
                        "recent_minus_previous":None}
        else:
            prior=sum(values[:3])/3
            recent=sum(values[3:])/3
            delta=round(recent-prior,6)
            trend[key]={"status":"OBSERVED_TRAJECTORY_NOT_CAUSAL",
                        "recent_minus_previous":delta,
                        "trend_direction":"UP" if delta>0 else "DOWN" if delta<0 else "FLAT"}
    raw["trajectory"]=trend
    raw["turnover_margin_recent"]=_mean(last,"turnover_margin")
    raw["turnover_data_games"]=sum(x.get("turnover_margin") is not None for x in last)
    raw["large_turnover_games"]=sum(abs(x["turnover_margin"])>=3 for x in last
                                   if x.get("turnover_margin") is not None)
    raw["structural_change_verified"]=False
    return raw


def _validate(row,decision):
    if not isinstance(row,dict) or not row.get("game_id") or not row.get("team") or not row.get("opponent"):
        raise ValueError("Invalid team/game identity")
    if row["team"]==row["opponent"]:
        raise ValueError("Self-game team")
    day=dt.date.fromisoformat(row["date"])
    if not (parse_time(row["kickoff_utc"])<parse_time(row["outcome_known_at_utc"])
            <=parse_time(row["source_observed_at_utc"])<=decision):
        raise ValueError("Outcome, capture or future-leakage error")
    if not str(row.get("source_url","")).startswith("https://"):
        raise ValueError("Missing cited completed-game source")
    if row.get("source_status")!="CAPTURED_COMPLETED_GAME_RESEARCH_ONLY":
        raise ValueError("Unsupported record trust level")
    for field in METRICS:
        if row.get(field) is not None and not _numeric(row[field]):
            raise ValueError("Invalid team metric")
    value=row.get("turnover_margin")
    if value is not None and (type(value) is not int or not -12<=value<=12):
        raise ValueError("Unverified turnover margin")
    return day


def build(observations,upcoming,decision_utc):
    decision=parse_time(decision_utc)
    if not upcoming: raise ValueError("Empty upcoming slate")
    upcoming_dates=[dt.date.fromisoformat(str(g["date"])) for g in upcoming]
    cutoff=min(upcoming_dates)
    if any(parse_time(g["kickoff_utc"])<=decision for g in upcoming):
        raise ValueError("Cannot use postkickoff target")
    by_game=defaultdict(list)
    for row in observations:
        day=_validate(row,decision)
        if day>=cutoff:
            # Source may exist now but is from the same/future football date;
            # this cannot enter any of the slate's prior-date profiles.
            continue
        by_game[str(row["game_id"])].append(row)
    for gid,rows in by_game.items():
        if (len(rows)!=2 or rows[0]["team"]!=rows[1]["opponent"]
            or rows[1]["team"]!=rows[0]["opponent"]
            or rows[0]["date"]!=rows[1]["date"]
            or parse_time(rows[0]["kickoff_utc"])!=parse_time(rows[1]["kickoff_utc"])):
            raise ValueError("Two-sided game identity mismatch: "+gid)
        if (rows[0]["turnover_margin"] is not None and rows[1]["turnover_margin"] is not None
                and rows[0]["turnover_margin"]!=-rows[1]["turnover_margin"]):
            raise ValueError("Turnover margin not zero-sum")
    history=defaultdict(list)
    calendar=defaultdict(list)
    for rows in by_game.values():
        calendar[rows[0]["date"]].extend(rows)
    for day in sorted(calendar):
        pending=[]
        for row in calendar[day]:
            old_opp=_profile(history[row["opponent"]])
            rec={k:row.get(k) for k in METRICS}
            rec.update({"date":day,"game_id":str(row["game_id"]),
                        "turnover_margin":row.get("turnover_margin")})
            for kind in ("pass","run"):
                defensive=old_opp[kind+"_def_allowed"]
                offensive=old_opp[kind+"_off"]
                rec[kind+"_off_adj"]=(row[kind+"_off"]-defensive
                     if row.get(kind+"_off") is not None and defensive is not None
                     and old_opp["prior_games"]>=MIN_OPP else None)
                rec[kind+"_def_adj"]=(row[kind+"_def_allowed"]-offensive
                     if row.get(kind+"_def_allowed") is not None and offensive is not None
                     and old_opp["prior_games"]>=MIN_OPP else None)
            pending.append((row["team"],rec))
        # Same football-date games never update profiles for each other.
        for team,record in pending:history[team].append(record)
    names=set(history)|{g[s] for g in upcoming for s in ("home","away")}
    profiles={name:_profile(history[name]) for name in sorted(names)}
    return {"status":STATUS,"decision_utc":decision.isoformat(),
            "prior_football_date_exclusive":cutoff.isoformat(),
            "source_record_count":sum(len(v) for v in by_game.values()),
            "profiles":profiles,
            "upcoming_games":[{
                "game_id":str(g["game_id"]),"home":g["home"],"away":g["away"],
                "kickoff_utc":g["kickoff_utc"],
                "home":g["home"],"away":g["away"],
                "home_profile":profiles[g["home"]],"away_profile":profiles[g["away"]],
                "model_impact_points":None
            } for g in upcoming],
            "historical_first_publication_authenticated":False,
            "structural_changes_claimed":0,"model_promoted":False,
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}


def run(observations,upcoming,decision,output):
    inputs=json.loads(Path(observations).read_text())
    slate=json.loads(Path(upcoming).read_text())
    result=build(inputs["observations"],slate["games"],decision)
    dst=Path(output);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--observations",required=True);p.add_argument("--upcoming",required=True)
    p.add_argument("--decision",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.observations,a.upcoming,a.decision,a.output)

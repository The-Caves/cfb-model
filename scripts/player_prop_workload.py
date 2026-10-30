"""Source-observed football-player workload share and retrospective ablation.

Shares are a fraction of RECORDED team-game statistical events, not snaps,
routes, targets, verified starters, healthy roster membership or guaranteed
future work. All rows are a retrospectively revised 2026 box feed; historical
provider first-publication timing is not independently authenticated.

Role candidate predicts player passing attempts, carries or receptions as
mean(prior same-player team stat share) * mean(prior team total). It competes
against the same-cohort previous-4 player-event count average. No missing
player stat category is treated as 0; same-day results never enter the day.
"""
import argparse
import datetime as dt
import json
import math
from collections import Counter,defaultdict
from pathlib import Path

from scripts.game_context import parse_time
from scripts.player_prop_history import STATUS as HISTORY

STATUS="CFB_ROLE_OPPORTUNITY_WALKFORWARD_RESEARCH_ONLY"
STAT_ROLE={
    "passing_yards":("passing_attempts","TEAM_RECORDED_PASS_ATTEMPT_SHARE"),
    "rushing_yards":("rushing_attempts","TEAM_RECORDED_RUSH_ATTEMPT_SHARE"),
    "receiving_yards":("receptions","TEAM_RECORDED_COMPLETION_SHARE_NOT_TARGET_SHARE"),
}
OTHER={metric:pair[0] for metric,pair in STAT_ROLE.items()}

def _avg(a):
    return sum(a)/len(a) if a else None

def _key(row):
    return str(row["game_id"]),str(row["team_id"])

def evidence(rows,after=None):
    """One row per observed player/game/stat category; no zero-filled DNPs."""
    group=defaultdict(list);seen=set()
    for p in rows:
        if p.get("source_status")!="RETROSPECTIVE_REVISED_PLAYER_BOX_ONLY":
            raise ValueError("Untrusted athlete-game form")
        key=(_key(p),str(p["player_id"]))
        if key in seen:raise ValueError("Duplicate athlete game row")
        seen.add(key)
        kick=parse_time(p["kickoff_utc"])
        if after is not None and kick>=parse_time(after):continue
        group[_key(p)].append(p)
    output=[];rejected=Counter()
    for (gid,team),players in group.items():
        team_totals={}
        for metric,(column,basis) in STAT_ROLE.items():
            vals=[r["values"].get(column) for r in players]
            values=[v for v in vals if type(v) is int]
            if not values or sum(values)<=0:
                team_totals[column]=None
            else:
                team_totals[column]=sum(values)
        completions=[r["values"].get("passing_completions") for r in players]
        known=[x for x in completions if type(x) is int]
        if known and team_totals["receptions"]!=sum(known):
            # Missing/extra receiving box rows can inflate a player's role.
            team_totals["receptions"]=None
            rejected["RECEPTIONS_DO_NOT_RECONCILE_RECORDED_COMPLETIONS"]+=1
        for r in players:
            for metric,(column,basis) in STAT_ROLE.items():
                total=team_totals[column]
                amount=r["values"].get(column)
                outcome=r["values"].get(metric)
                if type(amount) is not int or type(outcome) is not int or total is None:
                    continue
                if amount<0 or amount>total:
                    rejected["INVALID_RECORDED_PLAYER_SHARE"]+=1;continue
                output.append({
                    "game_id":gid,"team_id":team,"player_id":str(r["player_id"]),
                    "player_name":r["player_name"],"kickoff_utc":r["kickoff_utc"],
                    "metric":metric,"stat_role":column,"share_type":basis,
                    "observed_player_opportunities":amount,
                    "observed_team_opportunities":total,
                    "observed_player_yards":outcome,
                    "role_share":amount/total,
                    "player_pregame_participation_verified":False,
                    "source_first_published_before_this_game_verified":False,
                })
    output.sort(key=lambda x:(x["kickoff_utc"],x["game_id"],x["team_id"],x["player_id"],x["metric"]))
    return output,dict(rejected)

def player_role_index(rows,decision_utc):
    observations,excluded=evidence(rows,decision_utc)
    history=defaultdict(list);teams=defaultdict(list)
    for r in observations:
        key=(r["team_id"],r["player_id"],r["metric"])
        history[key].append(r)
        team_key=(r["game_id"],r["team_id"],r["metric"])
        # Same team volume appears in many player rows, count it once.
        teams[(r["team_id"],r["metric"])].append(team_key+(r["kickoff_utc"],r["observed_team_opportunities"]))
    distinct={}
    for key,vals in teams.items():
        unq={x[:3]:x for x in vals}
        distinct[key]=sorted(unq.values(),key=lambda x:x[3])
    return history,distinct,excluded

def role_summary(history,team,player,metric):
    records=history.get((str(team),str(player),metric),[])[-4:]
    if len(records)<2:return None
    mean=_avg([r["role_share"] for r in records])
    return {
        "role_basis":STAT_ROLE[metric][1],
        "recent_recorded_games":len(records),
        "recorded_opportunity_share":round(mean,5),
        "recent_recorded_share_low":round(min(r["role_share"] for r in records),5),
        "recent_recorded_share_high":round(max(r["role_share"] for r in records),5),
        "observed_at_utc":records[-1]["kickoff_utc"],
        "participation_not_confirmed":True,
        "share_is_not_snap_or_target_percentage":True,
        "unknown_unlisted_players_remain_unknown":True,
    }

def evaluate(snapshot,start="2026-09-26"):
    if (snapshot.get("status")!=HISTORY or snapshot.get("season")!=2026
        or snapshot.get("betting_status")!="PASS_UNVALIDATED"
        or snapshot.get("retrospective_first_publication_authenticated") is not False):
        raise ValueError("Untrusted revised 2026 player box research snapshot")
    begin=dt.date.fromisoformat(start)
    rows,excluded=evidence(snapshot["rows"])
    byday=defaultdict(list)
    for row in rows:byday[parse_time(row["kickoff_utc"]).date()].append(row)
    player_history=defaultdict(list);team_history=defaultdict(list)
    tested=defaultdict(list);missing=Counter()
    for day in sorted(byday):
        pending_player=[];pending_team={}
        for row in byday[day]:
            k=(row["team_id"],row["player_id"],row["metric"])
            team_k=(row["team_id"],row["metric"])
            previous=player_history[k]
            prev_teams=team_history[team_k]
            if day>=begin:
                if len(previous)<3 or len(prev_teams)<3:
                    missing[row["metric"]]+=1
                else:
                    recent_player=previous[-4:]
                    recent_team=prev_teams[-4:]
                    base=_avg([p["observed_player_opportunities"] for p in recent_player])
                    proposed=_avg([p["role_share"] for p in recent_player])*_avg(
                        [t["observed_team_opportunities"] for t in recent_team])
                    actual=row["observed_player_opportunities"]
                    tested[row["metric"]].append({
                        "date":day.isoformat(),"game_id":row["game_id"],
                        "team_id":row["team_id"],"player_id":row["player_id"],
                        "player_name":row["player_name"],"share_basis":row["share_type"],
                        "actual":actual,"baseline":base,"role_candidate":proposed,
                        "baseline_abs_error":abs(actual-base),
                        "role_abs_error":abs(actual-proposed),
                        "prior_recorded_player_games":len(previous),
                        "prior_recorded_team_games":len(prev_teams),
                    })
            pending_player.append((k,row))
            tkey=(row["game_id"],row["team_id"],row["metric"])
            pending_team[tkey]=(team_k,row)
        # Same football date embargo: no game on this date is used until
        # ALL this date's forecasts are fully evaluated.
        for k,row in pending_player:player_history[k].append(row)
        for team_k,row in pending_team.values():team_history[team_k].append(row)
    summary={}
    for metric,(name,basis) in STAT_ROLE.items():
        recs=tested[metric];n=len(recs)
        baseline=round(_avg([x["baseline_abs_error"] for x in recs]),5) if n else None
        role=round(_avg([x["role_abs_error"] for x in recs]),5) if n else None
        summary[metric]={
            "opportunity_stat":name,"share_basis":basis,
            "paired_recorded_stat_player_games":n,
            "baseline_mean_abs_error":baseline,
            "role_candidate_mean_abs_error":role,
            "role_minus_baseline_mae":round(role-baseline,5) if n else None,
            "insufficient_prior_records":missing[metric],
            "automatically_promoted":False}
    return {
        "status":STATUS,"season":2026,"first_test_date":start,
        "source_observed_at_utc":snapshot["observed_at_utc"],
        "summary":summary,"excluded_source_rows":excluded,
        "sample_predictions":{k:v[:25] for k,v in tested.items()},
        "missing_player_is_not_zero_filled":True,
        "category_participation_selection_bias":True,
        "historical_original_publication_times_verified":False,
        "reception_share_is_not_target_share":True,
        "passing_attempt_share_is_not_snap_share":True,
        "no_live_lineup_health_or_playing_time_confirmation":True,
        "no_actual_sportsbook_prop_lines_or_roi":True,
        "model_promoted":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED",
    }

def run(input,output):
    snapshot=json.loads(Path(input).read_text(encoding="utf-8"))
    result=evaluate(snapshot)
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":STATUS,"summary":result["summary"],"model_promoted":False}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.input,a.output)

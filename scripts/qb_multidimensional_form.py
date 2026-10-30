
"""QB passing, pressure, sacks, scrambling, designed rushing and giveaways.

Only accepted *player-attributed* historical observations received before the
decision; pregame source timing is not retroactively authenticated. Named
passing leader is NOT a confirmed starter. Verified transfer ID crosswalks
allow weak, uncertainty-aware prior-season/team data rather than zero-tape.
No guessed pressure response, rushing attribution or QB point effect.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
from urllib.parse import urlsplit
from scripts.game_context import parse_time

STATUS="QB_MULTIDIMENSIONAL_FORM_RESEARCH_ONLY"
SOURCE="QB_PLAYER_ATTRIBUTED_PBP_OBSERVED_RESEARCH_ONLY"
COUNT_FIELDS=("pressured_dropbacks","clean_dropbacks","qb_scrambles",
              "qb_designed_rushes","sacks_taken","offensive_turnovers")
SUM_FIELDS=("pressured_epa_sum","clean_epa_sum","scramble_epa_sum","designed_rush_epa_sum")
DECAY=.80
TRANSFER_PRIOR_WEIGHT=.55
OLDER_SEASON_WEIGHT=.60

def _finite(x):
    return type(x) in (int,float) and math.isfinite(x)

def _url(url):
    try:
        p=urlsplit(url)
        return p.scheme=="https" and bool(p.hostname)
    except (TypeError,ValueError):return False

def _validate(row):
    if (row.get("status")!=SOURCE or not row.get("player_id") or not row.get("team")
        or not row.get("opponent") or row["team"]==row["opponent"]
        or row.get("player_identity_crosswalk_verified") is not True
        or not _url(row.get("source_url"))):
        raise ValueError("Untrusted player-attributed QB source")
    kickoff=parse_time(row["kickoff_utc"])
    observed=parse_time(row["source_observed_at_utc"])
    if kickoff>=observed:raise ValueError("Postgame source must follow actual game")
    if row.get("season") not in (2025,2026):
        raise ValueError("Unsupported transfer/prior football season")
    for field in COUNT_FIELDS:
        if type(row.get(field)) is not int or not 0<=row[field]<=120:
            raise ValueError("Invalid observed QB attempt/sack/turnover count")
    for field in SUM_FIELDS:
        if not _finite(row.get(field)) or abs(row[field])>1500:
            raise ValueError("Invalid sourced QB EPA total")
    if row["sacks_taken"]>row["pressured_dropbacks"]+row["clean_dropbacks"]:
        raise ValueError("Sack count exceeds observed QB dropbacks")
    if row["offensive_turnovers"]>sum(row[k] for k in (
            "pressured_dropbacks","clean_dropbacks","qb_scrambles","qb_designed_rushes")):
        raise ValueError("Unattributable player turnovers")
    return kickoff,observed

def profile(observations,player_id,current_team,target_kickoff_utc,decision_utc,
            opponent_pressure_rate=None,opponent_pressure_observed_at_utc=None):
    decision=parse_time(decision_utc)
    kickoff=parse_time(target_kickoff_utc)
    if not decision<kickoff or not player_id or not current_team:
        raise ValueError("Pregame QB player/clock identity missing")
    if opponent_pressure_rate is not None:
        if (not _finite(opponent_pressure_rate) or not 0<=opponent_pressure_rate<=1 or
            not opponent_pressure_observed_at_utc or
            parse_time(opponent_pressure_observed_at_utc)>decision):
            raise ValueError("Future or unverified opponent pressure input")
    relevant=[];excluded={"future_capture":0,"unverified_transfer":0,"target_or_later_game":0}
    seen=set()
    for row in observations:
        if row.get("player_id")!=player_id:continue
        past,observed=_validate(row)
        if str(row["game_id"]) in seen:raise ValueError("Duplicate QB identity/game observation")
        seen.add(str(row["game_id"]))
        if past>=kickoff or dt.date.fromisoformat(row["date"])>=kickoff.date():
            excluded["target_or_later_game"]+=1;continue
        if observed>decision:
            excluded["future_capture"]+=1;continue
        transferred=row["team"]!=current_team
        if transferred and (row.get("transfer_identity_verified") is not True
                            or not row.get("transfer_source_url")
                            or not _url(row["transfer_source_url"])
                            or not row.get("transfer_observed_at_utc")
                            or parse_time(row["transfer_observed_at_utc"])>decision):
            excluded["unverified_transfer"]+=1;continue
        weight=(TRANSFER_PRIOR_WEIGHT if transferred else 1.) * (
            OLDER_SEASON_WEIGHT if row["season"]<kickoff.year else 1.)
        relevant.append((past,row,weight))
    relevant.sort(key=lambda x:x[0],reverse=True)
    relevant=relevant[:8]
    totals={k:0. for k in COUNT_FIELDS+SUM_FIELDS}
    for i,(_,r,w) in enumerate(relevant):
        recency=w*(DECAY**i)
        for k in totals:totals[k]+=recency*r[k]
    def ratio(a,b,min_sample=1):
        return round(totals[a]/totals[b],6) if totals[b]>=min_sample else None
    attempts=totals["pressured_dropbacks"]+totals["clean_dropbacks"]
    touches=attempts+totals["qb_scrambles"]+totals["qb_designed_rushes"]
    press=ratio("pressured_epa_sum","pressured_dropbacks",minimum_pressure_attempts)
    clean=ratio("clean_epa_sum","clean_dropbacks",minimum_clean_attempts)
    pass_delta=(round(press-clean,6) if press is not None and clean is not None else None)
    expected=(round(opponent_pressure_rate*press+(1-opponent_pressure_rate)*clean,6)
              if opponent_pressure_rate is not None and press is not None and clean is not None
              else None)
    trusted=sum(row["team"]==current_team for _,row,_ in relevant)
    return {
        "status":STATUS,"player_id":player_id,"team":current_team,
        "decision_utc":decision.isoformat(),
        "prior_games_evidenced":len(relevant),
        "same_team_games":trusted,
        "transfer_or_prior_team_games":len(relevant)-trusted,
        "excluded":excluded,
        "weighted_dropbacks":round(attempts,4),
        "weighted_rush_touches":round(totals["qb_scrambles"]+totals["qb_designed_rushes"],4),
        "pressured_epa_per_dropback":press,
        "clean_epa_per_dropback":clean,
        "pressure_penalty_epa_per_dropback":pass_delta,
        "sack_rate_per_dropback":round(totals["sacks_taken"]/attempts,6) if attempts>=10 else None,
        "scramble_epa_per_run":ratio("scramble_epa_sum","qb_scrambles",3),
        "designed_run_epa_per_carry":ratio("designed_rush_epa_sum","qb_designed_rushes",3),
        "turnovers_per_observed_touch":round(totals["offensive_turnovers"]/touches,6)
             if touches>=10 else None,
        "pressure_matched_epa_per_dropback":expected,
        "opponent_pressure_rate_observed":opponent_pressure_rate,
        "sample_sufficient_for_pressure_matchup":expected is not None,
        "source_timing_verified_live_as_observed":True,
        "historical_first_pbp_publication_verified":False,
        "starting_qb_confirmed_from_pbp":False,
        "qb_point_adjustment":None,
        "model_promoted":False,
        "safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED",
    }

minimum_pressure_attempts=8
minimum_clean_attempts=12

def run(history,current,decision,output):
    source=json.loads(Path(history).read_text())["observations"]
    target=json.loads(Path(current).read_text())
    result=profile(source,target["player_id"],target["team"],
         target["kickoff_utc"],decision,
         target.get("opponent_pressure_rate"),target.get("opponent_pressure_observed_at_utc"))
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True);p.add_argument("--target",required=True)
    p.add_argument("--decision",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.history,a.target,a.decision,a.output)

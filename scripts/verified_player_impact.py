
"""Learn an all-roster, usage-weighted *reported* availability adjustment.

This is NOT an injury diagnosis, causal individual replacement rating, player
medical data, or permission to modify V03. Every eligible player needs a
source-linked identity crosswalk and PREDECISION participation/role share.
Unlisted players are unknown, not healthy. Estimate group effects on residuals
of independently frozen baseline forecasts, with older observed finals only.
No fabricated partial-game point penalty, questionable-play probability or
transfer carryover. Missing source => explicit PASS.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
from scripts.game_context import parse_time

STATUS="VERIFIED_PLAYER_IMPACT_RESEARCH_ONLY"
GROUPS=("QB","SKILL","OL","FRONT","SECONDARY","SPECIAL","OTHER")
LABELS=("FULL_OUT","FIRST_HALF_OUT","UNCERTAIN")
FEATURES=tuple(group+"_"+kind for group in GROUPS for kind in LABELS)+(
    "HOME_OL_VS_DEFENSIVE_PRESSURE","AWAY_OL_VS_DEFENSIVE_PRESSURE",
    "HOME_QB_VS_DEFENSIVE_PRESSURE","AWAY_QB_VS_DEFENSIVE_PRESSURE")
GROUP_MAP={"QB":"QB","RB":"SKILL","WR":"SKILL","TE":"SKILL",
           "OL":"OL","DL":"FRONT","EDGE":"FRONT","LB":"FRONT",
           "CB":"SECONDARY","DB":"SECONDARY","S":"SECONDARY",
           "K":"SPECIAL","P":"SPECIAL","OTHER":"OTHER"}
OUT={"OUT","SUSPENDED"}
PARTIAL={"OUT_FIRST_HALF"}
UNCERTAIN={"QUESTIONABLE","DOUBTFUL","GAME_TIME_DECISION","LIMITED"}
OTHER={"AVAILABLE","PROBABLE","UNKNOWN"}

def _url(url):
    try:
        p=urlsplit(url)
        return p.scheme=="https" and bool(p.hostname) and not p.username and not p.password
    except (ValueError,TypeError):
        return False

def _finite(v):
    return type(v) in (int,float) and math.isfinite(v)

def features(game,decision_utc):
    """Return no numeric injury effects without BOTH source-reviewed sides."""
    decision=parse_time(decision_utc)
    issued=parse_time(game["captured_at_utc"])
    kickoff=parse_time(game["kickoff_utc"])
    if not issued<=decision<kickoff:raise ValueError("Future/postkickoff roster evidence")
    if game.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Untrusted pregame roster source")
    sides=game.get("sides") or {}
    if set(sides)!={"home","away"} or game["home"]==game["away"]:
        raise ValueError("Incomplete matchup teams")
    impact={f:0. for f in FEATURES}
    names=[];unusable=[]
    side_totals={}
    for side in ("home","away"):
        item=sides[side]
        if item.get("team")!=game[side]:
            raise ValueError("Roster team does not match ESPN fixture")
        if item.get("coverage")!="VERIFIED_REPORT_REVIEWED":
            return {"status":"PASS_UNVERIFIED_TEAM_REPORT","features":None,
                    "unlisted_players":"UNKNOWN","missing_player_data":None}
        players=item.get("reported_players")
        if not isinstance(players,list):
            raise ValueError("Verified team report has no player array")
        seen=set();totals=defaultdict(float)
        for p in players:
            name=p.get("player_id")
            position=p.get("position")
            stat=p.get("reported_status")
            if not name or name in seen or position not in GROUP_MAP or stat not in OUT|PARTIAL|UNCERTAIN|OTHER:
                raise ValueError("Unknown or duplicate player identity, position, designation")
            seen.add(name)
            if stat in OTHER:
                continue
            if (p.get("identity_crosswalk_verified") is not True or
                p.get("pregame_role_share_verified") is not True or
                not _finite(p.get("prior_snap_share")) or not 0<=p["prior_snap_share"]<=1 or
                type(p.get("prior_games_observed")) is not int or p["prior_games_observed"]<2 or
                not _url(p.get("status_source_url")) or not _url(p.get("role_source_url")) or
                parse_time(p["status_published_at_utc"])>issued or
                parse_time(p["role_source_observed_at_utc"])>issued):
                unusable.append({"side":side,"player_id":name,"reason":"IDENTITY_ROLE_OR_SOURCE_UNVERIFIED"})
                continue
            group=GROUP_MAP[position]
            label=("FULL_OUT" if stat in OUT else "FIRST_HALF_OUT" if stat in PARTIAL
                   else "UNCERTAIN")
            signed=float(p["prior_snap_share"])*(1 if side=="home" else -1)
            impact[group+"_"+label]+=signed
            totals[group+"_"+label]+=float(p["prior_snap_share"])
            names.append({"side":side,"player_id":name,"position":position,
                          "designation":stat,"prior_snap_share":p["prior_snap_share"]})
        side_totals[side]=totals
    if unusable:
        # Distinguish absent from unknown: never complete a group total by zero.
        return {"status":"PASS_PLAYER_ROLE_OR_IDENTITY_MISSING","features":None,
                "missing_player_data":unusable,"unlisted_players":"UNKNOWN"}
    # Defensive pressure is an independently sourced past-only team feature;
    # missing pressure leaves interactions NULL and no learned adjustment.
    pressure={}
    for side in ("home","away"):
        value=game["sides"][side].get("opponent_pressure_rate")
        at=game["sides"][side].get("pressure_source_observed_at_utc")
        if value is None or not _finite(value) or not 0<=value<=1 or not at or parse_time(at)>issued:
            return {"status":"PASS_OPPONENT_PRESSURE_SOURCE_MISSING","features":None,
                    "unlisted_players":"UNKNOWN","missing_player_data":[]}
        pressure[side]=value
    for side in ("home","away"):
        for group in ("OL","QB"):
            impact[side.upper()+"_"+group+"_VS_DEFENSIVE_PRESSURE"]=round(
                side_totals[side].get(group+"_FULL_OUT",0.)*pressure[side],8)
            if side=="away":
                # Preserve home-margin sign for away absences, as with position burdens.
                impact[side.upper()+"_"+group+"_VS_DEFENSIVE_PRESSURE"] *= -1
    return {"status":"SOURCE_READY_RESEARCH_ONLY","features":impact,
            "reported_absent_and_uncertain_player_exposures":names,
            "unlisted_players":"UNKNOWN","missing_player_data":[]}

def fit_training(records,decision_utc,min_games=60,ridge=65.):
    decision=parse_time(decision_utc)
    if type(min_games) is not int or min_games<20 or ridge<=0:
        raise ValueError("Unsafe player impact training policy")
    xs=[];ys=[];seen=set();cutoffs=set();reasons=defaultdict(int)
    for row in records:
        game=row["pregame"]
        gid=str(game["game_id"])
        if gid in seen:raise ValueError("Duplicate training game")
        seen.add(gid)
        outcome=parse_time(row["outcome_known_at_utc"])
        if not (parse_time(game["captured_at_utc"])<
                parse_time(game["kickoff_utc"])<outcome<decision):
            raise ValueError("Train contains future final or retroactive pregame capture")
        if (row.get("frozen_baseline_hash") is None or
            len(str(row["frozen_baseline_hash"]))!=64 or
            row.get("observed_final_source") is None or
            not _url(row["observed_final_source"])):
            raise ValueError("No independently frozen prediction and observed source")
        projection=row["frozen_baseline_home_margin"]
        actual=row["actual_home_margin"]
        if not _finite(projection) or not _finite(actual):
            raise ValueError("Invalid verified final or historical baseline")
        signal=features(game,game["captured_at_utc"])
        if signal["features"] is None:
            reasons[signal["status"]]+=1
            continue
        xs.append([signal["features"][f] for f in FEATURES])
        ys.append(float(actual-projection))
        cutoffs.add(str(game["kickoff_utc"])[:10])
    if len(xs)<min_games or len(cutoffs)<4:
        return {"status":"PASS_INSUFFICIENT_PRIOR_VERIFIED_PLAYER_GAMES",
                "usable_training_games":len(xs),
                "excluded_reasons":dict(reasons),
                "coefficients":None,"model_promoted":False}
    x=np.asarray(xs,dtype=float);y=np.asarray(ys,dtype=float)
    varying=np.std(x,axis=0)
    if np.count_nonzero(varying>1e-6)<2:
        return {"status":"PASS_NO_INDEPENDENT_PLAYER_AVAILABILITY_VARIATION",
                "usable_training_games":len(xs),
                "excluded_reasons":dict(reasons),
                "coefficients":None,"model_promoted":False}
    # No intercept: target is residual relative to separately frozen V03.
    # Full rank not required; ridge regularization and shrinkage suppress
    # unstable thin player/position groups.
    beta=np.linalg.solve(x.T@x+np.eye(len(FEATURES))*ridge,x.T@y)
    return {"status":"FITTED_PRIOR_EVIDENCE_RESEARCH_ONLY",
            "asof_utc":decision.isoformat(),"usable_training_games":len(xs),
            "training_days":len(cutoffs),"ridge":ridge,
            "coefficients":{f:float(v) for f,v in zip(FEATURES,beta)},
            "excluded_reasons":dict(reasons),
            "individually_causal_player_values_established":False,
            "prospective_accuracy_established":False,
            "model_promoted":False}

def estimate(game,model,decision_utc):
    signal=features(game,decision_utc)
    if signal["features"] is None or model.get("status")!="FITTED_PRIOR_EVIDENCE_RESEARCH_ONLY":
        return {"status":"PASS_INCOMPLETE_EVIDENCE_OR_TRAINING",
                "source_status":signal["status"],"home_margin_adjustment":None,
                "model_promoted":False}
    if parse_time(model["asof_utc"])>parse_time(decision_utc):
        raise ValueError("Postdecision player model leakage")
    coeff=model["coefficients"]
    if set(coeff)!=set(FEATURES) or any(not _finite(x) for x in coeff.values()):
        raise ValueError("Corrupt player replacement fit")
    adjustment=sum(signal["features"][f]*coeff[f] for f in FEATURES)
    return {"status":"PLAYER_IMPACT_RESEARCH_CANDIDATE",
            "home_margin_adjustment":round(float(adjustment),6),
            "reported_player_exposures":signal["reported_absent_and_uncertain_player_exposures"],
            "unlisted_players":"UNKNOWN","model_promoted":False,
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

def run(training_path,current_path,decision,output):
    rows=json.loads(Path(training_path).read_text())["games"]
    game=json.loads(Path(current_path).read_text())
    trained=fit_training(rows,decision)
    forecast=estimate(game,trained,decision)
    result={"status":STATUS,"training":trained,"forecast":forecast,
            "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--training",required=True);p.add_argument("--current",required=True)
    p.add_argument("--decision",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.training,a.current,a.decision,a.output)

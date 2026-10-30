"""As-of empirical passer-use mixture, NOT a next-game starter probability.

The most recent two distinct games contribute named QB pass-play exposure.
Each game's denominator is independently recorded total offensive pass plays;
unattributed or unlisted passers retain UNKNOWN mass. These are descriptive
participation shares, not calibrated probabilities a QB starts next week.
History was received before the decision and game occurred before kickoff.
"""
import datetime as dt
import math
from collections import defaultdict
from zoneinfo import ZoneInfo
from scripts.game_context import parse_time
from scripts.qb_passer_history import player_key

STATUS="QB_EMPIRICAL_PASS_EXPOSURE_MIXTURE_RESEARCH_ONLY"
MIN_NAMED_COVERAGE=.70
DECAY=(2./3.,1./3.)  # latest game, preceding game; fixed, not tuned to results
MAX_GAMES=2
INACTIVE={"OUT","SUSPENDED","CONFLICT"}

def _number(raw):
    if type(raw) is bool:raise ValueError("Boolean pass count")
    try:n=float(raw)
    except (ValueError,TypeError):raise ValueError("Invalid historical pass count")
    if not math.isfinite(n) or n<0 or not n.is_integer():
        raise ValueError("Nonintegral or negative historical pass count")
    return int(n)

def mixture(rows,team,slot,game_date,observed_at):
    """Return player weights and residual UNKNOWN; does not assert QB starter."""
    cutoff=dt.date.fromisoformat(game_date)
    decision=parse_time(observed_at)
    if decision.astimezone(ZoneInfo("America/New_York")).date()>cutoff:
        raise ValueError("QB mixture calculated after target game date")
    if slot.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Untrusted QB expected starter slate")
    available={}
    for c in slot.get("scenarios",[]):
        name=c.get("player")
        if not isinstance(name,str) or not player_key(name):raise ValueError("Bad charted QB")
        key=player_key(name)
        if key in available:raise ValueError("Duplicate normalized candidate QB")
        available[key]=name
    statuses={player_key(n):v.get("status") for n,v in
              (slot.get("availability_by_player") or {}).items()}
    # These candidates are projected eligible, not confirmed healthy.
    for k in list(available):
        if statuses.get(k) in INACTIVE:del available[k]
    if slot.get("is_confirmed_starter"):
        key=player_key(slot.get("starter") or "")
        if key not in available or statuses.get(key) in INACTIVE:
            raise ValueError("Official starter conflicts with available candidates")
        return {"status":"REVIEWED_GAME_SPECIFIC_STARTER_SCENARIO",
            "source":STATUS,"weights":{name:(1. if k==key else 0.) for k,name in available.items()},
            "unknown_weight":0.,"accepted_past_games":0,"rejected_past_games":0,
            "not_starter_probabilities":True,"calibrated":False,
            "assumptions":"Verified exact-game starter only, not calibrated injury or snap-share forecast."}
    grouped=defaultdict(list)
    seen=set()
    for row in rows:
        if row.get("team")!=team:continue
        if row.get("betting_status")!="PASS_UNVALIDATED" or row.get(
            "historical_source_time_verified") not in (False,"False","false"):
            raise ValueError("Untrusted historical passer data")
        date=dt.date.fromisoformat(row["date"])
        source=parse_time(row["source_retrieved_at_utc"])
        if source>decision or date>=cutoff:continue
        player=player_key(row["player"])
        if not player:raise ValueError("Empty historical passer ID")
        key=(str(row["game_id"]),player)
        if key in seen:raise ValueError("Duplicate named passer game attribution")
        seen.add(key)
        grouped[(date,str(row["game_id"]))].append(row)
    accepted=[];quality_ignored=0
    for (day,gid) in sorted(grouped,reverse=True)[:MAX_GAMES]:
        game=grouped[(day,gid)]
        totals={_number(r.get("team_pass_tagged_plays")) for r in game
                if r.get("team_pass_tagged_plays") not in (None,"")}
        if len(totals)!=1:
            quality_ignored+=1;continue
        total=next(iter(totals))
        counts={player_key(r["player"]):_number(r["pass_tagged_plays"]) for r in game}
        if (total==0 or sum(counts.values())>total or
            sum(counts.values())/total<MIN_NAMED_COVERAGE):
            quality_ignored+=1;continue
        # Availability is applied to expected *future* participation, not to
        # observed past counts: the OUT player contributes UNKNOWN mass.
        accepted.append((day,gid,total,counts))
    if not available or not accepted:
        return {"status":"PASS_NO_SOURCED_PRIOR_QB_EXPOSURE",
            "source":STATUS,"weights":{name:0. for name in available.values()},
            "unknown_weight":1.,"accepted_past_games":0,
            "rejected_past_games":quality_ignored,
            "not_starter_probabilities":True,"calibrated":False}
    raw=defaultdict(float)
    # Re-normalize 2:1 recency fractions when only one prior game qualifies.
    coeffs=DECAY[:len(accepted)]
    denom=sum(coeffs)
    for w,(_,_,total,counts) in zip(coeffs,accepted):
        for k,count in counts.items():
            if k in available:raw[k]+=w/denom*count/total
    weights={name:round(raw[key],8) for key,name in available.items()}
    # Calculate residual from rounded published values and never distribute it
    # among candidates with no actual named pass-use evidence.
    unknown=round(max(0.,1.-sum(weights.values())),8)
    if not 0<=unknown<=1.00000001:raise ValueError("Invalid exposure mass")
    return {"status":STATUS,"source":STATUS,"weights":weights,
        "unknown_weight":unknown,
        "accepted_past_games":len(accepted),
        "rejected_past_games":quality_ignored,
        "past_game_ids":[gid for _,gid,_,_ in accepted],
        "sample_coverage":[round(sum(counts.values())/total,6) for _,_,total,counts in accepted],
        "recency_rule":"LATEST_TWO_GAMES_2_TO_1",
        "not_starter_probabilities":True,
        "calibrated":False,
        "assumptions":"Observed pass usage is a descriptive scenario mix, NOT an estimated next-game starter probability; unknown carries missing-source/untagged/inactive/other-QB mass."}

"""Verified historical *team* opportunity budgets for joint player simulations.

Uses explicitly source-reviewed complete prior team passing/rushing attempts.
There is NO assertion that ESPN sparse player box rows are a complete roster:
unmodelled players retain a nonnegative residual. Without a verified source,
the simulation remains an unconstrained shadow and reports that limitation.
"""
import math
from collections import defaultdict
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from scripts.game_context import parse_time

STATUS="REVIEWED_PAST_TEAM_PLAY_ATTEMPT_BUDGETS_RESEARCH_ONLY"
MIN_GAMES_PER_TEAM=3
EASTERN=ZoneInfo("America/New_York")


def _https(value):
    try:
        u=urlsplit(value)
        return u.scheme=="https" and bool(u.netloc)
    except (TypeError,ValueError):
        return False


def prepare(bundle,target,possession_rows,decision):
    """Fail closed on falsified sources; return (per_side, readiness_reason)."""
    if bundle is None:
        return None,"PASS_NO_REVIEWED_TEAM_ATTEMPT_BUDGET_SOURCE"
    when=parse_time(decision)
    if (bundle.get("status")!=STATUS or bundle.get("season")!=2026 or
        bundle.get("betting_status")!="PASS_UNVALIDATED" or
        bundle.get("safe_for_betting") is not False or
        bundle.get("model_promoted") is not False or
        parse_time(bundle["observed_at_utc"])>when):
        raise ValueError("Invalid or future team attempt budget source")
    identities=target.get("team_ids")
    if (not isinstance(identities,dict) or set(identities)!={"home","away"} or
        not all(str(identities[s]).isdigit() for s in ("home","away")) or
        identities["home"]==identities["away"]):
        raise ValueError("Reviewed team play budgets require exact two-team IDs")
    if (str(bundle.get("target_game_id"))!=str(target["game_id"]) or
        bundle.get("target_kickoff_utc")!=target["kickoff_utc"]):
        raise ValueError("Budget fixture cannot be reused for a different game")
    possessed={(str(r["game_id"]),str(r["team_id"])):r for r in possession_rows}
    prior=defaultdict(list)
    seen=set()
    for r in bundle.get("rows",[]):
        team=str(r.get("team_id",""))
        game=str(r.get("game_id",""))
        pair=(game,team)
        if pair in seen:raise ValueError("Duplicate verified team attempts")
        seen.add(pair)
        if team not in set(map(str,identities.values())):
            raise ValueError("Budget source mixes opponent or unknown team")
        clock=parse_time(r["kickoff_utc"])
        final=parse_time(r["outcome_known_at_utc"])
        observed=parse_time(r["captured_at_utc"])
        if (not clock<final<=observed<=when or
            not clock<parse_time(target["kickoff_utc"]) or
            clock.astimezone(EASTERN).date().isoformat()>=target["date"]):
            raise ValueError("Budgets are postgame, postdecision or same football day")
        if (r.get("complete_team_attempts_reviewed") is not True or
            not _https(r.get("source_url"))):
            raise ValueError("Unreviewed or incomplete team attempts")
        attempts=[]
        for stat in ("passing_attempts","rushing_attempts"):
            value=r.get(stat)
            if type(value) is not int or not 0<=value<=110:
                raise ValueError("Invalid audited team attempt count")
            attempts.append(value)
        if sum(attempts)==0:
            raise ValueError("Empty verified team offense")
        poss=possessed.get(pair)
        if (poss is None or type(poss.get("team_possessions")) is not int or
            not 1<=poss["team_possessions"]<=24 or
            parse_time(poss["observed_at_utc"])>when):
            raise ValueError("Team attempts missing matched reviewed possession identity")
        prior[team].append({**r,"historical_possessions":poss["team_possessions"]})
    sides={}
    for side in ("home","away"):
        tid=str(identities[side])
        ordered=sorted(prior[tid],key=lambda x:(x["kickoff_utc"],str(x["game_id"])),reverse=True)[:8]
        if len(ordered)<MIN_GAMES_PER_TEAM:
            return None,"PASS_INSUFFICIENT_COMPLETE_HISTORICAL_TEAM_ATTEMPTS"
        sides[side]=ordered
    return sides,"READY_CONDITIONAL_BUDGET_SHADOW"


def bounded_counts(proposed,limit):
    """Hamilton proportional cap: exact integer conservation with residual.

    Players not present in the target roster are never silently assigned zero.
    Missing/unprojected opportunities remain in the unallocated bucket.
    """
    if type(limit) is not int or limit<0:raise ValueError("Invalid team opportunity cap")
    if any(type(v) is not int or v<0 for v in proposed):
        raise ValueError("Invalid athlete proposed opportunity")
    total=sum(proposed)
    if total<=limit:return list(proposed),limit-total
    if total==0:return list(proposed),limit
    amounts=[v*limit/total for v in proposed]
    allocated=[int(math.floor(v)) for v in amounts]
    leftovers=limit-sum(allocated)
    ranks=sorted(range(len(proposed)),key=lambda i:(-(amounts[i]-allocated[i]),i))
    for i in ranks[:leftovers]:allocated[i]+=1
    return allocated,0


def conserve_trial(samples,caps):
    """In-place cap of modeled subset, preserving sparse unobserved categories.

    Samples: player_id -> {side, values:{stat:int}} from same trial/pace.
    caps: side -> {passing_attempts:int, rushing_attempts:int}.
    This enforces attempts and logical completions/receptions but not
    calibrated target shares or true DNP probabilities.
    """
    residual={}
    for side in ("home","away"):
        people=[x for x in samples.values() if x["side"]==side]
        residual[side]={}
        for metric,yards,td in (
            ("passing_attempts","passing_yards","passing_touchdowns"),
            ("rushing_attempts","rushing_yards","rushing_touchdowns")):
            participating=[p["values"] for p in people if metric in p["values"]]
            proposed=[v[metric] for v in participating]
            cap=caps[side][metric]
            assigned,rest=bounded_counts(proposed,cap)
            residual[side][metric]=rest
            for v,old,new in zip(participating,proposed,assigned):
                v[metric]=new
                if yards in v:
                    v[yards]=int(round(v[yards]*(new/old))) if old else 0
                if td in v:
                    v[td]=min(v[td],new)
                if metric=="passing_attempts":
                    if "passing_completions" in v:
                        v["passing_completions"]=min(v["passing_completions"],new)
                    if "interceptions" in v and "passing_completions" in v:
                        v["interceptions"]=min(v["interceptions"],
                                                new-v["passing_completions"])
                    if "passing_touchdowns" in v and "passing_completions" in v:
                        v["passing_touchdowns"]=min(v["passing_touchdowns"],
                                                   v["passing_completions"])
        # Modeled catches cannot outnumber modeled completed passes PLUS
        # unallocated (unknown-player) pass attempts. Missing completions
        # remain unknown; the upper bound is conservative, not a forecast.
        known_completions=sum(v["values"].get("passing_completions",0) for v in people)
        max_catches=min(caps[side]["passing_attempts"],
                        known_completions+residual[side]["passing_attempts"])
        receivers=[p["values"] for p in people if "receptions" in p["values"]]
        receptions=[v["receptions"] for v in receivers]
        assigned,rest=bounded_counts(receptions,max_catches)
        residual[side]["receptions_upper_bound_unallocated"]=rest
        for v,old,new in zip(receivers,receptions,assigned):
            v["receptions"]=new
            if "receiving_yards" in v:
                v["receiving_yards"]=int(round(v["receiving_yards"]*(new/old))) if old else 0
            if "receiving_touchdowns" in v:
                v["receiving_touchdowns"]=min(v["receiving_touchdowns"],new)
    return residual

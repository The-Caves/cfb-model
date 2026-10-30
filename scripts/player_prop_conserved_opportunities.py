"""Conservation-first, empirically budgeted CFB player-opportunity simulation.

Research only. Per-team play volumes are sampled from previously observed,
source-dated team box games, scaled by SAME-game simulated possession counts.
All passer attempts, completions, passing/receiving yards, targets, catches,
rush attempts and rush yards reconcile EXACTLY per trial. Unknown athletes
retain explicit OTHER_QB / OTHER_RECEIVER / OTHER_RUSHER buckets; the source
does NOT establish a complete starting lineup or a valid prop betting edge.

No touchdowns, red-zone attribution, defensive returns, sack assignment,
player absence probability, target-catch skill, or actual betting projections.
"""
import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from scripts.game_context import parse_time
from scripts.game_simulation_research import _sample, validate_inputs

STATUS="CONSERVATION_FIRST_PLAYER_OPPORTUNITY_RESEARCH_ONLY"
SOURCE="PREDECISION_TEAM_BOX_AND_ROLE_EVIDENCE_RESEARCH_ONLY"
BUDGET_FIELDS=("pass_attempts","pass_completions","pass_yards",
               "rush_attempts","rush_yards","possessions")
ROLES={
    "pass_attempt_share":("QB","OTHER_QB"),
    "target_share":("RECEIVER","OTHER_RECEIVER"),
    "carry_share":("RUSHER","OTHER_RUSHER"),
}
OTHER={"OTHER_QB","OTHER_RECEIVER","OTHER_RUSHER"}

def _url(s):
    try:
        u=urlsplit(s)
        return u.scheme=="https" and bool(u.hostname) and u.username is None
    except (ValueError,TypeError):
        return False

def _int(x,lo,hi):
    return type(x) is int and lo<=x<=hi

def _finite(x):
    return type(x) in (int,float) and math.isfinite(x)

def _validate(profile,gamefit,decision_utc):
    validate_inputs(gamefit,decision_utc)
    now=parse_time(decision_utc)
    kick=parse_time(gamefit["kickoff_utc"])
    if (profile.get("status")!=SOURCE or profile.get("betting_status")!="PASS_UNVALIDATED"
        or profile.get("safe_for_betting") is not False or
        parse_time(profile["captured_at_utc"])>now or
        set(profile.get("teams",{}))!={"home","away"}):
        raise ValueError("Missing or future source-backed team opportunity evidence")
    for side in ("home","away"):
        team=profile["teams"][side]
        if (team.get("team")!=gamefit[side] or
            team.get("roster_coverage")!="PARTIAL_VERIFIED_SOURCE_REVIEWED" or
            not isinstance(team.get("prior_games"),list) or
            len(team["prior_games"])<3 or
            not isinstance(team.get("players"),list)):
            raise ValueError("Missing prior team form or incomplete role evidence")
        games_seen=set()
        for g in team["prior_games"]:
            ident=str(g["game_id"])
            observed=parse_time(g["observed_at_utc"])
            last=parse_time(g["outcome_known_at_utc"])
            prior_kick=parse_time(g["kickoff_utc"])
            if (ident in games_seen or not ident or
                not prior_kick<last<=observed<=now or prior_kick>=kick or
                not _url(g.get("source_url")) or
                not _int(g.get("pass_attempts"),0,90) or
                not _int(g.get("pass_completions"),0,90) or
                not _int(g.get("pass_yards"),0,1000) or
                not _int(g.get("rush_attempts"),0,100) or
                not _int(g.get("rush_yards"),-200,900) or
                not _int(g.get("possessions"),1,24) or
                g["pass_completions"]>g["pass_attempts"] or
                (g["pass_completions"]==0 and g["pass_yards"]!=0)):
                raise ValueError("Unverified or internally inconsistent prior team box")
            games_seen.add(ident)
        seen=set()
        weights=defaultdict(float)
        for p in team["players"]:
            pid=str(p.get("player_id",""))
            if (not pid or pid in seen or pid in OTHER or
                p.get("availability") not in ("CONFIRMED_ACTIVE","UNCONFIRMED_EXPECTED") or
                p.get("role_evidence_reviewed") is not True or
                not _url(p.get("source_url")) or
                parse_time(p["source_observed_at_utc"])>now):
                raise ValueError("Missing unique predecision player role/status source")
            seen.add(pid)
            supplied=0
            for field in ROLES:
                value=p.get(field)
                if value is None:continue
                if not _finite(value) or not 0<=value<=1:
                    raise ValueError("Bad player role share")
                supplied+=value>0
                weights[field]+=value
            if not supplied:
                raise ValueError("No supported role opportunity for named player")
            if p.get("target_share",0)>0 and (
                    not _finite(p.get("receiving_yards_per_catch")) or
                    not 0<p["receiving_yards_per_catch"]<=80):
                raise ValueError("Unverified receiver efficiency")
            if p.get("carry_share",0)>0 and (
                    not _finite(p.get("rushing_yards_per_carry")) or
                    not 0<p["rushing_yards_per_carry"]<=40):
                raise ValueError("Unverified rusher efficiency")
        if any(x>=1-1e-10 for x in weights.values()):
            # With only a partial reviewed roster, a 100% named-player
            # share would imply unknown player opportunity is exactly zero.
            raise ValueError("Unmodeled-player source coverage may not be zero")
        if not any(x>0 for x in weights.values()):
            raise ValueError("Only unknown players; cannot test player model")
    return now

def _weighted_pick(rng,weights):
    total=sum(weight for _,weight in weights)
    if not total>0 or any(not _finite(w) or w<0 for _,w in weights):
        raise ValueError("Invalid opportunity distribution")
    pick=rng.random()*total
    for name,weight in weights:
        pick-=weight
        if pick<0:return name
    return weights[-1][0]

def _weights(team,key,other):
    items=[(str(p["player_id"]),p[key]) for p in team["players"]
           if p.get(key) is not None and p[key]>0]
    known=sum(w for _,w in items)
    if not 0<=known<1:return []
    items.append((other,max(0.,1-known)))
    return items

def _allocate_yards(rng,total,events,efficiency):
    # Work at completed-event granularity: a completed pass has exactly
    # one passer and one receiver. Yardage is attributed to both.
    if not events:
        if total!=0:raise ValueError("Nonzero yard total without an attributed event")
        return []
    if total==0:return [0 for _ in events]
    weights=[efficiency(i) for i in events]
    if any(not _finite(w) or w<=0 for w in weights):
        raise ValueError("Invalid source-weighted per-event efficiency")
    yards=[0]*len(events)
    for _ in range(abs(total)):
        j=_weighted_pick(rng,list(enumerate(weights)))
        yards[j]+=1 if total>0 else -1
    return yards

def _scaled(rng,n,scale):
    if not _finite(scale) or scale<=0:raise ValueError("Impossible possession pace")
    value=n*scale
    whole=int(math.floor(value))
    return whole+int(rng.random()<value-whole)

def _one_team(rng,team,possession_count):
    # Draw observed prior team-game totals as one correlated source vector.
    rows=sorted(team["prior_games"],key=lambda g:g["kickoff_utc"],reverse=True)[:8]
    prior=_sample(rng,[{"row":r,"weight":.82**i} for i,r in enumerate(rows)],"weight")["row"]
    scale=possession_count/prior["possessions"]
    attempts=_scaled(rng,prior["pass_attempts"],scale)
    rush_attempts=_scaled(rng,prior["rush_attempts"],scale)
    completions=_scaled(rng,prior["pass_completions"]*attempts/max(1,prior["pass_attempts"]),1)
    completions=min(completions,attempts)
    pass_yards=_scaled(rng,prior["pass_yards"]*completions/
                       max(1,prior["pass_completions"]),1) if completions else 0
    rush_yards=_scaled(rng,abs(prior["rush_yards"]),scale)*(1 if prior["rush_yards"]>=0 else -1)
    passers=_weights(team,"pass_attempt_share","OTHER_QB")
    receivers=_weights(team,"target_share","OTHER_RECEIVER")
    rushers=_weights(team,"carry_share","OTHER_RUSHER")
    if any(not x for x in (passers,receivers,rushers)):
        raise ValueError("Incomplete unknown player opportunity bucket")
    stats=defaultdict(lambda:defaultdict(int))
    attempts_ledger=[]
    for _ in range(attempts):
        passer=_weighted_pick(rng,passers)
        receiver=_weighted_pick(rng,receivers)
        stats[passer]["passing_attempts"]+=1
        stats[receiver]["targets"]+=1
        attempts_ledger.append((passer,receiver))
    completing=set(rng.sample(range(attempts),completions))
    catch_events=[attempts_ledger[i] for i in range(attempts) if i in completing]
    player_roles={str(p["player_id"]):p for p in team["players"]}
    for passer,receiver in catch_events:
        stats[passer]["passing_completions"]+=1
        stats[receiver]["receptions"]+=1
    mean_receive=(prior["pass_yards"]/prior["pass_completions"]
                  if prior["pass_completions"] else 1.)
    def receiver_ypr(event):
        player=player_roles.get(event[1])
        return player["receiving_yards_per_catch"] if player is not None else max(1,mean_receive)
    for (passer,receiver),value in zip(catch_events,_allocate_yards(
            rng,pass_yards,catch_events,receiver_ypr)):
        stats[passer]["passing_yards"]+=value
        stats[receiver]["receiving_yards"]+=value
    carries=[_weighted_pick(rng,rushers) for _ in range(rush_attempts)]
    for player in carries:stats[player]["rushing_attempts"]+=1
    mean_rush=max(1,abs(prior["rush_yards"])/max(1,prior["rush_attempts"]))
    def rusher_ypc(player):
        p=player_roles.get(player)
        return p["rushing_yards_per_carry"] if p is not None else mean_rush
    for player,yards in zip(carries,_allocate_yards(rng,rush_yards,carries,rusher_ypc)):
        stats[player]["rushing_yards"]+=yards
    totals={
        "pass_attempts":attempts,"pass_completions":completions,
        "pass_yards":pass_yards,"rush_attempts":rush_attempts,
        "rush_yards":rush_yards,"possessions":possession_count}
    def sum_category(names,key):
        return sum(stats[n].get(key,0) for n in names)
    qb_names={i for i,_ in passers}
    rec_names={i for i,_ in receivers}
    rush_names={i for i,_ in rushers}
    reconciled=(
        sum_category(qb_names,"passing_attempts")==attempts and
        sum_category(qb_names,"passing_completions")==completions and
        sum_category(qb_names,"passing_yards")==pass_yards and
        sum_category(rec_names,"targets")==attempts and
        sum_category(rec_names,"receptions")==completions and
        sum_category(rec_names,"receiving_yards")==pass_yards and
        sum_category(rush_names,"rushing_attempts")==rush_attempts and
        sum_category(rush_names,"rushing_yards")==rush_yards and
        all(stats[k].get("passing_completions",0)<=stats[k].get("passing_attempts",0)
            for k in qb_names) and
        all(stats[k].get("receptions",0)<=stats[k].get("targets",0)
            for k in rec_names)
    )
    if not reconciled:
        raise ValueError("Player stat budgets failed exact conservation")
    return totals,{k:dict(v) for k,v in stats.items()}

def simulate(gamefit,profile,decision_utc,trials=400,seed=2026):
    now=_validate(profile,gamefit,decision_utc)
    if type(trials) is not int or not 50<=trials<=20000 or type(seed) is not int:
        raise ValueError("Invalid Monte Carlo research trials")
    rng=random.Random(seed)
    history=defaultdict(lambda:defaultdict(list))
    budgets=defaultdict(lambda:defaultdict(list))
    conserved=0
    for _ in range(trials):
        selected=_sample(rng,gamefit["distributions"]["possessions"],"weight")
        counts={s:selected.get(s+"_count",selected.get("count"))
                for s in ("home","away")}
        for side in ("home","away"):
            totals,players=_one_team(rng,profile["teams"][side],counts[side])
            conserved+=1
            for stat,value in totals.items():budgets[side][stat].append(value)
            # Include explicit zeros for known players/categories in simulated
            # lineup, not unlisted source players. These are within a synthetic
            # conditional scenario, not retrospectively invented game stats.
            roster={str(p["player_id"]) for p in profile["teams"][side]["players"]}|OTHER
            stats={"passing_attempts","passing_completions","passing_yards",
                   "targets","receptions","receiving_yards",
                   "rushing_attempts","rushing_yards"}
            for player in sorted(roster):
                if player in OTHER or any(str(p["player_id"])==player for p in profile["teams"][side]["players"]):
                    for stat in stats:
                        history[(side,player)][stat].append(players.get(player,{}).get(stat,0))
    def aggregate(xs):
        return {"mean":round(sum(xs)/len(xs),4),
                "p10":sorted(xs)[int((len(xs)-1)*.1)],
                "median":sorted(xs)[int((len(xs)-1)*.5)],
                "p90":sorted(xs)[int((len(xs)-1)*.9)]}
    result=[]
    for side in ("home","away"):
        team=profile["teams"][side]
        records=[{"player_id":pid,"is_unmodeled_bucket":pid in OTHER,
                  "metrics":{k:aggregate(values) for k,values in stat_map.items()}}
                 for (s,pid),stat_map in sorted(history.items()) if s==side]
        result.append({"side":side,"team":team["team"],
                       "source_games":len(team["prior_games"]),
                       "source_lineup_complete":False,
                       "mean_team_budgets":{k:aggregate(xs)
                                            for k,xs in budgets[side].items()},
                       "player_opportunity_scenarios":records})
    return {"status":STATUS,"game_id":str(gamefit["game_id"]),
            "decision_utc":now.isoformat(),"trials":trials,"seed":seed,
            "team_scenarios":result,
            "team_stat_conservation":True,
            "reconciled_team_trials":conserved,
            "unknown_players_preserved":True,
            "player_active_scenario_conditional":True,
            "touchdown_allocation_supported":False,
            "historical_source_publication_authenticated":False,
            "prop_model_probabilities_calibrated":False,
            "model_promoted":False,"safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED"}

def run(fit_path,profile_path,decision_utc,output_path,trials=400):
    fit=json.loads(Path(fit_path).read_text(encoding="utf-8"))
    profile=json.loads(Path(profile_path).read_text(encoding="utf-8"))
    r=simulate(fit,profile,decision_utc,trials=trials)
    path=Path(output_path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(r,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return r

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--fit",required=True);p.add_argument("--profile",required=True)
    p.add_argument("--decision",required=True);p.add_argument("--output",required=True)
    p.add_argument("--trials",type=int,default=400)
    a=p.parse_args();run(a.fit,a.profile,a.decision,a.output,a.trials)

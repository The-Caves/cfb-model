"""Research-only possession-conditioned, correlated player-stat scenarios.

Each simulated game shares a *single* sampled two-team possession count and
offensive drive scoring scenario. Each player's same-game historical stat vector
is resampled jointly and scaled by shared team-pace. This preserves within-
player rec/yard/TD relationships approximately, but does NOT impose a team-level
target/carry budget; it is NOT a calibrated conservation-level play simulator.
No missing player category is zero-filled. Unconfirmed participants are
conditional scenarios; no validated prop line edge is inferred.
"""
import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from scripts.game_context import parse_time
from scripts.player_prop_history import STATUS as PLAYER_HISTORY, STATS, COUNT_STATS
from scripts.game_simulation_research import validate_inputs, _sample

STATUS="POSSESSION_CONDITIONED_PROP_SIM_RESEARCH_ONLY"
POS_SOURCE="OBSERVED_PRIOR_TEAM_POSSESSIONS_RESEARCH_ONLY"
QUOTE_STATUS="OBSERVED_TWO_SIDED_PREDECISION_PROP"

def _url(value):
    try:
        p=urlsplit(value)
        return p.scheme=="https" and bool(p.hostname)
    except (TypeError,ValueError):return False

def _stat(x,name):
    if name in COUNT_STATS:return max(0,int(round(x)))
    return int(round(x))  # A QB/RB can finish a game with negative rushing yards.

def _quantile(xs,p):
    s=sorted(xs)
    return s[int((len(s)-1)*p)]

def _source_rows(player_history,possessions,target,when):
    if (player_history.get("status")!=PLAYER_HISTORY or
        player_history.get("betting_status")!="PASS_UNVALIDATED" or
        player_history.get("retrospective_first_publication_authenticated") is not False):
        raise ValueError("Untrusted player-game history source")
    if (possessions.get("status")!=POS_SOURCE or
        parse_time(possessions["observed_at_utc"])>when):
        raise ValueError("Future or unverified historical drives")
    known={}
    for r in possessions.get("rows",[]):
        key=(str(r["game_id"]),str(r["team_id"]))
        if key in known:raise ValueError("Duplicate historical team/drive identity")
        if (type(r.get("team_possessions")) is not int or
            not 1<=r["team_possessions"]<=24 or
            parse_time(r["observed_at_utc"])>when or not _url(r.get("source_url"))):
            raise ValueError("Unverified historical team possessions")
        known[key]=r["team_possessions"]
    candidates=defaultdict(list)
    for r in player_history["rows"]:
        if parse_time(r["observed_at_utc"])>when:continue
        if (str(r["date"])>=str(target["date"]) or
            parse_time(r["kickoff_utc"])>=parse_time(target["kickoff_utc"])):
            continue
        key=(str(r["game_id"]),str(r["team_id"]))
        if key not in known:continue
        if r.get("source_status")!="RETROSPECTIVE_REVISED_PLAYER_BOX_ONLY":
            raise ValueError("Unsupported player source provenance")
        candidates[(str(r["player_id"]),str(r["team_id"]))].append((
            r["kickoff_utc"],r["values"],known[key]))
    for v in candidates.values():v.sort(key=lambda x:x[0],reverse=True)
    return candidates

def simulate(gamefit,player_history,prior_possessions,target,decision_utc,quotes=None,
             trials=1500,seed=2026):
    validate_inputs(gamefit,decision_utc)
    now=parse_time(decision_utc)
    if target["kickoff_utc"]!=gamefit["kickoff_utc"] or (
        str(target["game_id"])!=str(gamefit["game_id"]) or
        target["home"]!=gamefit["home"] or target["away"]!=gamefit["away"] or
        not target.get("date")):
        raise ValueError("Game and source fit identity mismatch")
    if type(trials) is not int or not 100<=trials<=25000 or type(seed) is not int:
        raise ValueError("Invalid stochastic research settings")
    if quotes is not None and (quotes.get("status")!="NCAAF_PLAYER_PROP_SOURCE_CAPTURE_RESEARCH_ONLY" or
        str(quotes.get("espn_game_id"))!=str(target["game_id"])):
        raise ValueError("Prop bookmaker and ESPN fixture mismatch")
    candidates=_source_rows(player_history,prior_possessions,target,now)
    eligible=[];insufficient=[];names=set()
    for item in target.get("players",[]):
        pid=str(item["player_id"]);team=str(item["team_id"])
        if (pid,team) in names:raise ValueError("Duplicate target athlete")
        names.add((pid,team))
        if item["team"] not in (target["home"],target["away"]):
            raise ValueError("Unknown home/away side")
        if (item.get("availability") not in ("CONFIRMED_ACTIVE","UNCONFIRMED_EXPECTED")
            or parse_time(item["availability_observed_at_utc"])>now):
            insufficient.append({"player_id":pid,"reason":"AVAILABILITY_UNKNOWN_OR_OUT"})
            continue
        past=candidates.get((pid,team),[])[:8]
        stat_coverage={field:sum(record[1].get(field) is not None for record in past)
                       for field in STATS}
        if len(past)<3 or not any(x>=3 for x in stat_coverage.values()):
            insufficient.append({"player_id":pid,"reason":"INSUFFICIENT_PRIOR_RECORDED_GAME_STAT_COVERAGE"})
            continue
        eligible.append((item,past,stat_coverage))
    if not eligible:
        return {"status":"PASS_INSUFFICIENT_PLAYER_PREGAME_EVIDENCE",
                "game_id":str(target["game_id"]),"player_scenarios":[],
                "excluded":insufficient,"model_promoted":False,
                "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    rng=random.Random(seed)
    dist=gamefit["distributions"]
    output=defaultdict(lambda:defaultdict(list))
    home_scores=[];away_scores=[];common_counts=[]
    for trial in range(trials):
        draw=_sample(rng,dist["possessions"],"weight")
        counts={side:draw.get(side+"_count",draw.get("count")) for side in ("home","away")}
        scores={}
        for side in ("home","away"):
            score=0
            for _ in range(counts[side]):
                source=(dist.get("field_position_by_side") or {}).get(side,dist["field_position"])
                zone=_sample(rng,source,"zone")["zone"]
                result=_sample(rng,dist["outcomes"][side][zone],"points")
                score+=result["points"]
            scores[side]=score
        home_scores.append(scores["home"]);away_scores.append(scores["away"])
        common_counts.append(counts)
        for item,past,coverage in eligible:
            key=str(item["player_id"])
            # Draw the *same prior game* vector for all stats of this player.
            # Missing category is excluded; not converted to a zero.
            recent=past[:6]
            vector=_sample(rng,[{"row":x,"weight":.78**i} for i,x in enumerate(recent)],"weight")["row"]
            _,values,old_count=vector
            side="home" if item["team"]==target["home"] else "away"
            pace=counts[side]/old_count
            for stat in STATS:
                if coverage[stat]<3 or values.get(stat) is None:continue
                output[key][stat].append(_stat(values[stat]*pace,stat))
    quote_idx=defaultdict(list)
    if quotes is not None:
        for q in quotes.get("quotes",[]):
            if (q.get("status")!=QUOTE_STATUS or str(q["espn_game_id"])!=str(target["game_id"])
                or parse_time(q["observed_at_utc"])>now
                or parse_time(q["kickoff_utc"])!=parse_time(target["kickoff_utc"])
                or q.get("betting_status")!="PASS_UNVALIDATED"):
                raise ValueError("Untrusted or postdecision player prop quote")
            quote_idx[(str(q["player_id"]),q["metric"])].append(q)
    report=[]
    for item,past,coverage in eligible:
        athlete=str(item["player_id"])
        metrics={}
        for stat,draws in output[athlete].items():
            n=len(draws)
            if n<100:continue
            markets=[]
            for q in quote_idx.get((athlete,stat),[]):
                line=q["line"]
                markets.append({"bookmaker":q["bookmaker"],"line":line,
                    "over_probability_conditional":round(sum(x>line for x in draws)/n,6),
                    "under_probability_conditional":round(sum(x<line for x in draws)/n,6),
                    "push_probability_conditional":round(sum(x==line for x in draws)/n,6),
                    "bookmaker_over_no_vig":q["implied_over_no_vig"],
                    "potential_edge_unvalidated":True})
            metrics[stat]={"samples":n,"mean":round(sum(draws)/n,4),
                           "p10":_quantile(draws,.1),"median":_quantile(draws,.5),
                           "p90":_quantile(draws,.9),
                           "quoted_markets":markets,
                           "probabilities_validated_prospectively":False}
        report.append({"player_id":athlete,"team":item["team"],
            "team_id":str(item["team_id"]),
            "availability":item["availability"],
            "probabilities_conditional_on_playing":True,
            "recorded_games_for_prior":len(past),"metrics":metrics})
    return {"status":STATUS,"game_id":str(target["game_id"]),
            "kickoff_utc":target["kickoff_utc"],
            "decision_utc":now.isoformat(),"simulation_trials":trials,"seed":seed,
            "teams":{"home":target["home"],"away":target["away"]},
            "mean_simulated_home_score":round(sum(home_scores)/trials,3),
            "mean_simulated_away_score":round(sum(away_scores)/trials,3),
            "mean_home_possessions":round(sum(x["home"] for x in common_counts)/trials,3),
            "mean_away_possessions":round(sum(x["away"] for x in common_counts)/trials,3),
            "player_scenarios":report,"excluded":insufficient,
            "script_conditioning_fitted":False,
            "team_level_stat_conservation_fitted":False,
            "historical_first_publication_verified":False,
            "prop_market_edge_validated":False,
            "model_promoted":False,"safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED"}

def run(fit_path,history_path,pos_path,game_path,decision,output,quote_path=None,trials=1500):
    read=lambda x:json.loads(Path(x).read_text(encoding="utf-8"))
    r=simulate(read(fit_path),read(history_path),read(pos_path),
               read(game_path),decision,read(quote_path) if quote_path else None,
               trials=trials)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(r,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return r

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("fit","history","possessions","game","decision","output"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--quotes");p.add_argument("--trials",type=int,default=1500)
    a=p.parse_args()
    run(a.fit,a.history,a.possessions,a.game,a.decision,a.output,a.quotes,a.trials)

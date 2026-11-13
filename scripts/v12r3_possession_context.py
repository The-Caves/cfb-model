"""V12R3 matched-opponent tempo, observed drive transition and RZ conversion research.

Three PREDECLARED low-complexity ablations on unchanged V11/V04 scored hazards.
Every fitted datum comes from the immutable source-reconciled possession ledger
strictly prior to the ORIGINAL frozen V04 weekly cutoff (never same-week games).
Red-zone conversion uses actual red-zone trips/TDs, NOT play success; it only
softly adjusts drives that begin on the opponent side of midfield. No actual
historical QB/injury/weather is inferred or introduced.

NOT verified for upstream source first-publication timing. RESEARCH ONLY.
"""
import datetime as dt
import math
from collections import defaultdict

from scripts.v10_possession_sim import clamp

STATUS="V12R3_PRIOR_WEEK_MATCHUP_POSSESSIONS_RESEARCH_ONLY"
HALF_LIFE=28
SHRINK_GAMES=4.
SHRINK_TRIPS=16.
TEAM_TRANSITION_WEIGHT_CAP=.35
RZ_EFFECT=.18
TRANSITIONS=("TD","FG","TURNOVER","EMPTY","RETURN_TD","OPENING")


def _avg(samples,prior,pseudo_n):
    total=sum(w for val,w in samples)
    return (sum(val*w for val,w in samples)+prior*pseudo_n)/(total+pseudo_n)


def _rate(num,den,prior,n):
    return (num+prior*n)/(den+n)


def _event(d):
    if d["turnover"] and d["defense_points"]>=6:return "RETURN_TD"
    if d["turnover"]:return "TURNOVER"
    if d["offense_points"]>=6:return "TD"
    if d["offense_points"]==3:return "FG"
    return "EMPTY"


def fit_context(source,fitted,cutoff):
    """Build once per original weekly cutoff, independent of target matchup."""
    if (not fitted.get("ready") or fitted.get("target_date")!=cutoff or
        not isinstance(source,list) or len(source)<35):
        raise ValueError("Invalid earlier-week possession fitting context")
    cut=dt.date.fromisoformat(cutoff)
    seen=set();games=[]
    for g in source:
        if g["date"]>=cutoff:continue
        gid=str(g["game_id"])
        if gid in seen:raise ValueError("Duplicate earlier historical game")
        seen.add(gid)
        if dt.date.fromisoformat(g["date"])>=cut:raise ValueError("Future game leakage")
        games.append(g)
    if len(games)!=fitted["source_prior_games"] or sum(len(g["drives"]) for g in games)!=fitted["prior_drives"]:
        raise ValueError("Transition evidence differs from matched V11 frozen cohort")
    league_pace=[];tempo_by_team=defaultdict(list)
    transitions={kind:{"league":[],"receiver":defaultdict(list),
                       "offense":defaultdict(list)} for kind in TRANSITIONS}
    league_rz=[];offense_rz=defaultdict(list);defense_rz=defaultdict(list)
    for g in games:
        date=dt.date.fromisoformat(g["date"])
        weight=math.exp2(-((cut-date).days)/HALF_LIFE)
        d=g["drives"]
        byside={"home":sum(x["side"]=="home" for x in d),
                "away":sum(x["side"]=="away" for x in d)}
        n=(byside["home"]+byside["away"])/2
        league_pace.append(n)
        for side,team in (("home",g["home"]),("away",g["away"])):
            # Offense's own possessions and its defense's opposing possessions
            # are genuinely separately observed within each earlier game.
            tempo_by_team[team].append(
                {"game_id":str(g["game_id"]),"day":g["date"],"weight":weight,
                 "own":byside[side],
                 "faced":byside["away" if side=="home" else "home"]})
        for x in d:
            if x["red_zone_visited"]:
                opp=g["away" if x["side"]=="home" else "home"]
                event=_event(x)
                record=(event=="TD",event=="FG")
                league_rz.append(record)
                offense_rz[x["team"]].append(record)
                defense_rz[opp].append(record)
        if d:
            first=d[0]
            yard=first["start_yards_to_goal"]
            if not isinstance(yard,int) or not 0<=yard<=100:
                raise ValueError("Unreconciled first-possession field position")
            transitions["OPENING"]["league"].append(yard)
            transitions["OPENING"]["receiver"][first["team"]].append(yard)
        for x,y in zip(d,d[1:]):
            if (x["team"] not in (g["home"],g["away"]) or
                y["team"] not in (g["home"],g["away"]) or
                not isinstance(y["start_yards_to_goal"],int) or
                not 0<=y["start_yards_to_goal"]<=100):
                raise ValueError("Invalid actual consecutive-drive field position")
            kind=_event(x)
            # A return TD ends with a kickoff to the original offense.
            if kind=="RETURN_TD":
                if y["team"]!=x["team"]:continue
            elif y["team"]==x["team"]:
                # Do not falsely call two possessions by the same team
                # an ordinary exchange or inferred turnover.
                continue
            record=transitions[kind]
            record["league"].append(y["start_yards_to_goal"])
            record["receiver"][y["team"]].append(y["start_yards_to_goal"])
            record["offense"][x["team"]].append(y["start_yards_to_goal"])
    if not league_rz or len(league_pace)<35:
        raise ValueError("No authenticated historical RZ drives/pace")
    mean=sum(league_pace)/len(league_pace)
    prior_td=sum(t for t,f in league_rz)/len(league_rz)
    n_non_td=sum(1 for t,f in league_rz if not t)
    prior_fg=sum(f for t,f in league_rz)/n_non_td if n_non_td else .20
    return {
        "status":STATUS,"ready":True,"cutoff":cutoff,
        "source_prior_game_ids":sorted(seen),"source_games":len(games),
        "league_pace":mean,
        "pace_deviations":[x-mean for x in league_pace],
        "tempo_by_team":dict(tempo_by_team),
        "transition":{
            k:{"league":v["league"],"receiver":dict(v["receiver"]),
               "offense":dict(v["offense"])}
            for k,v in transitions.items()},
        "rz":{"league":{"td":prior_td,"fg_given_non_td":prior_fg,
                        "trips":len(league_rz)},
              "offense":dict(offense_rz),
              "defense":dict(defense_rz)},
        "first_publication_verified":False,
        "source_cutoff_is_football_week":True,
        "model_promoted":False}


def matchup_pace(ctx,home,away):
    """Recency-weighted home-offense/away-defense and reverse tempo.

    Shrinks all four role observations to earlier source league mean.
    Fixed shrinkage, no learned coefficients on the target games.
    """
    if ctx.get("status")!=STATUS or not ctx["ready"]:
        raise ValueError("Unverified opponent pace")
    mean=ctx["league_pace"]
    def expected(team,role):
        data=ctx["tempo_by_team"].get(team,[])
        return _avg([(g[role],g["weight"]) for g in data],mean,SHRINK_GAMES)
    home_off=expected(home,"own")
    home_allowed=expected(home,"faced")
    away_off=expected(away,"own")
    away_allowed=expected(away,"faced")
    # Both squads' possessions are paired per game, so average their
    # opponent-conditioned offensive opportunity estimates.
    current=(.5*(home_off+away_allowed)+.5*(away_off+home_allowed))/2
    return {"source_cutoff":ctx["cutoff"],
            "distribution_source":"EARLIER_REAL_GAME_POSSESSION_COUNTS",
            "expected_possessions_each":clamp(current,7.,18.),
            "historical_deviations":ctx["pace_deviations"],
            "team_role_estimates":{
                "home_offense":round(home_off,4),"home_opponent_offense":round(home_allowed,4),
                "away_offense":round(away_off,4),"away_opponent_offense":round(away_allowed,4)},
            "source_games":ctx["source_games"],
            "source_first_publication_verified":False}


def next_field(ctx,kind,offense,receiver,rng):
    """Draw a *real* recorded opening/next possession start, league-shrunk.

    Receiver-specific returns and offense-specific short fields receive a
    bounded weight. Uses only bona fide observed consecutive-drive positions.
    """
    if ctx.get("status")!=STATUS or kind not in TRANSITIONS:
        raise ValueError("Unverified drive transition type")
    group=ctx["transition"][kind]
    pooled=group["league"]
    if not pooled:
        return None # caller must fall back to *source-observed* V11 starts
    own=group["receiver"].get(receiver,[])
    other=group["offense"].get(offense,[])
    # Subtle matchup effect: stronger for prior turnovers; fewer unverified
    # special-teams conclusions from sparse kickoff data.
    recv_weight=min(TEAM_TRANSITION_WEIGHT_CAP,len(own)/(len(own)+30))
    off_weight=min(.20,len(other)/(len(other)+40)) if kind=="TURNOVER" else 0.
    choice=rng.random()
    if own and choice<recv_weight:
        y=rng.choice(own)
    elif other and choice<recv_weight+off_weight:
        y=rng.choice(other)
    else:
        y=rng.choice(pooled)
    if not isinstance(y,int) or not 0<=y<=100:
        raise ValueError("Non-source field position")
    return y


def redzone_distribution(ctx,side,offense,opponent,zone,original):
    """Source RZ TD/FG rates softly update V11 scoring odds, not turnovers.

    Crucially: conditional RZ conversions are NOT applied as a whole-drive
    TD probability; they act only as a small relative log-odds adjustment in
    late-field zones. Never infer RZ trip probability on own-half drives.
    """
    if (ctx.get("status")!=STATUS or
        zone not in ("red_zone","opponent_half","midfield","own_half","own_deep")):
        raise ValueError("Invalid red-zone context")
    result=dict(original)
    if zone not in ("red_zone","opponent_half"):return result
    rz=ctx["rz"];base=rz["league"]
    att=rz["offense"].get(offense,[])
    allowed=rz["defense"].get(opponent,[])
    if len(att)<2 or len(allowed)<2:return result
    league_td=base["td"]
    pa=_rate(sum(t for t,f in att),len(att),league_td,SHRINK_TRIPS)
    pd=_rate(sum(t for t,f in allowed),len(allowed),league_td,SHRINK_TRIPS)
    opponent_td=(pa+pd)/2
    non_a=[f for t,f in att if not t]
    non_d=[f for t,f in allowed if not t]
    pf=_rate(sum(non_a),len(non_a),base["fg_given_non_td"],SHRINK_TRIPS)
    qf=_rate(sum(non_d),len(non_d),base["fg_given_non_td"],SHRINK_TRIPS)
    opponent_fg=(pf+qf)/2
    reliability=min(1.,len(att)/(len(att)+SHRINK_TRIPS),
                    len(allowed)/(len(allowed)+SHRINK_TRIPS))
    influence=RZ_EFFECT*reliability*(1. if zone=="red_zone" else .35)
    # Multiplicative scoring factors have bounded range and are
    # normalized exclusively within the non-turnover outcome mass.
    td_mult=math.exp(clamp(influence*math.log((opponent_td+.05)/(league_td+.05)),
                           -.12,.12))
    fg_mult=math.exp(clamp(influence*math.log((opponent_fg+.05)/(base["fg_given_non_td"]+.05)),
                           -.12,.12))
    turnover=original["TURNOVER"]
    result["TD"]*=td_mult
    result["FG"]*=fg_mult
    mass=sum(result[k] for k in ("TD","FG","EMPTY"))
    if mass<=0:raise ValueError("No non-turnover outcome mass")
    for k in ("TD","FG","EMPTY"):result[k]*=(1-turnover)/mass
    result["TURNOVER"]=turnover
    if abs(sum(result.values())-1.)>1e-8:
        raise ValueError("Red-zone adjusted probabilities not normalized")
    return result

"""V10 genuine possession-by-possession Monte Carlo from verified ESPN drive ledgers.

Each simulated drive has a source-derived starting field position, conditional
offensive TD/FG/empty/turnover outcome, distinct defensive return TD probability,
and opponent-specific pressure/EPA/red-zone adjustments. Training only uses
EARLIER FOOTBALL DATES; historical raw source publication time remains unknown.
Do not treat as a validated or actively promoted betting model.
"""
import csv
import hashlib
import math
import random
from collections import Counter,defaultdict
from scripts.possession_drive_ingest import STATUS as DRIVE_STATUS

STATUS="V10_OBSERVED_POSSESSION_MATCHUP_SIM_RESEARCH_ONLY"
OUTCOMES=("TD","FG","EMPTY","TURNOVER")
def clamp(x,low,high):return max(low,min(high,x))
def rate(num,den,prior,prior_n):
    return (num+prior*prior_n)/(den+prior_n)
def number(x):
    try:return float(x) if x is not None and x!="" and math.isfinite(float(x)) else None
    except (ValueError,TypeError,OverflowError):return None

def advanced_index(csv_file):
    rows=list(csv.DictReader(open(csv_file,encoding="utf-8-sig",newline="")))
    index={}
    for r in rows:
        k=(str(r.get("game_id")),r.get("team"))
        if not all(k) or k in index:raise ValueError("Unmapped or duplicate 2026 EPA game/team")
        index[k]=r
    return index

def _drive_outcome(d):
    if d["turnover"]:return "TURNOVER"
    if d["offense_points"]>=6:return "TD"
    if d["offense_points"]==3:return "FG"
    return "EMPTY"

def _pct(rows,predicate):
    return sum(bool(predicate(x)) for x in rows)

def _team_drives(past,team,offense=True):
    return [d for g in past for d in g["drives"]
            if (d["team"]==team if offense else d["team"]!=team and team in (g["home"],g["away"]))]

def _context(games,team,advanced,offense):
    """Historical EPA, play style, red-zone play success, and QB pressure.
    Def context reads opponent's offense against this team's defense, not
    this team's own offensive stat lines.
    """
    sums=defaultdict(float);totals=defaultdict(float)
    for g in games:
        if team not in (g["home"],g["away"]):continue
        target=team if offense else (g["away"] if team==g["home"] else g["home"])
        row=advanced.get((g["game_id"],target))
        if not row:continue
        for key,den in (
            ("off_epa_sum","epa_plays"),
            ("pass_epa_sum","pass_epa_plays"),
            ("rush_epa_sum","rush_epa_plays"),
            ("pressure_count","pressure_observed"),
            ("redzone_success","redzone_plays"),
            ("pass_plays","scrimmage_plays"),
        ):
            n=number(row.get(key));d=number(row.get(den))
            if n is not None and d is not None and d>0 and abs(n)<1e6 and d<2000:
                sums[key]+=n;totals[key]+=d
    result={}
    for key,den in (
        ("off_epa_sum","epa_plays"),("pass_epa_sum","pass_epa_plays"),
        ("rush_epa_sum","rush_epa_plays"),("pressure_count","pressure_observed"),
        ("redzone_success","redzone_plays"),("pass_plays","scrimmage_plays")):
        result[key]=sums[key]/totals[key] if totals[key]>0 else None
        result[key+"_plays"]=int(totals[key])
    return result

def fit(source_games,advanced,target,min_games=35,min_team_games=1):
    """Fit game only from prior *completed football dates* and verified real drives.

    This is a retrospective evaluation until source publication-time snapshots
    are independently certified. It cannot be called with future drives.
    """
    if not isinstance(source_games,list):raise ValueError("No 2026 possession ledger")
    day=target["date"]
    if len({g["game_id"] for g in source_games})!=len(source_games):
        raise ValueError("Duplicate historical game")
    past=[g for g in source_games if g["date"]<day]
    if len(past)<min_games:
        return {"ready":False,"reason":"INSUFFICIENT_PRIOR_VERIFIED_DRIVE_GAMES",
                "past_games":len(past)}
    home,away=target["home"],target["away"]
    if not home or not away or home==away:raise ValueError("Invalid matchup")
    exposure={s:sum(s in (g["home"],g["away"]) for g in past) for s in (home,away)}
    if min(exposure.values())<min_team_games:
        return {"ready":False,"reason":"MISSING_MATCHED_TEAM_DRIVE_HISTORY",
                "past_games":len(past),"team_games":exposure}
    prior_drives=[d for g in past for d in g["drives"]]
    if len(prior_drives)<200:raise ValueError("Unreliable or empty source drive coverage")
    league=Counter(_drive_outcome(d) for d in prior_drives)
    league_probs={kind:rate(league[kind],len(prior_drives),.25,8) for kind in OUTCOMES}
    # League baseline P(type | starting yard zone) comes from verified drives.
    zones=defaultdict(list)
    for d in prior_drives:zones[d["field_zone"]].append(d)
    league_result={}
    for zone in ("own_deep","own_half","midfield","opponent_half","red_zone"):
        ds=zones.get(zone,[])
        league_result[zone]={k:rate(_pct(ds,lambda d:_drive_outcome(d)==k),len(ds),
                                   league_probs[k],45) for k in OUTCOMES}
    # Analyze field-position impact from actual next drives following turnover
    # vs punts/missed kicks. Missing sequence history remains generic.
    starts=defaultdict(list)
    for g in past:
        for a,b in zip(g["drives"],g["drives"][1:]):
            if b["team"]==a["team"]:continue
            kind="TURNOVER" if a["turnover"] and a["defense_points"]==0 else (
                "SCORE" if a["offense_points"] or a["defense_points"] else "NORMAL")
            starts[kind].append(b["start_yards_to_goal"])
    for k in ("TURNOVER","SCORE","NORMAL"):
        if not starts[k]:starts[k]=[75]
    profiles={};keys={}
    for side,team,opponent in (("home",home,away),("away",away,home)):
        att=_team_drives(past,team)
        defn=_team_drives(past,opponent,False)
        offense_ctx=_context(past,team,advanced,True)
        defense_ctx=_context(past,opponent,advanced,False)
        byzone={}
        for zone in league_result:
            aa=[d for d in att if d["field_zone"]==zone]
            dd=[d for d in defn if d["field_zone"]==zone]
            byzone[zone]={}
            for k in OUTCOMES:
                lp=league_result[zone][k]
                # Give offensive opportunities slightly more weight than
                # opposing-defense allowances, both heavily league-shrunk.
                pa=rate(_pct(aa,lambda d:_drive_outcome(d)==k),len(aa),lp,14)
                pd=rate(_pct(dd,lambda d:_drive_outcome(d)==k),len(dd),lp,14)
                byzone[zone][k]=.56*pa+.44*pd
        # Takeaways from true opponent scoring drives, not boxscore plus
        # source unverified claims. Prior drives are complete/box-reconciled.
        giveaways=sum(d["turnover"] for d in att)
        opponent_takeaways=sum(d["turnover"] for d in defn)
        league_to=league_probs["TURNOVER"]
        o=rate(giveaways,len(att),league_to,20)
        d=rate(opponent_takeaways,len(defn),league_to,20)
        turnover_probability=clamp(math.sqrt(o*d),.012,.32)
        defense_return_tds=sum(d["defense_points"]>=6 for d in defn)
        defense_takeaways=max(1,opponent_takeaways)
        baseline_return=sum(d["defense_points"]>=6 for d in prior_drives)
        base_return=rate(baseline_return,league["TURNOVER"],.06,15)
        pick_six_p=clamp(rate(defense_return_tds,defense_takeaways,base_return,18),0,.28)
        team_games=[g for g in past if team in (g["home"],g["away"])]
        possessions=[sum(x["team"]==team for x in g["drives"]) for g in team_games]
        profiles[side]={
            "team":team,"opponent":opponent,"team_games":len(team_games),
            "offense_drives":len(att),"defense_exposure_drives":len(defn),
            "zone_outcomes":byzone,"turnover_probability":turnover_probability,
            "return_td_probability_conditional_turnover":pick_six_p,
            "offense_context":offense_ctx,"defense_context":defense_ctx,
            "mean_possessions":sum(possessions)/len(possessions),
            "league_turnover_probability":league_to,
        }
        keys[side]={"offense_games":len(team_games),"opponent_defense_games":exposure[opponent]}
    return {"ready":True,"status":STATUS,"source_prior_games":len(past),
        "prior_drives":len(prior_drives),"team_coverage":keys,
        "target_game_id":target["game_id"],
        "target_home":home,"target_away":away,"target_date":day,
        "source_data_first_published_by_historical_cutoff_verified":False,
        "model_promoted":False,"profiles":profiles,"next_field_positions":starts,
        "league_zone_outcomes":league_result}

def _zone(ytg):
    return "red_zone" if ytg<=20 else "opponent_half" if ytg<=50 else (
        "midfield" if ytg<=60 else "own_half" if ytg<=90 else "own_deep")

def outcome_distribution(fitted,side,ytg,matchup=True):
    x=fitted["profiles"][side]
    zone=_zone(ytg)
    base=x["zone_outcomes"][zone].copy()
    if matchup:
        attack=x["offense_context"];defense=x["defense_context"]
        # Offense EPA is complemented by opponent EPA ALLOWED in earlier
        # meetings; no use of today's postgame scouting state.
        off=attack["off_epa_sum"];allowed=defense["off_epa_sum"]
        pass_rate=attack["pass_plays"] or .5
        pass_e=attack["pass_epa_sum"];rush_e=attack["rush_epa_sum"]
        pressured=attack["pressure_count"];created=defense["pressure_count"]
        if off is not None and allowed is not None:
            matchup_delta=clamp((off+allowed)*.5,-1,1)
            offense_factor=math.exp(.24*matchup_delta)
            base["TD"]*=offense_factor
            base["FG"]*=math.exp(.1*matchup_delta)
        if pass_e is not None and rush_e is not None:
            # Avoid unbounded passing advantage just because a team
            # passes frequently against undermanned opponents.
            style=clamp(pass_rate*pass_e+(1-pass_rate)*rush_e,-1,1)
            base["TD"]*=math.exp(.10*style)
        if pressured is not None and created is not None:
            risk=clamp(pressured+created-.22,-.22,.5)
            base["TD"]*=math.exp(-.22*risk)
            base["TURNOVER"]*=math.exp(.3*risk)
        off_rz=attack["redzone_success"];def_rz=defense["redzone_success"]
        if zone in ("red_zone","opponent_half") and off_rz is not None and def_rz is not None:
            rz=clamp((off_rz+def_rz-1)*.6,-.4,.4)
            base["TD"]*=math.exp(.2*rz)
            base["FG"]*=math.exp(-.08*rz)
    # Turnover risk is modeled independently of an offense's scored TDs.
    # League/category conditional decomposition renormalizes non-turnovers.
    event_to=clamp(x["turnover_probability"]*(base["TURNOVER"]/
                       max(.01,x["league_turnover_probability"])),.015,.36)
    non=sum(base[k] for k in OUTCOMES if k!="TURNOVER")
    return {"TURNOVER":event_to,**{k:(1-event_to)*base[k]/non
                                 for k in OUTCOMES if k!="TURNOVER"}}

def one_game(fitted,matchup,rng,trace=False):
    prof=fitted["profiles"]
    # Drives per team are sampled from earlier real possession counts, not
    # fitted from final game scores. This is a regulation possession model.
    n=round((prof["home"]["mean_possessions"]+prof["away"]["mean_possessions"])/2)
    n=clamp(n+rng.choice((-2,-1,0,0,0,1,2)),7,18)
    total={"home":0,"away":0};takeaways={"home":0,"away":0}
    first="home" if rng.random()<.5 else "away"
    side=first;start=75;trace_rows=[];previous_kind="SCORE"
    for i in range(2*n):
        p=outcome_distribution(fitted,side,start,matchup)
        u=rng.random();acc=0;event="EMPTY"
        for k in OUTCOMES:
            acc+=p[k]
            if u<=acc:event=k;break
        scorer=side;points=0;returns=False
        if event=="TD":points=7
        elif event=="FG":points=3
        elif event=="TURNOVER":
            other="away" if side=="home" else "home"
            takeaways[other]+=1
            if rng.random()<prof[side]["return_td_probability_conditional_turnover"]:
                scorer=other;points=7;returns=True
        total[scorer]+=points
        other="away" if side=="home" else "home"
        transition="TURNOVER" if event=="TURNOVER" and not returns else (
            "SCORE" if event in ("TD","FG") or returns else "NORMAL")
        starts=fitted["next_field_positions"][transition]
        next_start=rng.choice(starts)
        if trace and i<28:trace_rows.append({"possession":i+1,"offense":side,
            "start_yards_to_goal":start,"event":event,"scoring_team":scorer if points else None,
            "offense_points":points if scorer==side else 0,
            "defense_points":points if scorer!=side else 0,
            "takeaway_by":other if event=="TURNOVER" else None,
            "next_start_yards_to_goal":next_start})
        start=next_start
        # A defensive return touchdown results in a kickoff back to the
        # offense that committed the turnover. Do not give the scoring
        # defense an immediate extra offensive possession.
        side=side if returns else other
    return total,takeaways,trace_rows

def simulate(fitted,matchup=True,trials=1200,seed=2026,trace=False):
    if not fitted.get("ready") or fitted.get("status")!=STATUS:
        raise ValueError("Unverified drive fit")
    if not 100<=trials<=20000 or type(seed) is not int:
        raise ValueError("Invalid Monte Carlo parameters")
    rng=random.Random(seed);hm=[];ts=[];hs=[];as_=[];to_h=[];to_a=[]
    results=[];example=[]
    for i in range(trials):
        scores,turnovers,drives=one_game(fitted,matchup,rng,trace=trace and i==0)
        h=scores["home"];a=scores["away"]
        hm.append(h-a);ts.append(h+a);hs.append(h);as_.append(a)
        to_h.append(turnovers["home"]);to_a.append(turnovers["away"])
        results.append((h-a,h+a,turnovers["home"],turnovers["away"]))
        if drives:example=drives
    hm.sort();ts.sort()
    quant=lambda arr:[round(arr[int((trials-1)*p)],2) for p in (.05,.5,.95)]
    mean=lambda arr:sum(arr)/len(arr)
    no_h=[m for m,t,th,ta in results if th==0]
    with_h=[m for m,t,th,ta in results if th>0]
    return {"status":STATUS,"model_variant":"OPPONENT_EPA_PRESSURE_RZ_TURNOVER_MATCHUP" if matchup else "OBSERVED_DRIVE_FREQUENCY",
        "trials":trials,"home_points_mean":round(mean(hs),3),
        "away_points_mean":round(mean(as_),3),
        "home_margin_mean":round(mean(hs)-mean(as_),3),
        "total_mean":round(mean(ts),3),
        "home_win_probability":round(sum(v>0 for v in hm)/trials,5),
        "regulation_tie_probability":round(sum(v==0 for v in hm)/trials,5),
        "margin_p05_p50_p95":quant(hm),"total_p05_p50_p95":quant(ts),
        "expected_home_takeaways":round(mean(to_h),3),
        "expected_away_takeaways":round(mean(to_a),3),
        "prob_home_zero_takeaways":round(len(no_h)/trials,4),
        "home_margin_when_home_zero_takeaways":round(mean(no_h),2) if no_h else None,
        "home_margin_when_home_positive_takeaways":round(mean(with_h),2) if with_h else None,
        "sample_possessions":example,"model_promoted":False,
        "historical_source_publication_unauthenticated":True,
        "safe_for_betting":False}

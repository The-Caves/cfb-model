"""V10 genuine possession-by-possession Monte Carlo from verified ESPN drive ledgers.

Each simulated drive has a source-derived starting field position, conditional
offensive TD/FG/empty/turnover outcome, distinct defensive return TD probability,
and opponent-specific pressure/EPA/red-zone adjustments. Training only uses
EARLIER FOOTBALL DATES; historical raw source publication time remains unknown.
Do not treat as a validated or actively promoted betting model.
"""
import csv
import datetime as dt
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

# Keep an explicit as-of feature inventory. Team-game rows have no genuine
# historical first-publication timestamps in this 2026 research source.
FEATURE_RATIOS=(
    ("off_epa_sum","epa_plays"),
    ("def_epa_sum","def_epa_plays"),
    ("pass_epa_sum","pass_epa_plays"),
    ("rush_epa_sum","rush_epa_plays"),
    ("pressure_count","pressure_observed"),
    ("sack_count","sack_observed"),
    ("redzone_success","redzone_plays"),
    ("pass_plays","scrimmage_plays"),
    ("pass_success_count","pass_success_plays"),
    ("rush_success_count","rush_success_plays"),
    ("third_success","third_plays"),
    ("fourth_success","fourth_plays"),
    ("explosive_pass","pass_plays"),
    ("explosive_rush","rush_plays"),
)
RECENCY_HALF_LIFE_DAYS=28

def _context(games,team,advanced,offense,asof_day):
    """Coverage-aware, earlier-game EPA/pressure/style with 28d recency.

    Defense-facing opponent offensive statistics represent what prior
    opposing offenses actually achieved against the defense (allowed),
    not proof of a particular current defensive personnel lineup.
    """
    cutoff=dt.date.fromisoformat(asof_day)
    sums=defaultdict(float);totals=defaultdict(float)
    team_dates=set()
    for g in games:
        if team not in (g["home"],g["away"]):continue
        day=dt.date.fromisoformat(g["date"])
        if day>=cutoff:raise ValueError("Game-date lookahead in matchup features")
        target=team if offense else (g["away"] if team==g["home"] else g["home"])
        row=advanced.get((str(g["game_id"]),target))
        if row is None:continue
        if row.get("date") and row["date"]!=g["date"]:
            raise ValueError("Advanced EPA game/date identity mismatch")
        if row.get("opponent") and row["opponent"]!=(g["away"] if target==g["home"] else g["home"]):
            raise ValueError("Advanced EPA opponent identity mismatch")
        weight=math.exp2(-(cutoff-day).days/RECENCY_HALF_LIFE_DAYS)
        team_dates.add(g["date"])
        for key,den in FEATURE_RATIOS:
            n=number(row.get(key));d=number(row.get(den))
            if n is not None and d is not None and d>0 and abs(n)<1e6 and d<2000:
                if key not in ("off_epa_sum","def_epa_sum","pass_epa_sum","rush_epa_sum") and (n<0 or n>d):
                    continue
                sums[key]+=n*weight
                totals[key]+=d*weight
    result={}
    for key,den in FEATURE_RATIOS:
        result[key]=sums[key]/totals[key] if totals[key]>0 else None
        result[key+"_weighted_plays"]=round(totals[key],2)
    result["source_games"]=len(team_dates)
    result["recency_half_life_days"]=RECENCY_HALF_LIFE_DAYS
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
        offense_ctx=_context(past,team,advanced,True,day)
        defense_ctx=_context(past,opponent,advanced,False,day)
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
            "team":team,
            "historical_offensive_points_per_game":sum(d["offense_points"] for d in att)/len(team_games),
            "source_feature_coverage":{
                "offense_advanced_games":offense_ctx["source_games"],
                "opponent_defense_advanced_games":defense_ctx["source_games"],
            },"opponent":opponent,"team_games":len(team_games),
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

def outcome_distribution(fitted,side,ytg,matchup=True,regress_turnovers=False,
                         v04_prior=None,dated_profile=None):
    x=fitted["profiles"][side]
    zone=_zone(ytg)
    base=x["zone_outcomes"][zone].copy()
    if matchup:
        attack=x["offense_context"];defense=x["defense_context"]
        # Offense EPA is complemented by opponent EPA ALLOWED in earlier
        # meetings; no use of today's postgame scouting state.
        off=attack["off_epa_sum"];allowed=defense["off_epa_sum"]
        # V11 research challenger: replace raw season EPA with previously
        # reconstructed opponent-adjusted *weekly* EPA, not stack it on
        # raw EPA and count the same scoring advantage twice.
        if dated_profile is not None:
            own=dated_profile["teams"][side]
            other=dated_profile["teams"]["away" if side=="home" else "home"]
            own_form=own["weekly_recent_form"]
            other_form=other["weekly_recent_form"]
            if (own["games_before_cutoff"]>=2 and other["games_before_cutoff"]>=2
                and number(own_form.get("epa_off_adj")) is not None and
                number(other_form.get("epa_def_adj")) is not None):
                off=float(own_form["epa_off_adj"])
                allowed=float(other_form["epa_def_adj"])
        pass_rate=attack["pass_plays"] if attack["pass_plays"] is not None else .5
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
        # Additional observed opponent/style metrics. Unavailable denominators
        # preserve missingness and produce NO guessed effect.
        ps=attack["pass_success_count"];pd=defense["pass_success_count"]
        rs=attack["rush_success_count"];rd=defense["rush_success_count"]
        if ps is not None and pd is not None and rs is not None and rd is not None:
            success=clamp(pass_rate*(ps+pd-1)+(1-pass_rate)*(rs+rd-1),-.7,.7)
            base["TD"]*=math.exp(.13*success)
        ep=attack["explosive_pass"];ed=defense["explosive_pass"]
        er=attack["explosive_rush"];erd=defense["explosive_rush"]
        if all(v is not None for v in (ep,ed,er,erd)):
            explosive=clamp(pass_rate*(ep+ed-.14)+(1-pass_rate)*(er+erd-.14),-.25,.25)
            base["TD"]*=math.exp(.19*explosive)
        third=attack["third_success"];third_allowed=defense["third_success"]
        if third is not None and third_allowed is not None:
            base["TD"]*=math.exp(.06*clamp(third+third_allowed-.8,-.6,.6))
    # Keep V04's opponent-adjusted expected scoring in the possession process.
    # A fixed, capped PRIOR changes touchdown/FG likelihood on each drive;
    # this is not a post-simulation blending of invented fractional scores.
    if v04_prior is not None:
        score=v04_prior.get("home_points" if side=="home" else "away_points")
        if number(score) is None or not 0<=float(score)<=120:
            raise ValueError("Invalid earlier-week frozen V04 score prior")
        historical=x["historical_offensive_points_per_game"]
        strength=clamp(math.exp(.55*math.log((score+7)/(historical+7))),.68,1.45)
        base["TD"]*=strength
        base["FG"]*=math.sqrt(strength)
    # Turnover risk is modeled independently of an offense's scored TDs.
    # League/category conditional decomposition renormalizes non-turnovers.
    event_to=clamp(x["turnover_probability"]*(base["TURNOVER"]/
                       max(.01,x["league_turnover_probability"])),.015,.36)
    if regress_turnovers:
        # Only prior OFFENSE giveaway and OPPONENT defense takeaway exposure
        # can move a game materially away from the league turnover baseline.
        # Recent takeaway streaks with little independent evidence regress.
        exposure=min(x["offense_drives"],x["defense_exposure_drives"])
        reliability=clamp(exposure/(exposure+120),0,.70)
        event_to=clamp(x["league_turnover_probability"]+
            reliability*(event_to-x["league_turnover_probability"]),.015,.24)
    non=sum(base[k] for k in OUTCOMES if k!="TURNOVER")
    return {"TURNOVER":event_to,**{k:(1-event_to)*base[k]/non
                                 for k in OUTCOMES if k!="TURNOVER"}}

def one_game(fitted,matchup,rng,trace=False,regress_turnovers=False,v04_prior=None,
             distributions=None,pace_override=None,transition_context=None):
    prof=fitted["profiles"]
    # Drives per team are sampled from earlier real possession counts, not
    # fitted from final game scores. This is a regulation possession model.
    n=round((prof["home"]["mean_possessions"]+prof["away"]["mean_possessions"])/2)
    if pace_override is None:
        n=clamp(n+rng.choice((-2,-1,0,0,0,1,2)),7,18)
    else:
        n=clamp(round(pace_override["expected_possessions_each"]+
                      rng.choice(pace_override["historical_deviations"])),7,18)
    total={"home":0,"away":0};takeaways={"home":0,"away":0}
    first="home" if rng.random()<.5 else "away"
    side=first;start=75;trace_rows=[];previous_kind="SCORE"
    if transition_context is not None:
        from scripts.v12r3_possession_context import next_field
        observed=next_field(transition_context,"OPENING","",prof[side]["team"],rng)
        if observed is not None:start=observed
    for i in range(2*n):
        p=(distributions.get((side,_zone(start))) if distributions is not None else
           outcome_distribution(fitted,side,start,matchup,regress_turnovers,v04_prior))
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
        if transition_context is None:
            next_start=rng.choice(starts)
        else:
            from scripts.v12r3_possession_context import next_field
            event_kind="RETURN_TD" if returns else event
            receiver=side if returns else other
            actual=next_field(transition_context,event_kind,prof[side]["team"],
                              prof[receiver]["team"],rng)
            next_start=actual if actual is not None else rng.choice(starts)
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

def simulate(fitted,matchup=True,trials=1200,seed=2026,trace=False,
             regress_turnovers=False,v04_prior=None,dated_profile=None,
             return_draws=False,pace_override=None,
             r3_context=None,r3_field=False,r3_redzone=False):
    if not fitted.get("ready") or fitted.get("status")!=STATUS:
        raise ValueError("Unverified drive fit")
    if not 100<=trials<=20000 or type(seed) is not int:
        raise ValueError("Invalid Monte Carlo parameters")
    if pace_override is not None:
        if (not isinstance(pace_override,dict) or
            pace_override.get("distribution_source")!="EARLIER_REAL_GAME_POSSESSION_COUNTS" or
            pace_override.get("source_cutoff")!=fitted["target_date"] or
            not pace_override.get("historical_deviations")):
            raise ValueError("Unverified earlier-week learned pace source")
    if r3_field or r3_redzone:
        from scripts.v12r3_possession_context import STATUS as R3_STATUS
        if (not isinstance(r3_context,dict) or r3_context.get("status")!=R3_STATUS or
            not r3_context.get("ready") or r3_context.get("cutoff")!=fitted["target_date"] or
            r3_context.get("source_games")!=fitted["source_prior_games"] or
            r3_context.get("first_publication_verified") is not False):
            raise ValueError("V12R3 source must match original weekly V04 cutoff")
    if v04_prior is not None:
        if (not isinstance(v04_prior,dict) or v04_prior.get("source")!="EARLIER_FOLD_V04" or
            (v04_prior.get("game_id") is not None and
             str(v04_prior["game_id"])!=str(fitted["target_game_id"])) or
            (v04_prior.get("asof_cutoff") is not None and
             not (dt.date.fromisoformat(v04_prior["asof_cutoff"]) <=
                  dt.date.fromisoformat(fitted["target_date"]) <
                  dt.date.fromisoformat(v04_prior["asof_cutoff"])+dt.timedelta(days=7)))
            or not all(number(v04_prior.get(k)) is not None
                       for k in ("home_points","away_points"))
            or not all(0<=v04_prior[k]<=120 for k in ("home_points","away_points"))):
            raise ValueError("Unauthenticated V04 score prior: "+
                str({"source":v04_prior.get("source"),
                     "prior_game":v04_prior.get("game_id"),
                     "target_game":fitted.get("target_game_id"),
                     "prior_cutoff":v04_prior.get("asof_cutoff"),
                     "target_date":fitted.get("target_date"),
                     "home_points":v04_prior.get("home_points"),
                     "away_points":v04_prior.get("away_points")}))
    if dated_profile is not None:
        from scripts.v11_dated_profile_bridge import verify_for_target
        if v04_prior is None or not matchup:
            raise ValueError("Dated profile research requires frozen V04 matchup prior")
        date=dt.date.fromisoformat(fitted["target_date"])
        cutoff=dt.date.fromisoformat(v04_prior["asof_cutoff"])
        if not cutoff<=date<cutoff+dt.timedelta(days=7):
            raise ValueError("Dated profile and V04 source from wrong football week")
        verify_for_target(dated_profile,{
            "game_id":fitted["target_game_id"],
            "cutoff":v04_prior["asof_cutoff"],
            "home":fitted["target_home"],"away":fitted["target_away"],
        })
    # The context and source history are fixed for a matchup. Precompute
    # 10 conditional drive distributions once instead of re-fitting them on
    # each of ~20 possessions in every Monte Carlo draw.
    representatives={"own_deep":95,"own_half":75,"midfield":55,"opponent_half":35,"red_zone":15}
    distributions={(side,zone):outcome_distribution(fitted,side,yard,matchup,
                     regress_turnovers,v04_prior,dated_profile)
        for side in ("home","away") for zone,yard in representatives.items()}
    if r3_redzone:
        from scripts.v12r3_possession_context import redzone_distribution
        distributions={
            (side,zone):redzone_distribution(r3_context,side,
                fitted["profiles"][side]["team"],fitted["profiles"][side]["opponent"],
                zone,source)
            for (side,zone),source in distributions.items()}
    rng=random.Random(seed);hm=[];ts=[];hs=[];as_=[];to_h=[];to_a=[]
    results=[];example=[]
    for i in range(trials):
        scores,turnovers,drives=one_game(fitted,matchup,rng,trace=trace and i==0,
            regress_turnovers=regress_turnovers,v04_prior=v04_prior,
            distributions=distributions,pace_override=pace_override,
            transition_context=r3_context if r3_field else None)
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
    pwin=sum(v>0 for v in hm)/trials
    # Wilson interval remains nonzero for 0% / 100% finite samples;
    # naive Wald uncertainty misleadingly reports zero in those cases.
    z=1.96
    wilson_half=z*math.sqrt(pwin*(1-pwin)/trials+(z*z)/(4*trials*trials))/(1+(z*z)/trials)
    output = {"status":STATUS,
        "model_variant":"V11_DATED_V04_OPPONENT_ADJUSTED_EPA_POSSESSIONS" if dated_profile else
          "V04_STRENGTH_ANCHORED_POSSESSIONS" if v04_prior else
          "REGRESSED_TURNOVER_MATCHUP" if regress_turnovers else
          "OPPONENT_EPA_PRESSURE_RZ_TURNOVER_MATCHUP" if matchup else "OBSERVED_DRIVE_FREQUENCY",
        "v04_prior_used":v04_prior is not None,
        "dated_v04_team_profile_used":dated_profile is not None,
        "learned_pace_override_used":pace_override is not None,
        "r3_field_position_used":r3_field,"r3_redzone_conversion_used":r3_redzone,
        "turnover_regression_used":regress_turnovers,
        "sampling_95ci_half_width_home_win":round(wilson_half,5),
        "trials":trials,"home_points_mean":round(mean(hs),3),
        "away_points_mean":round(mean(as_),3),
        "home_margin_mean":round(mean(hs)-mean(as_),3),
        "total_mean":round(mean(ts),3),
        "home_win_probability":round(pwin,5),
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
    # Research only: callers can request the exact same-run draws for proper
    # CRPS and betting-line probability calibration against the V12 challenger.
    # Default remains byte-for-byte compatible with historical V10/V11 scores.
    if return_draws:
        output["margin_draws"]=[r[0] for r in results]
        output["total_draws"]=[r[1] for r in results]
    return output

"""V12 opponent-conditioned possession research.

Two-stage observed drive outcomes: P(reach red zone | starting field position,
offense, defense) and P(TD/FG/turnover/empty | reached red zone, matchup).
Uses only earlier-week verified completed-game drives, V11 dated scouting,
and an unchanged, independently reconstructed V04 expected-score prior.
ESPN historical first-publication times remain unauthenticated. RESEARCH ONLY.
"""
import datetime as dt
import math
import random
from collections import Counter

from scripts.v10_possession_sim import (
    OUTCOMES, STATUS as V10_STATUS, _drive_outcome, _team_drives, _zone,
    clamp, outcome_distribution,
)
from scripts.v11_dated_profile_bridge import verify_for_target
from scripts.v12_availability_gate import STATUS as PIT_STATUS, _time as verified_utc

STATUS = "V12_RZ_TRIP_OUTCOME_OPPONENT_CONDITIONED_RESEARCH_ONLY"
ZONES = ("own_deep", "own_half", "midfield", "opponent_half", "red_zone")


def _smooth(numerator, denominator, prior, weight):
    return (numerator + weight * prior) / (denominator + weight)


def _event_rate(rows, event, prior, weight):
    return _smooth(sum(_drive_outcome(d) == event for d in rows),
                   len(rows), prior, weight)


def _reach_rate(rows, prior, weight):
    return _smooth(sum(bool(d["red_zone_visited"]) for d in rows),
                   len(rows), prior, weight)


def _conditional(rows, reached):
    return [d for d in rows if bool(d["red_zone_visited"]) == reached]


def _empirical_zone(league, offense, defense, zone):
    all_zone = [d for d in league if _zone(d["start_yards_to_goal"]) == zone]
    att = [d for d in offense if _zone(d["start_yards_to_goal"]) == zone]
    allowed = [d for d in defense if _zone(d["start_yards_to_goal"]) == zone]
    # League RZ reach is conditional on actual possession start, not red-zone
    # play success. Sparse attack/defense histories shrink to prior league trips.
    league_visit = _reach_rate(all_zone, .45 if zone == "opponent_half"
                               else .12 if zone in ("midfield","own_half")
                               else 1. if zone == "red_zone" else .035, 16)
    visit = clamp(.56 * _reach_rate(att, league_visit, 18) +
                  .44 * _reach_rate(allowed, league_visit, 18), .005, .995)
    if zone == "red_zone":
        # Every drive *starting* inside the red zone is already a red-zone trip.
        visit = 1.
    likelihood = {}
    for reached in (False, True):
        population = _conditional(all_zone, reached)
        a = _conditional(att, reached)
        d = _conditional(allowed, reached)
        league_rates = {k:_event_rate(population, k, .25, 12)
                        for k in OUTCOMES}
        likelihood[reached] = {k:.56 * _event_rate(a, k, league_rates[k], 16) +
                                   .44 * _event_rate(d, k, league_rates[k], 16)
                               for k in OUTCOMES}
        total = sum(likelihood[reached].values())
        likelihood[reached] = {k:likelihood[reached][k]/total for k in OUTCOMES}
    return {"visit":visit,"conditional":likelihood,
            "league_zone_drives":len(all_zone),
            "offense_zone_drives":len(att),"defense_zone_drives":len(allowed),
            "league_reached":sum(bool(d["red_zone_visited"]) for d in all_zone)}


def fit_v12(fitted,source_games,v04_prior,dated_profile,point_in_time_context=None):
    """Fit only from games strictly before the V04 weekly cutoff."""
    if not fitted.get("ready") or fitted.get("status") != V10_STATUS:
        raise ValueError("V12 requires a source-verified V10 historical drive fit")
    if not isinstance(v04_prior, dict) or v04_prior.get("source") != "EARLIER_FOLD_V04":
        raise ValueError("Missing unchanged frozen V04 prior")
    cutoff = v04_prior.get("asof_cutoff")
    if cutoff != fitted.get("target_date"):
        raise ValueError("V12 target fit must use original V04 weekly cutoff")
    if (not isinstance(dated_profile,dict) or
        dated_profile.get("historical_source_first_publication_verified") is not False):
        raise ValueError("V12 cannot silently authenticate historical scouting data")
    verify_for_target(dated_profile, {
        "game_id": fitted["target_game_id"], "cutoff": cutoff,
        "home": fitted["target_home"], "away": fitted["target_away"],
    })
    if str(v04_prior.get("game_id")) != str(fitted["target_game_id"]):
        raise ValueError("V04 score game identity mismatch")
    availability={"qb":"UNVERIFIED","injury":"UNVERIFIED","weather":"UNVERIFIED"}
    if point_in_time_context is not None:
        evidence=point_in_time_context
        # Original weekly V04 scoring cutoffs are day-level: conservatively
        # forbid evidence observed at or after that cutoff date.
        asof=verified_utc(evidence.get("asof_utc"))
        if (evidence.get("status")!=PIT_STATUS or
            evidence.get("source_cutoff_checked") is not True or
            evidence.get("score_effects_applied") is not False or
            evidence.get("model_promoted") is not False or
            str(evidence.get("game_id"))!=str(fitted["target_game_id"]) or
            evidence.get("teams")!={"home":fitted["target_home"],
                                   "away":fitted["target_away"]} or
            asof is None or asof >=
            dt.datetime.combine(dt.date.fromisoformat(cutoff),dt.time(),
                                tzinfo=dt.timezone.utc)):
            raise ValueError("V12 evidence not proven before original V04 weekly cutoff")
        for category in availability:
            if any(x is not None for x in evidence["evidence"][category].values()):
                availability[category]="PIT_SOURCE_CONFIRMED_RESEARCH_ONLY"
    if not isinstance(source_games,list):
        raise ValueError("Unverified possession source list")
    prior = [g for g in source_games if g["date"] < cutoff]
    if (len(prior) != fitted["source_prior_games"] or
        sum(len(g["drives"]) for g in prior) != fitted["prior_drives"] or
        len({g["game_id"] for g in prior}) != len(prior)):
        raise ValueError("V12 possession history differs from frozen V10 fit")
    if any(dt.date.fromisoformat(g["date"]) >= dt.date.fromisoformat(cutoff) for g in prior):
        raise ValueError("Future possession leakage")
    league = [d for g in prior for d in g["drives"]]
    zones = {}
    transition = {}
    for side in ("home","away"):
        team = fitted["profiles"][side]["team"]
        opponent = fitted["profiles"][side]["opponent"]
        attack = _team_drives(prior,team)
        allowed = _team_drives(prior,opponent,False)
        zones[side] = {zone:_empirical_zone(league,attack,allowed,zone)
                       for zone in ZONES}
        # Only genuine consecutive opposing-team drives count. Sample the
        # next short-field advantage following turnovers with empirical data.
        offense_giveaways = []
        defense_takeaways = []
        for g in prior:
            for a,b in zip(g["drives"],g["drives"][1:]):
                if (a["turnover"] and not a["defense_points"] and
                    a["team"] != b["team"] and
                    isinstance(b.get("start_yards_to_goal"),int)):
                    if a["team"] == team: offense_giveaways.append(b["start_yards_to_goal"])
                    if b["team"] == opponent: defense_takeaways.append(b["start_yards_to_goal"])
        # The second sample concerns opportunities created by this opponent
        # defense against other offenses, not opponents scoring against us.
        # Retain only actual observed transitions; no invented yard lines.
        transition[side] = {"offense_giveaways":offense_giveaways,
                            "opponent_takeaways":defense_takeaways}
    return {"status":STATUS,"ready":True,"fitted":fitted,"source_games":len(prior),
            "zones":zones,"turnover_field":transition,"prior":v04_prior,
            "dated_profile":dated_profile,"cutoff_date_exclusive":cutoff,
            "historical_first_publication_authenticated":False,
            "availability_evidence":availability,
            "availability_adjustments_applied":False,
            "model_promoted":False}


def drive_probabilities(model,side,ytg,trained_hazards=None):
    """Event probabilities are conditional on actual red-zone-trip state."""
    if model.get("status") != STATUS or not model.get("ready"):
        raise ValueError("Unfitted V12")
    zone = _zone(ytg)
    if trained_hazards is not None:
        from scripts.v12_regularized_hazards import probabilities as trained_probabilities
        if (not trained_hazards.get("ready") or
            trained_hazards.get("cutoff")!=model["cutoff_date_exclusive"] or
            trained_hazards.get("historical_source_first_publication_verified") is not False):
            raise ValueError("V12R2 learned hazards mismatch original weekly cutoff")
        profile=model["fitted"]["profiles"][side]
        return trained_probabilities(trained_hazards,side,zone,profile["team"],
                                     profile["opponent"],model["prior"],model["dated_profile"])
    raw = model["zones"][side][zone]
    base = outcome_distribution(model["fitted"],side,ytg,True,True,
                                model["prior"],model["dated_profile"])
    # Preserve every active V11/V04 pressure, EPA, tempo-independent matchup
    # and scoring-prior hazard through an odds tilt of observed two-stage
    # red-zone outcomes. Avoid claiming non-scoring research fields are fitted.
    unconditional = {k:sum(
        (raw["visit"] if reached else 1.-raw["visit"]) *
        raw["conditional"][reached][k] for reached in (False,True))
        for k in OUTCOMES}
    tilts = {k:clamp(base[k]/max(unconditional[k],.0001),.3,3.)
             for k in OUTCOMES}
    conditional = {}
    for reached in (False,True):
        weighted = {k:raw["conditional"][reached][k]*tilts[k] for k in OUTCOMES}
        total = sum(weighted.values())
        conditional[reached] = {k:weighted[k]/total for k in OUTCOMES}
    return {"reach_probability":raw["visit"],"conditional":conditional,
            "source_zone_drives":raw["league_zone_drives"]}


def _pick(rng,probabilities):
    r = rng.random()
    acc = 0.
    for kind in OUTCOMES:
        acc += probabilities[kind]
        if r <= acc:return kind
    return OUTCOMES[-1]


def _next_field(model,side,event,returns,rng):
    fitted = model["fitted"]
    kind = ("TURNOVER" if event=="TURNOVER" and not returns else
            "SCORE" if event in ("TD","FG") or returns else "NORMAL")
    league = fitted["next_field_positions"][kind]
    if kind=="TURNOVER":
        evidence = model["turnover_field"][side]
        source = evidence["offense_giveaways"]
        opponent = evidence["opponent_takeaways"]
        # Low-n transitions are dominated by the real league distribution.
        # No future-drive records or hypothetical field position values.
        r=rng.random()
        if source and r < min(.25,len(source)/(len(source)+25)):
            return rng.choice(source)
        if opponent and r < min(.50,len(source)/(len(source)+25) +
                                 len(opponent)/(len(opponent)+25)):
            return rng.choice(opponent)
    return rng.choice(league)


def one_game(model,rng,conditional,trace=False,pace=None):
    fitted = model["fitted"]
    profiles=fitted["profiles"]
    n=round((profiles["home"]["mean_possessions"]+
             profiles["away"]["mean_possessions"])/2)
    if pace is None:
        n=clamp(n+rng.choice((-2,-1,0,0,0,1,2)),7,18)
    else:
        n=clamp(round(pace["expected_possessions_each"]+
                      rng.choice(pace["historical_deviations"])),7,18)
    scores={"home":0,"away":0};takeaways={"home":0,"away":0}
    trips={"home":0,"away":0};rztd={"home":0,"away":0}
    side="home" if rng.random()<.5 else "away"
    field=75;traces=[]
    for i in range(2*n):
        zone=_zone(field)
        chance=conditional[side,zone]
        visited=rng.random()<chance["reach_probability"]
        kind=_pick(rng,chance["conditional"][visited])
        other="away" if side=="home" else "home"
        if visited:trips[side]+=1
        if visited and kind=="TD":rztd[side]+=1
        returns=False;scorer=side;points=0
        if kind=="TD":points=7
        elif kind=="FG":points=3
        elif kind=="TURNOVER":
            takeaways[other]+=1
            if rng.random()<profiles[side]["return_td_probability_conditional_turnover"]:
                scorer=other;points=7;returns=True
        scores[scorer]+=points
        next_field=_next_field(model,side,kind,returns,rng)
        if trace and i<28:
            traces.append({"offense":side,"start_yards_to_goal":field,
                           "red_zone_visited":visited,"result":kind,
                           "next_start_yards_to_goal":next_field})
        field=next_field
        side=side if returns else other
    return scores,takeaways,trips,rztd,traces


def simulate(model,trials=2000,seed=2026,trace=False,
             trained_hazards=None,use_learned_pace=False,
             use_trained_hazards=True):
    if model.get("status")!=STATUS or not model.get("ready"):
        raise ValueError("Unverified V12 context")
    if type(trials) is not int or not 100<=trials<=20000 or type(seed) is not int:
        raise ValueError("Invalid simulation parameters")
    if not use_trained_hazards and not use_learned_pace:
        raise ValueError("Empirical-hazard control requires the separate learned pace ablation")
    if trained_hazards is not None and (
        not trained_hazards.get("ready") or
        trained_hazards.get("cutoff")!=model["cutoff_date_exclusive"] or
        trained_hazards.get("historical_source_first_publication_verified") is not False):
        raise ValueError("Learned pace or hazards from mismatched weekly cutoff source")
    if use_learned_pace and trained_hazards is None:
        raise ValueError("V12R2 pace requires strictly historical trained hazards")
    pace=None
    if use_learned_pace:
        from scripts.v12_regularized_hazards import pace_profile
        pace=pace_profile(trained_hazards,model["fitted"]["target_home"],
                          model["fitted"]["target_away"])
    conditional={(side,zone):drive_probabilities(model,side,ytg,
             trained_hazards if use_trained_hazards else None)
        for side in ("home","away")
        for zone,ytg in (("own_deep",95),("own_half",75),
                         ("midfield",55),("opponent_half",35),("red_zone",15))}
    rng=random.Random(seed);margins=[];totals=[];scores_h=[];scores_a=[]
    visits_h=[];visits_a=[];td_h=[];td_a=[];sample=[]
    for i in range(trials):
        score,_,trips,rztd,traces=one_game(model,rng,conditional,trace and i==0,pace=pace)
        h=score["home"];a=score["away"]
        scores_h.append(h);scores_a.append(a)
        margins.append(h-a);totals.append(h+a)
        visits_h.append(trips["home"]);visits_a.append(trips["away"])
        td_h.append(rztd["home"]);td_a.append(rztd["away"])
        if traces:sample=traces
    sorted_m=sorted(margins);sorted_t=sorted(totals)
    quant=lambda x,p:x[int((trials-1)*p)]
    mean=lambda x:sum(x)/len(x)
    # Match V11's P(home leads after regulation) definition. Ties are
    # recorded separately; assigning half to home would make
    # paired Brier scores use incompatible event definitions.
    win=sum(m>0 for m in margins)/trials
    return {"status":STATUS,"model_variant":("V12R2_EMPIRICAL_HAZARDS_LEARNED_PACE" if
                         use_learned_pace and not use_trained_hazards else
                         "V12R2_TRAINED_RZ_DRIVES_PACE" if use_learned_pace else
                         "V12R2_TRAINED_RZ_DRIVES" if trained_hazards is not None else
                         "V12_OPPONENT_CONDITIONED_RZ_AND_TURNOVER_FIELD"),
        "home_points_mean":round(mean(scores_h),4),"away_points_mean":round(mean(scores_a),4),
        "home_margin_mean":round(mean(margins),4),"total_mean":round(mean(totals),4),
        "home_win_probability":round(win,6),
        "regulation_tie_probability":round(sum(m==0 for m in margins)/trials,6),
        "margin_p10":quant(sorted_m,.1),"margin_p90":quant(sorted_m,.9),
        "total_p10":quant(sorted_t,.1),"total_p90":quant(sorted_t,.9),
        "expected_home_redzone_trips":round(mean(visits_h),3),
        "expected_away_redzone_trips":round(mean(visits_a),3),
        "expected_home_redzone_tds":round(mean(td_h),3),
        "expected_away_redzone_tds":round(mean(td_a),3),
        "margin_draws":margins,"total_draws":totals,
        "sample_possessions":sample,"trials":trials,"model_promoted":False,
        "historical_source_publication_unauthenticated":True,
        "availability_adjustments_applied":False,
        "learned_drive_hazards_used":trained_hazards is not None and use_trained_hazards,
        "learned_possession_pace_used":use_learned_pace,
        "safe_for_betting":False}

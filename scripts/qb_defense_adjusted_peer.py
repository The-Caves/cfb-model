"""Predecision opponent-adjusted within-team QB evidence, research-only.

Compare QB passing EPA with *other QBs on the same team*, after removing
each historical opponent's previously observed defensive pass EPA allowed.
Opponent baselines use only game dates strictly EARLIER than that game's
date, so the target game cannot establish how strong its own defense was.
Inadequate attribution, missing opponents or weak peer sample => PASS.
No starter identification, fake odds, causal QB attribution or V03 promotion.
"""
import datetime as dt
import math
from collections import defaultdict
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time
from scripts.qb_passer_history import player_key

STATUS="QB_OPPONENT_DEFENSE_ADJUSTED_PEER_RESEARCH_ONLY"
MIN_NAMED_COVERAGE=.70
MIN_EPA_COVERAGE=.70
MIN_PRIOR_DEF_GAMES=2
MAX_PRIOR_DEF_GAMES=6
MIN_QB_EPA_PLAYS=15
MIN_PEER_EPA_PLAYS=15
SHRINK_PSEUDO_PLAYS=60.
MAX_EPA_INPUT_CHANGE=.7
MAX_QB_POINTS=4.

def _int(row,key):
    try:
        raw=row[key]
        if isinstance(raw,bool):raise ValueError()
        value=float(raw)
        if not math.isfinite(value) or value<0 or not value.is_integer():
            raise ValueError()
        return int(value)
    except (TypeError,ValueError,KeyError) as exc:
        raise ValueError("Invalid sourced passer count: "+key) from exc

def _float(row,key):
    try:
        raw=row[key]
        if isinstance(raw,bool):raise ValueError()
        val=float(raw)
        if not math.isfinite(val):raise ValueError()
        return val
    except (TypeError,ValueError,KeyError) as exc:
        raise ValueError("Invalid sourced passer EPA: "+key) from exc

def _source_time(row):
    when=parse_time(row["source_retrieved_at_utc"])
    if when.tzinfo is None:raise ValueError("No QB source timestamp")
    return when

def build_context(rows,game_date,observed_at):
    """Point-in-time opponent baselines; only accepted historical game/team data.

    Returns a precomputed context reusable across game widgets on the same day.
    Historical PBP first-publication times are NOT authenticated.
    """
    cutoff=dt.date.fromisoformat(game_date)
    decision=parse_time(observed_at)
    if decision.astimezone(ZoneInfo("America/New_York")).date()>cutoff:
        raise ValueError("QB opponent context requested after game day")
    by_game=defaultdict(list)
    seen=set()
    for row in rows:
        day=dt.date.fromisoformat(row["date"])
        if day>=cutoff or _source_time(row)>decision:continue
        if (row.get("betting_status")!="PASS_UNVALIDATED" or
            row.get("historical_source_time_verified") not in (False,"False","false")):
            raise ValueError("Untrusted as-of opponent QB source")
        team=row.get("team");defender=row.get("opponent")
        keyname=player_key(row["player"])
        gid=str(row["game_id"])
        if not team or not defender or team==defender or not gid.isdigit() and not gid.startswith("past"):
            raise ValueError("Invalid historical football team or game")
        key=(team,gid,keyname)
        if key in seen:raise ValueError("Duplicate opponent-adjusted QB game")
        seen.add(key)
        by_game[(team,gid)].append(row)
    accepted=[]
    rejected=0
    for (team,gid),group in by_game.items():
        dates={row["date"] for row in group}
        opponents={row["opponent"] for row in group}
        totals={_int(row,"team_pass_tagged_plays") for row in group
                if row.get("team_pass_tagged_plays") not in (None,"")}
        if len(dates)!=1 or len(opponents)!=1 or len(totals)>1:
            raise ValueError("Conflicting team-game passer evidence")
        if len(totals)!=1:
            rejected+=1;continue
        total=next(iter(totals))
        named=sum(_int(row,"pass_tagged_plays") for row in group)
        epa_plays=sum(_int(row,"pass_epa_plays") for row in group)
        epa=sum(_float(row,"pass_epa_sum") for row in group)
        if named>total or epa_plays>named:
            raise ValueError("Player attribution exceeds observed team totals")
        if (total==0 or named/total<MIN_NAMED_COVERAGE or
            epa_plays/total<MIN_EPA_COVERAGE or epa_plays==0):
            rejected+=1;continue
        accepted.append({"team":team,"game_id":gid,
            "date":dt.date.fromisoformat(next(iter(dates))),
            "opponent":next(iter(opponents)),
            "observed_offense_pass_epa":epa/epa_plays,
            "epa_plays":epa_plays,"rows":group})
    # Team X's pass defense allowed is an opponent team's *offensive*
    # QB-tagged EPA against X. No team-level sack pressure is invented.
    by_defender=defaultdict(list)
    for record in accepted:by_defender[record["opponent"]].append(record)
    for name in by_defender:by_defender[name].sort(key=lambda r:(r["date"],r["game_id"]))
    residuals=defaultdict(list)
    missing_prior=0
    for record in accepted:
        prev=[r for r in by_defender[record["opponent"]]
              if r["date"]<record["date"]]
        if len(prev)<MIN_PRIOR_DEF_GAMES:
            missing_prior+=1;continue
        prev=prev[-MAX_PRIOR_DEF_GAMES:]
        n=sum(r["epa_plays"] for r in prev)
        defensive_pass_allowed=sum(r["observed_offense_pass_epa"]*r["epa_plays"]
                                   for r in prev)/n
        for raw in record["rows"]:
            plays=_int(raw,"pass_epa_plays")
            if not plays:continue
            residuals[record["team"]].append({
                "player_key":player_key(raw["player"]),
                "player":raw["player"],"game_id":record["game_id"],
                "date":record["date"].isoformat(),"opponent":record["opponent"],
                "plays":plays,
                "adjusted_epa_sum":_float(raw,"pass_epa_sum")-plays*defensive_pass_allowed,
                "opponent_prior_defense_pass_epa_allowed":round(defensive_pass_allowed,7),
                "opponent_prior_defense_games":len(prev)})
    return {"status":STATUS,"cutoff_exclusive":game_date,
        "observed_at_utc":decision.isoformat(),
        "by_team":dict(residuals),
        "accepted_team_games":len(accepted),
        "rejected_game_coverage":rejected,
        "games_missing_prior_opponent_defense":missing_prior,
        "source_historical_publication_verified":False,
        "not_starter_probabilities":True,
        "betting_status":"PASS_UNVALIDATED"}

def peer_effect(context,team,player,coefficient):
    """Return research QB-vs-other-QB score effect, or PASS with zero effect."""
    if (context.get("status")!=STATUS or
        context.get("betting_status")!="PASS_UNVALIDATED" or
        context.get("source_historical_publication_verified") is not False):
        raise ValueError("Untrusted opponent QB context")
    if type(coefficient) not in (int,float) or not math.isfinite(coefficient):
        raise ValueError("Invalid fitted pass EPA coefficient")
    wanted=player_key(player) if isinstance(player,str) else ""
    if len(wanted)<2:raise ValueError("Opponent adjusted QB candidate required")
    rows=context["by_team"].get(team,[])
    own=[r for r in rows if r["player_key"]==wanted]
    other=[r for r in rows if r["player_key"]!=wanted]
    a=sum(r["plays"] for r in own)
    b=sum(r["plays"] for r in other)
    base={"status":"PASS_INSUFFICIENT_OPPONENT_ADJUSTED_QB_PEER_SAMPLE",
          "player":player,"team":team,"margin_impact":0.,
          "player_adjusted_plays":a,"peer_adjusted_plays":b,
          "opponent_defense_adjustment_applied":False,
          "not_starting_qb_confirmation":True}
    if a<MIN_QB_EPA_PLAYS or b<MIN_PEER_EPA_PLAYS:return base
    player_adj=sum(r["adjusted_epa_sum"] for r in own)/a
    peer_adj=sum(r["adjusted_epa_sum"] for r in other)/b
    # Both samples must be source accepted, but this remains a descriptive
    # conditional comparison, not an identified causal QB replacement effect.
    delta=player_adj-peer_adj
    effective=2*a*b/(a+b)
    reliability=effective/(effective+SHRINK_PSEUDO_PLAYS)
    feature_change=max(-MAX_EPA_INPUT_CHANGE,min(MAX_EPA_INPUT_CHANGE,delta*reliability))
    points=max(-MAX_QB_POINTS,min(MAX_QB_POINTS,feature_change*coefficient))
    return {**base,"status":"QB_OPPONENT_ADJUSTED_PEER_SHADOW",
        "margin_impact":round(points,5),
        "player_adjusted_epa_per_pass":round(player_adj,6),
        "other_qb_adjusted_epa_per_pass":round(peer_adj,6),
        "adjusted_player_minus_peer_epa":round(delta,6),
        "adjusted_games_player":len({r["game_id"] for r in own}),
        "adjusted_games_other":len({r["game_id"] for r in other}),
        "effective_sample_plays":round(effective,4),
        "reliability":round(reliability,6),
        "pass_epa_feature_delta":round(feature_change,6),
        "opponent_defense_adjustment_applied":True,
        "no_depth_chart_rank_penalty":True}

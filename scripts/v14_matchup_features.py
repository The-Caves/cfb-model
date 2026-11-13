"""V14 source-dated opponent styles for a V04-anchored RESIDUAL challenger.

Historical 2026 advanced PBP and ESPN turnover data are retrospectively
retrieved and do not have authenticated historical first-publication times.
All FEATURES are calculated from source game dates < the ORIGINAL V04
weekly cutoff, never target-game stats. This is historical research only.
"""
import csv
import datetime as dt
import math
from collections import defaultdict

STATUS="V14_DATED_MATCHUP_FEATURES_RESEARCH_ONLY"
FEATURES=("pass_matchup","rush_matchup","pressure_pass","explosive_pass",
          "turnover_quality","redzone_play","game_pace")
MIN_TEAM_GAMES=3
HALF_LIFE_DAYS=35
EPS=1e-9


def _float(x):
    try:
        n=float(x)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _ratio(row,num,den):
    a,b=_float(row.get(num)),_float(row.get(den))
    return a/b if a is not None and b is not None and b>0 else None


def _clamp(x,limit):
    return max(-limit,min(limit,x))


def load_inputs(advanced_csv,turnovers_json):
    if not isinstance(advanced_csv,list) or not isinstance(turnovers_json,dict):
        raise ValueError("V14 requires frozen advanced source and turnover report")
    if (turnovers_json.get("status")!="ESPN_COMPLETED_BOXSCORE_TURNOVERS_RESEARCH_ONLY" or
        turnovers_json.get("historical_publication_times_verified") is not False or
        turnovers_json.get("model_promoted") is not False or
        turnovers_json.get("safe_for_betting") is not False):
        raise ValueError("V14 turnover source not verified or promoted")
    adv={}
    for row in advanced_csv:
        if not all(row.get(k) for k in ("game_id","date","team","opponent")):
            raise ValueError("Missing advanced team-game identity")
        dt.date.fromisoformat(row["date"])
        key=(str(row["game_id"]),row["team"])
        if key in adv:raise ValueError("Duplicate historical advanced team-game")
        adv[key]=row
    to={}
    for row in turnovers_json["rows"]:
        key=(str(row["game_id"]),row["team"])
        if key in to:raise ValueError("Duplicate ESPN turnover team-game")
        if row.get("historical_pregame_publication_verified") is not False:
            raise ValueError("Untrusted historical turnover time")
        for k in ("turnovers_committed","takeaways_observed"):
            v=_float(row.get(k))
            if v is None or v<0 or v>15:raise ValueError("Invalid observed turnover")
        to[key]=row
    return {"status":STATUS,"advanced":adv,"turnovers":to,
            "historical_first_publication_authenticated":False,
            "game_date_before_cutoff_required":True}


def _weighted_mean(values):
    if not values:return None
    denom=sum(w for x,w in values)
    return sum(x*w for x,w in values)/denom if denom else None


def profile(source,cutoff):
    """One immutable week fit; player/defense exposures from earlier games only."""
    if source.get("status")!=STATUS or not source.get("game_date_before_cutoff_required"):
        raise ValueError("Untrusted V14 source")
    day=dt.date.fromisoformat(cutoff)
    earlier=defaultdict(list)
    ids=defaultdict(set)
    for (gid,team),row in source["advanced"].items():
        game=dt.date.fromisoformat(row["date"])
        if game>=day:continue
        if gid in ids[team]:raise ValueError("Duplicate prior team game")
        ids[team].add(gid)
        weight=math.exp2(-(day-game).days/HALF_LIFE_DAYS)
        opponent=source["advanced"].get((gid,row["opponent"]))
        own={
            "pass":_ratio(row,"pass_epa_sum","pass_epa_plays"),
            "rush":_ratio(row,"rush_epa_sum","rush_epa_plays"),
            "pressure_allowed":_ratio(row,"pressure_count","pressure_observed"),
            "explosive_pass":_ratio(row,"explosive_pass","pass_plays"),
            "redzone":_ratio(row,"redzone_success","redzone_plays"),
            "plays":_float(row.get("scrimmage_plays")),
            "pass_rate":_ratio(row,"pass_plays","scrimmage_plays")
        }
        if opponent and opponent.get("opponent")==team:
            own["def_pass"]=_ratio(opponent,"pass_epa_sum","pass_epa_plays")
            own["def_rush"]=_ratio(opponent,"rush_epa_sum","rush_epa_plays")
            own["pressure_generated"]=_ratio(opponent,"pressure_count","pressure_observed")
            own["def_explosive_pass"]=_ratio(opponent,"explosive_pass","pass_plays")
            own["def_redzone"]=_ratio(opponent,"redzone_success","redzone_plays")
        else:
            # Do not fabricate an opposing defensive split.
            own.update({k:None for k in
                ("def_pass","def_rush","pressure_generated","def_explosive_pass","def_redzone")})
        turnover=source["turnovers"].get((gid,team))
        own["giveaways"]=float(turnover["turnovers_committed"]) if turnover else None
        own["takeaways"]=float(turnover["takeaways_observed"]) if turnover else None
        earlier[team].append((gid,row["date"],weight,own))
    result={}
    for team,rows in earlier.items():
        attrs={}
        for feature in ("pass","rush","def_pass","def_rush",
            "pressure_allowed","pressure_generated","explosive_pass",
            "def_explosive_pass","redzone","def_redzone",
            "pass_rate","plays","giveaways","takeaways"):
            vals=[(data[feature],weight) for gid,date,weight,data in rows
                  if data[feature] is not None]
            attrs[feature]=_weighted_mean(vals) if len(vals)>=MIN_TEAM_GAMES else None
        result[team]={"asof_cutoff_exclusive":cutoff,"games":len(rows),
                      "historical_game_ids":sorted(gid for gid,date,w,d in rows),
                      "features":attrs}
    return {"status":STATUS,"cutoff":cutoff,"teams":result,
            "earlier_source_game_count":len({g for rows in earlier.values()
                                              for g,d,w,data in rows}),
            "source_publication_authenticated":False,
            "no_current_game_data":True}


def matchup(context,home,away):
    if (context.get("status")!=STATUS or
        context.get("source_publication_authenticated") is not False or home==away):
        raise ValueError("Untrusted historical V14 matchup context")
    h=context["teams"].get(home)
    a=context["teams"].get(away)
    if not h or not a or min(h["games"],a["games"])<MIN_TEAM_GAMES:
        return {"ready":False,"reason":"INSUFFICIENT_PRIOR_TEAM_GAMES",
                "cutoff":context["cutoff"],"features":None}
    H,A=h["features"],a["features"]
    need=("pass","rush","def_pass","def_rush","pressure_allowed",
          "pressure_generated","explosive_pass","def_explosive_pass",
          "redzone","def_redzone","pass_rate","plays","giveaways","takeaways")
    if any(H[k] is None or A[k] is None for k in need):
        return {"ready":False,"reason":"MISSING_VERIFIED_EARLIER_MATCHUP_FEATURE",
                "cutoff":context["cutoff"],"features":None}
    pass_edge=(H["pass"]+A["def_pass"]-A["pass"]-H["def_pass"])/2
    rush_edge=(H["rush"]+A["def_rush"]-A["rush"]-H["def_rush"])/2
    h_pressure=H["pass_rate"]*(H["pressure_allowed"]+A["pressure_generated"])/2
    a_pressure=A["pass_rate"]*(A["pressure_allowed"]+H["pressure_generated"])/2
    h_expl=(H["explosive_pass"]+A["def_explosive_pass"])/2
    a_expl=(A["explosive_pass"]+H["def_explosive_pass"])/2
    h_rz=(H["redzone"]+A["def_redzone"])/2
    a_rz=(A["redzone"]+H["def_redzone"])/2
    # Opponent and own turnover histories are separate, prior-only records.
    h_net=(A["giveaways"]+H["takeaways"])-(H["giveaways"]+A["takeaways"])
    raw=(pass_edge/.25,rush_edge/.25,(a_pressure-h_pressure)/.10,
         (h_expl-a_expl)/.10,h_net/2.,(h_rz-a_rz)/.15,
         (H["plays"]+A["plays"]-140)/25.)
    vec={name:round(_clamp(float(value),2.5),6)
         for name,value in zip(FEATURES,raw)}
    if not all(math.isfinite(x) for x in vec.values()):
        raise ValueError("Nonfinite opponent-conditioned feature")
    return {"ready":True,"status":STATUS,"cutoff":context["cutoff"],
            "features":vec,
            "home_prior_games":h["games"],"away_prior_games":a["games"],
            "home_prior_ids":h["historical_game_ids"],
            "away_prior_ids":a["historical_game_ids"],
            "historical_first_publication_authenticated":False}

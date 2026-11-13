"""V11: rebuild native V04 team components and weekly scouting profiles as-of.

Use the SAME earlier-week game source as the paired V04 benchmark. Match each
profile and V04 opponent-strength component to the exact game and cutoff.
These are retrospectively reconstructed, not independently proven first-
published prior to the historical cutoff.
"""
import datetime as dt
import math
from collections import defaultdict

from scripts.model_v03 import load_inputs
from scripts.weekly_profiles import build_snapshots, STATUS as PROFILE_STATUS
from scripts.v04_direct_scores import fit as fit_v04, predict as predict_v04, STATUS as V04_STATUS

STATUS="V11_V04_NATIVE_DATE_PROFILE_BRIDGE_RESEARCH_ONLY"

def bridge(games_path,advanced_path,manifest_path,targets):
    source,advanced,manifest=load_inputs(games_path,advanced_path,manifest_path)
    if manifest.get("historical_pregame_availability_verified") is not False:
        raise ValueError("Missing retrospective source warning")
    all_names=sorted({x[side] for x in source for side in ("home","away")})
    by_id={str(x["game_id"]):x for x in source}
    cutoffs=sorted({dt.date.fromisoformat(t["cutoff"]) for t in targets})
    if not cutoffs or any(x.year!=2026 for x in cutoffs):
        raise ValueError("Only 2026 cutoffs permitted")
    snap=build_snapshots(source,advanced,all_names,cutoffs)
    indexed={x["cutoff_date_exclusive"]:x for x in snap}
    models={}
    for cutoff in cutoffs:
        day=cutoff.isoformat()
        prior=[g for g in source if g["date"]<day]
        instant=dt.datetime.combine(cutoff,dt.time(12),tzinfo=dt.timezone.utc).isoformat()
        model=fit_v04(prior,instant)
        if model["status"]!=V04_STATUS or model["historical_first_publication_verified"] is not False:
            raise ValueError("Untrusted V04 team component source")
        models[day]=model
    result={}
    for t in targets:
        gid=str(t["game_id"])
        src=by_id.get(gid)
        if not src or src["home"]!=t["home"] or src["away"]!=t["away"]:
            raise ValueError("V04 game and source team mismatch")
        cutoff=t["cutoff"]
        game_date=dt.date.fromisoformat(src["date"])
        if not dt.date.fromisoformat(cutoff)<=game_date<dt.date.fromisoformat(cutoff)+dt.timedelta(days=7):
            raise ValueError("Game is outside original frozen V04 week")
        snap_at=indexed[cutoff]
        if snap_at["evidence_status"]!=PROFILE_STATUS or snap_at["historical_publication_times_verified"] is not False:
            raise ValueError("Untrusted weekly profile source")
        profiles={p["team"]:p for p in snap_at["profiles"]}
        home,away=profiles[src["home"]],profiles[src["away"]]
        neutral=str(src["neutral"]).lower()
        if neutral not in ("true","false"):raise ValueError("Historical home-field information unknown")
        model=models[cutoff]
        direct=predict_v04(model,src["home"],src["away"],neutral=="true")
        if direct is None:raise ValueError("No original V04 source model")
        for key,raw in (("home_points","home_points"),("away_points","away_points")):
            actual=float(t[raw])
            if not math.isfinite(actual) or abs(actual-direct[key])>0.011:
                raise ValueError("Reconstructed V04 score differs from saved weekly baseline")
        if any(p["games_before_cutoff"]!=len(p["prior_game_ids"]) for p in (home,away)):
            raise ValueError("Corrupt dated team profile")
        if any(any(by_id[x]["date"]>=cutoff for x in p["prior_game_ids"]) for p in (home,away)):
            raise ValueError("Future-game leakage inside weekly team profile")
        result[gid]={
            "status":STATUS,"game_id":gid,"cutoff_date_exclusive":cutoff,
            "historical_source_first_publication_verified":False,
            "scores_reconciled_to_weekly_v04":True,
            "v04_model_training_games":model["n_training_games"],
            "v04_scoring_intercept":round(model["scoring_intercept"],5),
            "v04_home_field_points":round(model["home_field_points"],5),
            "teams":{},
        }
        for side,team,p in (("home",src["home"],home),("away",src["away"],away)):
            result[gid]["teams"][side]={
                "team":team,"games_before_cutoff":p["games_before_cutoff"],
                "prior_game_ids":p["prior_game_ids"],
                "weekly_recent_form":p["recent_form"],
                "v04_neutral_strength":round(model["neutral_team_strength"][team],5),
                "v04_scoring_offense_component":round(model["offense"][team],5),
                "v04_scoring_defense_component":round(model["defense"][team],5),
                "asof_profile_status":PROFILE_STATUS,
            }
    return {"status":STATUS,"season":2026,"historical_publication_verified":False,
            "source_weekly_cutoffs":[x.isoformat() for x in cutoffs],
            "target_games":len(result),"models_fitted":len(models),
            "profiles":result,"used_in_published_v04":False,
            "model_promoted":False,"safe_for_betting":False}

def verify_for_target(item,game):
    if (not isinstance(item,dict) or item.get("status")!=STATUS or
        item.get("historical_source_first_publication_verified") is not False or
        item.get("scores_reconciled_to_weekly_v04") is not True or
        str(item.get("game_id"))!=str(game["game_id"]) or
        item.get("cutoff_date_exclusive")!=game["cutoff"] or
        not item.get("teams")):
        raise ValueError("Unmatched or hindsight weekly V04 team profile")
    for side in ("home","away"):
        p=item["teams"].get(side)
        if (not isinstance(p,dict) or p.get("team")!=game[side] or
            not isinstance(p.get("weekly_recent_form"),dict) or
            type(p.get("games_before_cutoff")) is not int or
            p["games_before_cutoff"]!=len(p.get("prior_game_ids",[])) or
            p.get("asof_profile_status")!=PROFILE_STATUS or
            any(not isinstance(x,str) for x in p.get("prior_game_ids",[])) or
            any(type(p.get(k)) not in (int,float) or not math.isfinite(p[k]) for k in
                ("v04_neutral_strength","v04_scoring_offense_component","v04_scoring_defense_component"))):
            raise ValueError("Untrusted historical team identity or fitted V04 components")
    return True

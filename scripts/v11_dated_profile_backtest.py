"""V11 historical V04 + dated-profile possession-simulator ablation.

Both possession variants use identical earlier-WEEKLY-cutoff drive history,
same as reconstructed V04's training cutoff, seed, trials and market quotes.
The V11 challenger replaces raw matchup EPA with frozen weekly opponent-
adjusted team-profile EPA where both sides have genuine earlier evidence.
It does not silently blend final scores or re-use today's team profile.
Historical raw 2026 source *first publication* is not authenticated.
"""
import argparse
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.v11_dated_profile_bridge import bridge, STATUS as BRIDGE_STATUS
from scripts.v10_possession_sim import advanced_index, fit, simulate
from scripts.v10_possession_backtest import _metric
from scripts.possession_drive_ingest import STATUS as DRIVE_STATUS

STATUS = "V11_DATED_PROFILE_V04_ANCHORED_POSSESSION_PAIRED_RESEARCH_ONLY"
VERSIONS = ("v04","v10_same_weekly_cutoff","v11_dated_opponent_epa")

def _score(s):
    return {"home_points":s["home_points_mean"],"away_points":s["away_points_mean"],
            "margin":s["home_margin_mean"],"total":s["total_mean"],
            "home_win_probability":s["home_win_probability"]}

def _has_adjusted(profile):
    p=profile["teams"]
    def ok(side,field):
        x=p[side]
        return (x["games_before_cutoff"]>=2 and
                x["weekly_recent_form"].get(field) is not None)
    return (ok("home","epa_off_adj") and ok("away","epa_def_adj") and
            ok("away","epa_off_adj") and ok("home","epa_def_adj"))

def evaluate(archive,source,advanced,bridge_result,min_past=35,trials=2000):
    if (archive.get("status")!="V10_R2_2026_PROFILE_ANCHORED_POSSESSION_PAIRED_V04_RETROSPECTIVE" or
        archive.get("tested_games")!=len(archive.get("games",[])) or
        archive.get("model_promoted") is not False or
        archive.get("source_historic_publication_timing_verified") is not False or
        not archive.get("games")):
        raise ValueError("Untrusted same-cohort archived V10 original")
    if (source.get("status")!=DRIVE_STATUS or source.get("games_accepted")!=387 or
        source.get("historical_pregame_publication_times_verified") is not False or
        len(source.get("games",[]))!=387 or
        source.get("model_promoted") is not False):
        raise ValueError("Changed/unauthenticated verified 2026 drive source cohort")
    if (bridge_result.get("status")!=BRIDGE_STATUS or
        bridge_result.get("target_games")!=len(archive["games"]) or
        bridge_result.get("historical_publication_verified") is not False):
        raise ValueError("Historical team-profile bridge is missing")
    seen=set()
    evaluated=[];skipped=Counter()
    for prev in archive["games"]:
        gid=str(prev["game_id"])
        if gid in seen:raise ValueError("Duplicated held-out paired matchup")
        seen.add(gid)
        profile=bridge_result["profiles"].get(gid)
        if not profile:raise ValueError("Missing dated V04 team profile")
        # Embargo the entire current football WEEK, not only target game date.
        target={"game_id":gid,"date":prev["cutoff"],
                "home":prev["home"],"away":prev["away"]}
        model=fit(source["games"],advanced,target,min_games=min_past)
        if not model["ready"]:
            skipped[model["reason"]]+=1
            continue
        old=prev["v04"]
        prior={"source":"EARLIER_FOLD_V04","home_points":old["home_points"],
               "away_points":old["away_points"],"game_id":gid,
               "asof_cutoff":prev["cutoff"]}
        seed=int(hashlib.sha256(("v11|"+gid).encode()).hexdigest()[:16],16)
        normal=simulate(model,True,trials=trials,seed=seed,
                        regress_turnovers=True,v04_prior=prior)
        enriched=simulate(model,True,trials=trials,seed=seed,
                          regress_turnovers=True,v04_prior=prior,
                          dated_profile=profile)
        row={key:prev[key] for key in
             ("game_id","home","away","date","cutoff","kickoff_utc",
              "final_home","final_away","market")}
        row["v04"]=old
        row["simulations"]={
          "v10_same_weekly_cutoff":_score(normal),
          "v11_dated_opponent_epa":_score(enriched)}
        row["source_provenance"]={
            "original_v04_scoring_prior":old,
            "same_week_training_cutoff_exclusive":prev["cutoff"],
            "profile_game_ids":{
              "home":profile["teams"]["home"]["prior_game_ids"],
              "away":profile["teams"]["away"]["prior_game_ids"]},
            "v04_components":{
              side:{k:profile["teams"][side][k] for k in
                    ("v04_neutral_strength","v04_scoring_offense_component",
                     "v04_scoring_defense_component")}
              for side in ("home","away")},
            "weekly_recent_form":{
              side:profile["teams"][side]["weekly_recent_form"]
              for side in ("home","away")},
            "dated_opponent_adjusted_epa_available_both_ways":_has_adjusted(profile),
            "actual_source_date_published_pre_kickoff_authenticated":False,
            "simulator_original_scoring_prior_replaced":False,
            "scoring_changes_only_when_dated_adjusted_epa_is_available":True,
            "earlier_verified_drive_games":model["source_prior_games"],
            "model_promoted":False,
        }
        evaluated.append(row)
    weeks={}
    for w in sorted({r["cutoff"] for r in evaluated}):
        subset=[r for r in evaluated if r["cutoff"]==w]
        weeks[w]={"games":len(subset),"models":{v:_metric(subset,v) for v in VERSIONS},
                   "adjusted_epa_available":sum(
                       r["source_provenance"]["dated_opponent_adjusted_epa_available_both_ways"]
                       for r in subset)}
    result={"status":STATUS,"season":2026,"models":{v:_metric(evaluated,v) for v in VERSIONS},
        "matched_games":len(evaluated),"original_v10_games":len(archive["games"]),
        "excluded":dict(skipped),
        "both_teams_asof_adjusted_epa_games":sum(
            r["source_provenance"]["dated_opponent_adjusted_epa_available_both_ways"]
            for r in evaluated),
        "historical_source_first_publication_verified":False,
        "model_promoted":False,"promotion_eligible":False,
        "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
        "historical_book_lines_source_observed_not_closing":True,
        "simulation_type":"TRUE_SEQUENTIAL_POSSESSION_SIMULATION_WITH_DATED_TEAM_PROFILE",
        "variants":{
          "v04":"Reconstructed same original weekly V04 opponent-adjusted scores",
          "v10_same_weekly_cutoff":"V04-anchored actual drives, earlier-week possessions and raw advanced matchup",
          "v11_dated_opponent_epa":"Same possessions, prior and Monte Carlo seed, with earlier-week opponent-adjusted EPA substituted when both sides have coverage"},
        "weekly":weeks,"games":evaluated,
        "limitations":[
            "This is a retrospective as-of-date reconstruction, NOT verified pregame publication of PBP/EPA",
            "Same original 2026 V04 model forecast paired and revalidated on source game IDs",
            "No current profile, same or later football week results used by either possession variant",
            "V04's opponent-adjusted strength is present as an expected-score prior; feature transfer replaces rather than stacks raw EPA",
            "Resumé SOS/SOR/SOV remains logged research context, not fitted scoring multipliers",
            "Unverified historical line quotes are not fabricated; numbers only on observed pregame prices",
            "More feature inputs do not constitute an independently measured edge or grounds for model promotion",
        ]}
    return result

def run(previous,drives,games,advanced,manifest,output,trials=2000):
    archived=json.loads(Path(previous).read_text())
    source=json.loads(Path(drives).read_text())
    targets=[{"game_id":str(g["game_id"]),"home":g["home"],"away":g["away"],
              "cutoff":g["cutoff"],"home_points":g["v04"]["home_points"],
              "away_points":g["v04"]["away_points"]} for g in archived["games"]]
    profiles=bridge(games,advanced,manifest,targets)
    result=evaluate(archived,source,advanced_index(advanced),profiles,trials=trials)
    result["profile_bridge_coverage"]={k:profiles[k] for k in
         ("status","target_games","models_fitted","source_weekly_cutoffs",
          "historical_publication_verified")}
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:result[k] for k in
          ("status","matched_games","excluded","both_teams_asof_adjusted_epa_games",
           "models","weekly","profile_bridge_coverage","promotion_eligible")},
           sort_keys=True))
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    for k in ("previous","drives","games","advanced","manifest","output"):
        parser.add_argument("--"+k,required=True)
    parser.add_argument("--trials",type=int,default=2000)
    a=parser.parse_args()
    run(a.previous,a.drives,a.games,a.advanced,a.manifest,a.output,a.trials)

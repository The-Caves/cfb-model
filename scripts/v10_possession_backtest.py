"""2026 V10 true possessions: paired retrospective V04, ATS and O/U audit.

Only historical completed observed drive records from strictly earlier 2026
football dates train this model. Uses opponent-specific turnover/pressure/EPA
interactions and actual field position and defensive-score events.
Historical source publication timing is NOT verified at old cutoffs, so this
is research rather than authenticated prospective wagering performance.
"""
import argparse,datetime as dt,hashlib,json
from collections import defaultdict
from pathlib import Path
from scripts.v10_possession_sim import STATUS,advanced_index,fit,simulate
from scripts.v09_retro_score_sim import load_rows,metrics as v09_metrics
from scripts.game_context import parse_time
from scripts.possession_drive_ingest import STATUS as SOURCE_STATUS

REPORT="V10_R2_2026_PROFILE_ANCHORED_POSSESSION_PAIRED_V04_RETROSPECTIVE"
def _score(row,variant):
    if variant=="v04":return row["v04"]
    return row["simulations"][variant]

def _correct(side,real):
    if side in (None,"PASS") or real=="PUSH":return None
    return int(side==real)
def _choice(x):return "HOME" if x>0 else "AWAY" if x<0 else "PASS"
def _metric(rows,variant):
    if not rows:return {"games":0}
    margin=[];total=[];su=[];ats=[];ou=[];brier=[]
    spread_baseline=[];total_baseline=[]
    for g in rows:
        p=_score(g,variant)
        m=p["margin"];t=p["total"]
        actual_m=g["final_home"]-g["final_away"];actual_t=g["final_home"]+g["final_away"]
        margin.append(abs(m-actual_m));total.append(abs(t-actual_t))
        su.append(_correct(_choice(m),_choice(actual_m).replace("PASS","PUSH")))
        sp=g["market"].get("home_spread");line=g["market"].get("total")
        if sp is not None:
            ats.append(_correct(_choice(m+sp),_choice(actual_m+sp).replace("PASS","PUSH")))
            spread_baseline.append(abs(-sp-actual_m))
        if line is not None:
            pred="OVER" if t>line else "UNDER" if t<line else "PASS"
            actual="OVER" if actual_t>line else "UNDER" if actual_t<line else "PUSH"
            ou.append(_correct(pred,actual))
            total_baseline.append(abs(line-actual_t))
        if variant!="v04" and actual_m!=0:
            brier.append((p["home_win_probability"]-int(actual_m>0))**2)
    bin=lambda items:{"n":len([x for x in items if x is not None]),
        "wins":sum(x for x in items if x is not None),
        "rate":round(sum(x for x in items if x is not None)/len([x for x in items if x is not None]),4)
            if any(x is not None for x in items) else None}
    return {"games":len(rows),"margin_mae":round(sum(margin)/len(margin),4),
        "total_mae":round(sum(total)/len(total),4),
        "winner":bin(su),"hypothetical_ats":bin(ats),"hypothetical_ou":bin(ou),
        "winner_brier":round(sum(brier)/len(brier),5) if brier else None,
        "book_spread_mae":round(sum(spread_baseline)/len(spread_baseline),4) if spread_baseline else None,
        "book_total_mae":round(sum(total_baseline)/len(total_baseline),4) if total_baseline else None}

def audit(games,source,advanced,min_past=35,trials=500):
    if (source.get("status")!=SOURCE_STATUS or source.get("season")!=2026
        or source.get("model_promoted") is not False or source.get("safe_for_betting") is not False
        or source.get("historical_pregame_publication_times_verified") is not False
        or not isinstance(source.get("games"),list)):
        raise ValueError("Unreviewed possession sources")
    accepted=source["games"]
    if len({g["game_id"] for g in accepted})!=len(accepted):
        raise ValueError("Duplicated real ESPN possession source game")
    for g in accepted:
        if not g.get("scoring_ownership_verified") or not g.get("scoreboard_and_boxscore_reconciled"):
            raise ValueError("Cannot train on unreviewed source game")
    ready=[];skipped=defaultdict(int)
    for game in games:
        model=fit(accepted,advanced,game,min_games=min_past,min_team_games=1)
        if not model["ready"]:
            skipped[model["reason"]]+=1
            continue
        # Deterministic common-random-numbers grade to compare scoring and
        # turnover effects, without opportunistically picking best variant.
        seed=int(hashlib.sha256(("v10|"+game["game_id"]).encode()).hexdigest()[:16],16)
        base=simulate(model,False,trials=trials,seed=seed)
        matchup=simulate(model,True,trials=trials,seed=seed)
        regressed=simulate(model,True,trials=trials,seed=seed,
                           regress_turnovers=True)
        frozen_prior={"source":"EARLIER_FOLD_V04","home_points":game["home_points"],
                      "away_points":game["away_points"],
                      "game_id":game["game_id"],"asof_cutoff":game["cutoff"]}
        anchored=simulate(model,True,trials=trials,seed=seed,
                          regress_turnovers=True,v04_prior=frozen_prior)
        row={k:game[k] for k in ("game_id","home","away","date","cutoff","kickoff_utc",
                "final_home","final_away","market")}
        row["v04"]={"home_points":game["home_points"],"away_points":game["away_points"],
                    "margin":game["home_points"]-game["away_points"],
                    "total":game["home_points"]+game["away_points"]}
        row["simulations"]={
            "empirical_drives":{
                "margin":base["home_margin_mean"],"total":base["total_mean"],
                "home_points":base["home_points_mean"],"away_points":base["away_points_mean"],
                "home_win_probability":base["home_win_probability"]},
            "matchup_drives":{
                "margin":matchup["home_margin_mean"],"total":matchup["total_mean"],
                "home_points":matchup["home_points_mean"],"away_points":matchup["away_points_mean"],
                "home_win_probability":matchup["home_win_probability"]},
            "regressed_turnover_drives":{
                "margin":regressed["home_margin_mean"],"total":regressed["total_mean"],
                "home_points":regressed["home_points_mean"],"away_points":regressed["away_points_mean"],
                "home_win_probability":regressed["home_win_probability"]},
            "v04_anchored_drives":{
                "margin":anchored["home_margin_mean"],"total":anchored["total_mean"],
                "home_points":anchored["home_points_mean"],"away_points":anchored["away_points_mean"],
                "home_win_probability":anchored["home_win_probability"]}}
        row["turnover_risk"]={
            "expected_home_takeaways":matchup["expected_home_takeaways"],
            "expected_away_takeaways":matchup["expected_away_takeaways"],
            "prob_home_zero_takeaways":matchup["prob_home_zero_takeaways"],
            "home_margin_zero_takeaways":matchup["home_margin_when_home_zero_takeaways"],
            "home_margin_positive_takeaways":matchup["home_margin_when_home_positive_takeaways"]}
        row["simulation_evidence"]={
            "prior_verified_games":model["source_prior_games"],
            "prior_drives":model["prior_drives"],
            "team_coverage":model["team_coverage"],
            "source_first_published_before_game_unverified":True,
            "v04_frozen_scoring_prior_from_earlier_week":True,
            "asof_advanced_features_recency_half_life_days":28,
            "available_advanced_metrics":{
               "home_offense":model["profiles"]["home"]["offense_context"],
               "away_offense":model["profiles"]["away"]["offense_context"],
               "home_defense_allowed":model["profiles"]["away"]["defense_context"],
               "away_defense_allowed":model["profiles"]["home"]["defense_context"],
            }}
        ready.append(row)
    weeks={}
    for week in sorted({r["cutoff"] for r in ready}):
        wk=[r for r in ready if r["cutoff"]==week]
        weeks[week]={"games":len(wk),"models":{v:_metric(wk,v)
            for v in ("v04","empirical_drives","matchup_drives",
                      "regressed_turnover_drives","v04_anchored_drives")}}
    examples=[r for r in ready if "Kentucky Wildcats" in (r["home"],r["away"])]
    return {"status":REPORT,"season":2026,"source_drive_model":STATUS,
        "model_promoted":False,"promotion_eligible":False,"safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED",
        "source_historic_publication_timing_verified":False,
        "score_ownership_reconciled":True,
        "simulation_type":"TRUE_OBSERVED_POSSESSION_SEQUENCE_NOT_PLAY_BY_PLAY",
        "tested_games":len(ready),"skipped":dict(skipped),
        "drives_source_accepted":len(accepted),
        "drives_source_quarantined":source.get("games_quarantined"),
        "trials_per_model":trials,
        "feature_inventory":{
            "v04_score_prior":"opponent-adjusted earlier-fold home/away expected score",
            "recency_half_life_days":28,
            "drive_zone_rates":"2026 observed starting field position and drive endings",
            "turnover_context":"earlier offense giveaway versus opposing defense takeaways with reliability regression",
            "scoring_shifts":"prior offense and opposing allowed EPA, pass/rush EPA, pressure, third down, explosiveness and red-zone play success",
            "missing_not_guessed":"verified starting QB, injuries, localized weather, historical PBP publication timestamps",
            "simulation_engine":"sequential scored possessions with turnover short-field and defensive return TD ownership",
        },
        "summary":{v:_metric(ready,v) for v in
            ("v04","empirical_drives","matchup_drives",
             "regressed_turnover_drives","v04_anchored_drives")},
        "weeks":weeks,"kentucky_examples":examples,"games":ready,
        "research_limits":[
            "Offensive points and defensive return touchdowns are separate, source matched and boxscore reconciled",
            "EPA, pressure, red zone and turnover features use only games dated before test game; historical source publication timestamps remain unauthenticated",
            "Drive start and transition positions come from observed 2026 ESPN source, not from final score",
            "True POSSESSION simulator, not yet detailed play-by-play/down-and-distance 4Q clock state",
            "Monte Carlo probabilities are not calibrated betting edges and cannot replace V04 without independent prospective validation",
            "Only authentic pregame saved bookstore prices are used, with no unknown lines imputed",
            "Observed opponent-specific outcomes do not prove causality; turnover-luck regression remains a research hypothesis"]
    }

def run(source_file,advanced_file,baseline,game_csv,market_root,output,min_past=35,trials=500):
    now=dt.datetime.now(dt.timezone.utc)
    games,coverage=load_rows(baseline,game_csv,market_root,now)
    source=json.loads(Path(source_file).read_text())
    advanced=advanced_index(advanced_file)
    result=audit(games,source,advanced,min_past,trials)
    result["v04_coverage"]=coverage
    result["captured_at_utc"]=source["captured_at_utc"]
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:result[k] for k in
       ("status","tested_games","skipped","drives_source_accepted","drives_source_quarantined",
        "summary","weeks","promotion_eligible")},sort_keys=True))
    print("KENTUCKY_CASES",json.dumps([{
         "game_id":r["game_id"],"kickoff":r["kickoff_utc"],
         "matchup":r["home"]+" v "+r["away"],
         "v04_margin":r["v04"]["margin"],
         "sim_margin":r["simulations"]["matchup_drives"]["margin"],
         "actual_margin":r["final_home"]-r["final_away"],
         "turnover_risk":r["turnover_risk"]} for r in result["kentucky_examples"]]))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for arg in ("source","advanced","baseline","games","market-root","output"):
        p.add_argument("--"+arg,required=True)
    p.add_argument("--min-past",type=int,default=35)
    p.add_argument("--trials",type=int,default=500)
    a=p.parse_args()
    run(a.source,a.advanced,a.baseline,a.games,getattr(a,"market_root"),a.output,a.min_past,a.trials)

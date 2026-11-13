"""V10R2 Monte Carlo stability on selected real 2026 prior-game matchup fits.

Re-simulate each selected game at 500/2000/5000/10000 trials using the same
seed and same as-of possessions. This measures simulation sampling noise,
NOT the model's outcome accuracy or probability calibration.
"""
import argparse,datetime as dt,hashlib,json
from pathlib import Path
from scripts.v10_possession_sim import advanced_index,fit,simulate
from scripts.v09_retro_score_sim import load_rows
from scripts.game_context import parse_time

STATUS="V10R2_MONTE_CARLO_CONVERGENCE_RESEARCH_ONLY"
COUNTS=(500,2000,5000,10000)

def run(source_file,advanced_file,benchmark,game_csv,market_root,output,max_games=3):
    from scripts.v10_possession_backtest import _metric
    archive=json.loads(Path(source_file).read_text())
    games,coverage=load_rows(benchmark,game_csv,market_root,dt.datetime.now(dt.timezone.utc))
    advanced=advanced_index(advanced_file)
    cases=[]
    preferred=[
        ("Tennessee Volunteers","Kentucky Wildcats"),
        ("Kentucky Wildcats","LSU Tigers"),
        ("Oklahoma Sooners","Kentucky Wildcats"),
        ("Georgia Bulldogs","Ole Miss Rebels"),
    ]
    for h,a in preferred:
        for game in games:
            if game["home"]!=h or game["away"]!=a:continue
            m=fit(archive["games"],advanced,game,min_games=35)
            if not m["ready"]:continue
            seed=int(hashlib.sha256(("convergence|"+game["game_id"]).encode()).hexdigest()[:16],16)
            v04={"source":"EARLIER_FOLD_V04","home_points":game["home_points"],
                 "away_points":game["away_points"],"game_id":game["game_id"],
                 "asof_cutoff":game["cutoff"]}
            reports=[]
            for n in COUNTS:
                sim=simulate(m,True,trials=n,seed=seed,
                    regress_turnovers=True,v04_prior=v04)
                reports.append({"n":n,
                    "home_win_probability":sim["home_win_probability"],
                    "winner_sampling_ci_halfwidth":sim["sampling_95ci_half_width_home_win"],
                    "margin_mean":sim["home_margin_mean"],
                    "total_mean":sim["total_mean"],
                    "expected_home_takeaways":sim["expected_home_takeaways"],
                    "home_margin_when_zero_takeaways":sim["home_margin_when_home_zero_takeaways"],
                    "home_margin_when_positive_takeaways":sim["home_margin_when_home_positive_takeaways"],
                    "prob_home_zero_takeaways":sim["prob_home_zero_takeaways"],
                    "margin_range_p05_p50_p95":sim["margin_p05_p50_p95"],
                    "total_range_p05_p50_p95":sim["total_p05_p50_p95"]})
            cases.append({"game_id":game["game_id"],"home":h,"away":a,
                "kickoff_utc":game["kickoff_utc"],
                "frozen_v04_home_margin":game["home_points"]-game["away_points"],
                "frozen_v04_total":game["home_points"]+game["away_points"],
                "final_home":game["final_home"],"final_away":game["final_away"],
                "prior_verified_drive_games":m["source_prior_games"],
                "prior_verified_drives":m["prior_drives"],
                "trials":reports,
                "p_diff_500_to_10000":round(abs(reports[-1]["home_win_probability"]-
                                                 reports[0]["home_win_probability"]),5),
                "p_diff_5000_to_10000":round(abs(reports[-1]["home_win_probability"]-
                                                  reports[-2]["home_win_probability"]),5)})
            break
        if len(cases)>=max_games:break
    result={"status":STATUS,"season":2026,
        "model_promoted":False,"historical_source_publication_verified":False,
        "sampled_games":len(cases),"trials":list(COUNTS),
        "risk_note":"Monte Carlo convergence is not predictive calibration",
        "comparisons":cases}
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result,sort_keys=True))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for field in ("source","advanced","benchmark","games","market-root","output"):
        p.add_argument("--"+field,required=True)
    p.add_argument("--max-games",type=int,default=3)
    a=p.parse_args()
    run(a.source,a.advanced,a.benchmark,a.games,a.market_root,a.output,a.max_games)

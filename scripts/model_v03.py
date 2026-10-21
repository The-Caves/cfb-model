"""2026-only retrospective weekly football features and v0.3 research backtest.

The SportsDataverse 2026 PBP release is retrospectively mutable. Historical
game inputs are filtered by kickoff but publication-time availability is NOT
verified; results are never bettable, and are NOT a leakage-free backtest.
"""
import argparse,csv,datetime as dt,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np

UTC=dt.timezone.utc
SCORE=["score_margin_form","scoring_total_form","win_rate_form","rest_days_diff","neutral_site"]
ADV=["off_epa_matchup","def_epa_matchup","pass_epa_form","rush_epa_form",
     "success_form","explosive_pass_form","explosive_rush_form",
     "pressure_form","drive_yards_form","pass_rate_form","epa_coverage_form"]
FEATURES=SCORE+ADV

def timestamp(s):
    x=dt.datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if x.tzinfo is None:raise ValueError("Unzoned source time")
    return x.astimezone(UTC)

def numeric(row,name):
    value=row.get(name)
    if value is None or str(value).strip()=="":return None
    x=float(value)
    return x if math.isfinite(x) else None

def rate(row,numerator,denominator):
    n=numeric(row,numerator);d=numeric(row,denominator)
    return n/d if n is not None and d and d>0 else None

def load_inputs(game_path,advanced_path,manifest_path):
    games=list(csv.DictReader(open(game_path,encoding="utf-8-sig",newline="")))
    advanced=list(csv.DictReader(open(advanced_path,encoding="utf-8-sig",newline="")))
    manifest=json.loads(Path(manifest_path).read_text())
    if manifest.get("season")!=2026 or manifest.get("betting_status")!="PASS_UNVALIDATED":
        raise ValueError("Expected unvalidated 2026 advanced research manifest")
    if manifest.get("historical_pregame_availability_verified") is not False:
        raise ValueError("Retrospective source status must be explicitly unverified")
    seen=set()
    for g in games:
        if g["game_id"] in seen:raise ValueError("Duplicate ESPN game")
        seen.add(g["game_id"])
        if not g["home"] or not g["away"] or g["home"]==g["away"]:
            raise ValueError("Invalid ESPN opponents")
        if timestamp(g["kickoff_utc"]).year!=2026:
            raise ValueError("Season mismatch")
        int(g["home_score"]);int(g["away_score"])
    ledger={g["game_id"]:g for g in games}
    team_rows=defaultdict(dict)
    for p in advanced:
        gid=p["game_id"];team=p["team"]
        if gid not in ledger:raise ValueError("Advanced row for unverified ESPN final")
        g=ledger[gid]
        if team not in (g["home"],g["away"]) or team in team_rows[gid]:
            raise ValueError("Duplicate or invalid advanced game/team")
        if p["opponent"]!=(g["away"] if team==g["home"] else g["home"]):
            raise ValueError("Advanced team opponent mismatch")
        if p["date"]!=g["date"]:
            raise ValueError("Advanced date does not match ESPN")
        team_rows[gid][team]=p
    for gid,parts in team_rows.items():
        if set(parts)!={ledger[gid]["home"],ledger[gid]["away"]}:
            raise ValueError("Advanced game must be two-sided")
    games.sort(key=lambda g:(timestamp(g["kickoff_utc"]),g["game_id"]))
    return games,team_rows,manifest

def game_stats(g,team,adv):
    home=team==g["home"];opp=g["away"] if home else g["home"]
    pf=int(g["home_score"] if home else g["away_score"])
    pa=int(g["away_score"] if home else g["home_score"])
    p=adv.get(g["game_id"],{}).get(team)
    if p is None:
        advanced={}
    else:
        advanced={
          "epa_off":rate(p,"off_epa_sum","epa_plays"),
          "epa_def":rate(p,"def_epa_sum","def_epa_plays"),
          "epa_pass":rate(p,"pass_epa_sum","pass_epa_plays"),
          "epa_rush":rate(p,"rush_epa_sum","rush_epa_plays"),
          "success":rate(p,"success_count","success_plays"),
          "explosive_pass":rate(p,"explosive_pass","pass_plays"),
          "explosive_rush":rate(p,"explosive_rush","rush_plays"),
          "pressure":rate(p,"pressure_count","pressure_observed"),
          "drive_yards":rate(p,"drive_yards_sum","drives"),
          "pass_rate":rate(p,"pass_plays","scrimmage_plays")}
    return {"team":team,"opponent":opp,"kickoff":timestamp(g["kickoff_utc"]),
            "game_id":g["game_id"],"points_for":pf,"points_against":pa,
            "margin":max(-28,min(28,pf-pa)),"win":int(pf>pa),
            **advanced}

def weighted(history,field,min_count=1):
    recent=sorted(history,key=lambda x:x["kickoff"],reverse=True)[:6]
    terms=[(float(r[field]),0.78**i) for i,r in enumerate(recent)
           if r.get(field) is not None]
    if len(terms)<min_count:return None
    return sum(a*w for a,w in terms)/sum(w for _,w in terms)

def summarize(history,now):
    prior=[r for r in history if r["kickoff"].date()<now.date()]
    if len(prior)!=len(history):
        raise ValueError("Current-day or future result entered weekly features")
    rest=min(21,max(0,(now-max(r["kickoff"] for r in prior)).days)) if prior else None
    ret={"games":len(prior),"rest":rest}
    for k in ("points_for","points_against","margin","win","epa_off",
              "epa_def","epa_pass","epa_rush","success","explosive_pass",
              "explosive_rush","pressure","drive_yards","pass_rate",
              "epa_off_adj","epa_def_adj"):
        ret[k]=weighted(prior,k)
    ret["epa_coverage"]=sum(x.get("epa_off") is not None for x in prior[-6:])/max(1,min(6,len(prior)))
    return ret

def difference(a,b,field):
    return None if a.get(field) is None or b.get(field) is None else a[field]-b[field]

def matchup(g,home,away):
    def delta(name):
        return difference(home,away,name)
    def two(a,fa,b,fb):
        return None if a.get(fa) is None or b.get(fb) is None else a[fa]-b[fb]
    margin=delta("margin")
    totals=[x["points_for"]+x["points_against"] for x in (home,away)
            if x["points_for"] is not None and x["points_against"] is not None]
    return {
      "score_margin_form":margin,
      "scoring_total_form":sum(totals)/2 if len(totals)==2 else None,
      "win_rate_form":delta("win"),
      "rest_days_diff":delta("rest"),
      "neutral_site":int(str(g["neutral"]).strip().lower()=="true"),
      "off_epa_matchup":two(home,"epa_off_adj",away,"epa_def_adj"),
      "def_epa_matchup":two(away,"epa_off_adj",home,"epa_def_adj"),
      "pass_epa_form":delta("epa_pass"),
      "rush_epa_form":delta("epa_rush"),
      "success_form":delta("success"),
      "explosive_pass_form":delta("explosive_pass"),
      "explosive_rush_form":delta("explosive_rush"),
      "pressure_form":delta("pressure"),
      "drive_yards_form":delta("drive_yards"),
      "pass_rate_form":delta("pass_rate"),
      "epa_coverage_form":delta("epa_coverage")
    }

def build_weekly_games(games,advanced):
    histories=defaultdict(list);output=[]
    for kickoff,group in group_by_date(games):
        # All same-date matchups use yesterday's history, regardless of kickoff.
        pending=[]
        for g in group:
            home=summarize(histories[g["home"]],kickoff)
            away=summarize(histories[g["away"]],kickoff)
            features=matchup(g,home,away)
            row={"game_id":g["game_id"],"date":g["date"],
                 "kickoff_utc":g["kickoff_utc"],"home":g["home"],"away":g["away"],
                 "home_score":int(g["home_score"]),"away_score":int(g["away_score"]),
                 "home_games_prior":home["games"],"away_games_prior":away["games"],
                 "advanced_row_available":g["game_id"] in advanced,
                 "feature_evidence_status":"RETROSPECTIVE_NOT_PUBLICATION_VERIFIED",
                 "betting_status":"PASS_UNVALIDATED",**features}
            output.append(row)
            pending.append(g)
        # Opponent adjustment for a past game's EPA uses each opponent's
        # defense/offense observed BEFORE that game; no current-game stats.
        pregame={team:summarize(histories[team],kickoff)
                 for g in pending for team in (g["home"],g["away"])}
        for g in pending:
            for team,opp in ((g["home"],g["away"]),(g["away"],g["home"])):
                r=game_stats(g,team,advanced)
                other=pregame[opp]
                r["epa_off_adj"]=(r["epa_off"]-other["epa_def"]
                    if r.get("epa_off") is not None and other["epa_def"] is not None else None)
                r["epa_def_adj"]=(r["epa_def"]-other["epa_off"]
                    if r.get("epa_def") is not None and other["epa_off"] is not None else None)
                histories[team].append(r)
    return output

def group_by_date(games):
    groups=defaultdict(list)
    for g in games:groups[timestamp(g["kickoff_utc"]).date()].append(g)
    for day in sorted(groups):yield timestamp(day.isoformat()+"T00:00:00Z"),groups[day]

def matrix(rows,fields,means=None,stds=None):
    values=np.asarray([[float(r[f]) if r.get(f) is not None else np.nan for f in fields]
                       for r in rows],dtype=float)
    if means is None:
        means=np.asarray([float(np.nanmean(col)) if np.isfinite(col).any() else 0.
                          for col in values.T])
        stds=np.asarray([float(np.std(np.where(np.isfinite(col),col,means[i])))
                         for i,col in enumerate(values.T)])
        stds=np.where(stds<1e-7,1.,stds)
    clean=np.where(np.isfinite(values),values,means)
    return (clean-means)/stds,means,stds

def fit_ridge(rows,fields,penalty=45.):
    x,means,stds=matrix(rows,fields)
    x=np.column_stack([np.ones(len(x)),x])
    target=np.asarray([[r["home_score"]-r["away_score"],
                        r["home_score"]+r["away_score"]] for r in rows],dtype=float)
    reg=np.eye(x.shape[1])*penalty;reg[0,0]=0
    beta=np.linalg.solve(x.T@x+reg,x.T@target)
    resid=target-x@beta
    sigma=float(max(7.,np.sqrt(np.mean(resid[:,0]**2))))
    return beta,means,stds,sigma

def predict(rows,fields,params):
    beta,means,stds,sigma=params
    x,_,_=matrix(rows,fields,means,stds)
    y=np.column_stack([np.ones(len(x)),x])@beta
    return y,sigma

def validate(rows,start_date="2026-09-26",days=7,min_training=90):
    if not rows:raise ValueError("No football games to test")
    begin=dt.date.fromisoformat(start_date);latest=max(dt.date.fromisoformat(r["date"]) for r in rows)
    results=[];details=[]
    for week in range(30):
        first=begin+dt.timedelta(days=days*week)
        end=first+dt.timedelta(days=days)
        train=[r for r in rows if dt.date.fromisoformat(r["date"])<first and
               r["home_games_prior"]>=1 and r["away_games_prior"]>=1]
        test=[r for r in rows if first<=dt.date.fromisoformat(r["date"])<end and
              r["home_games_prior"]>=1 and r["away_games_prior"]>=1]
        if first>latest:break
        if len(train)<min_training or not test:continue
        fold={"train_before":first.isoformat(),"test_until_exclusive":end.isoformat(),
              "train_games":len(train),"test_games":len(test)}
        pred={}
        for name,cols in (("score_only",SCORE),("v03_advanced",FEATURES),
                          ("v03_no_opponent_adjustment",[x for x in FEATURES
                            if x not in ("off_epa_matchup","def_epa_matchup")])):
            params=fit_ridge(train,cols)
            scores,sigma=predict(test,cols,params)
            stats={"count":0,"su_correct":0,"su_graded":0,"margin_abs":0.,
                   "total_abs":0.,"brier_sum":0.}
            for game,row in zip(test,scores):
                margin=float(np.clip(row[0],-55,55))
                total=float(np.clip(row[1],0,110))
                actual=game["home_score"]-game["away_score"]
                stats["margin_abs"]+=abs(margin-actual)
                stats["total_abs"]+=abs(total-game["home_score"]-game["away_score"])
                stats["count"]+=1
                if actual!=0:
                    probability=0.5*(1+math.erf(margin/(sigma*math.sqrt(2))))
                    stats["su_correct"]+=int((margin>0)==(actual>0))
                    stats["su_graded"]+=1
                    stats["brier_sum"]+=(probability-int(actual>0))**2
                if name=="v03_advanced":
                    details.append({"game_id":game["game_id"],"kickoff_utc":game["kickoff_utc"],
                                    "pred_margin":round(margin,2),
                                    "pred_total":round(total,2),
                                    "actual_margin":actual,
                                    "result_labels_only":True})
            pred[name]={"games":stats["count"],"su_accuracy":
                round(stats["su_correct"]/stats["su_graded"],4) if stats["su_graded"] else None,
                "margin_mae":round(stats["margin_abs"]/stats["count"],3),
                "total_mae":round(stats["total_abs"]/stats["count"],3),
                "su_brier":round(stats["brier_sum"]/stats["su_graded"],5)
                    if stats["su_graded"] else None}
        fold["models"]=pred
        results.append(fold)
    return results,details

def run(games_path,advanced_path,manifest_path,output,start_date="2026-09-26"):
    games,advanced,manifest=load_inputs(games_path,advanced_path,manifest_path)
    features=build_weekly_games(games,advanced)
    folds,details=validate(features,start_date=start_date)
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    # Export pregame inputs and postgame outcomes as SEPARATE artifacts.
    # Internal training receives score labels but the feature CSV never does.
    base=["game_id","date","kickoff_utc","home","away",
          "home_games_prior","away_games_prior",
          "advanced_row_available","feature_evidence_status","betting_status"]
    with (out/"weekly_pregame_features.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=base+FEATURES,extrasaction="ignore")
        writer.writeheader();writer.writerows(features)
    with (out/"weekly_postgame_labels.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=[
            "game_id","date","kickoff_utc","home_score","away_score"])
        writer.writeheader()
        writer.writerows({k:r[k] for k in writer.fieldnames} for r in features)
    summary={"status":"RETROSPECTIVE_RESEARCH_ONLY","season":2026,
        "model_version":"v0.3-candidate","betting_status":"PASS_UNVALIDATED",
        "safe_for_betting":False,
        "historical_pregame_source_provenance_verified":False,
        "advanced_release_retrieved_at_utc":manifest["retrieved_at_utc"],
        "advanced_release_source_checksums":{k:v.get("sha256") for k,v in manifest["sources"].items()},
        "games_total":len(games),"advanced_games_two_sided":len(advanced),
        "rows_built":len(features),"weekly_folds":folds,
        "notes":["EPA release retrieved retrospectively; earlier point-in-time versions unavailable.",
                 "Score labels were excluded from per-game feature vector.",
                 "Out-of-sample in chronology of GAMES only, not authenticated release history.",
                 "No sportsbook history: ATS/O-U bet grading and EV unavailable.",
                 "No trained QB/injury/weather effects. Do not use for picks."]}
    (out/"research_backtest.json").write_text(json.dumps(summary,indent=2)+"\n")
    (out/"heldout_research_predictions.json").write_text(json.dumps(details,indent=2)+"\n")
    print(json.dumps({"status":summary["status"],"games":len(games),
                      "advanced_games":len(advanced),"folds":len(folds),
                      "betting_status":summary["betting_status"]},indent=2))
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True);p.add_argument("--advanced",required=True)
    p.add_argument("--manifest",required=True);p.add_argument("--output",required=True)
    p.add_argument("--start-date",default="2026-09-26")
    a=p.parse_args()
    run(a.games,a.advanced,a.manifest,a.output,a.start_date)

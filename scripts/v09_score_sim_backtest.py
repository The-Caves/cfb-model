"""Frozen 2026 V04 Monte Carlo, strict earlier-result score backtest.

This is an empirical paired SCORE residual simulation, not the audited drive
or play-by-play simulator. No current team profiles are copied into prior weeks.
All model scores must have actually been published before scheduled kickoff.
"""
import argparse,datetime as dt,hashlib,json,math,random
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.game_context import parse_time
from scripts.site_history import _load,_digest,ARCHIVE_STATUS,FINAL_STATUS

STATUS="V09_ARCHIVED_V04_SCORE_MONTE_CARLO_WALKFORWARD_RESEARCH"
ET=ZoneInfo("America/New_York")
def numeric(x):return type(x) in (int,float) and math.isfinite(x)

def v04(row):
    keys=["v04_direct_home_points","v04_direct_away_points",
          "v04_direct_home_margin","v04_direct_total_points"]
    if not (row.get("home_bias_quarantined") is True and
            row.get("v04_research_not_promoted") is True and
            row.get("v04_direct_source_no_v03_total_reuse") is True and
            all(numeric(row.get(k)) for k in keys)):return False
    h,a,m,t=[row[k] for k in keys]
    return (min(h,a,t)>=0 and max(h,a)<150 and abs(h-a-m)<.05 and abs(h+a-t)<.05)

def read_frozen(root,now):
    root=Path(root);now=parse_time(now)
    index=json.loads((root/"research_2026/site_board_snapshots/index.json").read_text())
    outcome=json.loads((root/"research_2026/outcome_index.json").read_text())
    if (index.get("status")!=ARCHIVE_STATUS or index.get("schema_version")!=1
        or not isinstance(index.get("runs"),list) or
        outcome.get("status")!=FINAL_STATUS or outcome.get("season")!=2026
        or outcome.get("safe_for_betting") is not False or
        not isinstance(outcome.get("games"),dict)):
        raise ValueError("Untrusted pregame forecast or independent final archive")
    selected={};inspected=0
    for run in sorted(index["runs"],key=lambda x:x["capture_utc"]):
        cap=parse_time(run["capture_utc"])
        if cap>now:continue
        snap=_load(root,run["path"])
        if _digest(snap)!=run["sha256"]:raise ValueError("Frozen pregame digest mismatch")
        if (snap.get("status")!=ARCHIVE_STATUS or snap.get("betting_status")!="PASS_UNVALIDATED"
            or snap.get("capture_utc")!=run["capture_utc"]
            or str(snap.get("dashboard_run_id"))!=str(run["run_id"])):
            raise ValueError("Invalid original snapshot or capture clock")
        inspected+=1
        for row in snap.get("rows",[]):
            gid=str(row.get("game_id",""))
            issued=row.get("frozen_forecast_observed_utc")
            if not gid or gid in selected or not v04(row) or not issued:continue
            kickoff=parse_time(row["kickoff_utc"])
            if not parse_time(issued)<=cap<kickoff or row["home"]==row["away"]:continue
            spread=total=provider=market_time=None
            if row.get("market_provider") and row.get("market_observed_utc"):
                m=parse_time(row["market_observed_utc"])
                if m<=cap and m<kickoff:
                    x=row.get("market_home_spread");y=row.get("market_total")
                    spread=float(x) if numeric(x) and abs(x)<80 else None
                    total=float(y) if numeric(y) and 0<y<150 else None
                    if spread is not None or total is not None:
                        provider=row["market_provider"];market_time=row["market_observed_utc"]
            selected[gid]={"game_id":gid,"home":row["home"],"away":row["away"],
                "kickoff_utc":row["kickoff_utc"],"forecast_utc":issued,
                "capture_utc":run["capture_utc"],"source_run":str(run["run_id"]),
                "snapshot_sha256":run["sha256"],
                "home_points":float(row["v04_direct_home_points"]),
                "away_points":float(row["v04_direct_away_points"]),
                "market":{"home_spread":spread,"total":total,
                          "provider":provider,"observed_at_utc":market_time},
                "frozen_ats_policy":row.get("v04_research_ats_side"),
                "frozen_ou_policy":row.get("v04_research_ou_side")}
    records=[]
    for gid,game in selected.items():
        final=outcome["games"].get(gid)
        if not final:continue
        kickoff=parse_time(game["kickoff_utc"])
        if (str(final.get("game_id"))!=gid or
            final.get("home")!=game["home"] or final.get("away")!=game["away"]
            or abs((parse_time(final["kickoff_utc"])-kickoff).total_seconds())>900
            or not kickoff<parse_time(final["outcome_known_at_utc"])<=now
            or not all(type(final.get(k)) is int and 0<=final[k]<=200 for k in
                       ("home_score","away_score"))):continue
        game["final_home"]=final["home_score"]
        game["final_away"]=final["away_score"]
        game["result_known_utc"]=final["outcome_known_at_utc"]
        game["result_sha256"]=final.get("record_sha256")
        records.append(game)
    records.sort(key=lambda g:(g["kickoff_utc"],g["game_id"]))
    return records,{"snapshot_runs_verified":inspected,
                    "v04_games_before_kickoff":len(selected),
                    "independently_settled_v04_games":len(records)}

def bias(train,game,variant):
    if variant=="uncorrected":return (0.,0.)
    n=len(train)
    mh=sum(x["final_home"]-x["home_points"] for x in train)/n
    ma=sum(x["final_away"]-x["away_points"] for x in train)/n
    shift=[max(-4.,min(4.,x*n/(n+80))) for x in (mh,ma)]
    if variant=="global":return tuple(shift)
    if variant!="team_form":raise ValueError("Invalid simulation variant")
    def past_team_error(name,offense):
        hist=[]
        for x in train:
            if name==x["home"]:
                err=(x["final_home"]-x["home_points"]) if offense else (x["final_away"]-x["away_points"])
            elif name==x["away"]:
                err=(x["final_away"]-x["away_points"]) if offense else (x["final_home"]-x["home_points"])
            else:continue
            hist.append(err)
        if len(hist)<3:return 0.
        recent=hist[-6:]
        return max(-3.,min(3.,(sum(recent)/len(recent)-(mh+ma)/2)*len(hist)/(len(hist)+12)))
    shift[0]+=(past_team_error(game["home"],True)+past_team_error(game["away"],False))/2
    shift[1]+=(past_team_error(game["away"],True)+past_team_error(game["home"],False))/2
    return tuple(max(-7.,min(7.,x)) for x in shift)

def simulate(game,train,variant,trials=1200):
    at=parse_time(game["forecast_utc"])
    if not train or type(trials) is not int or not 100<=trials<=10000:
        raise ValueError("Missing earlier errors or invalid trials")
    if any(x["game_id"]==game["game_id"] or
           parse_time(x["result_known_utc"])>at or
           parse_time(x["kickoff_utc"])>=parse_time(game["kickoff_utc"])
           for x in train):
        raise ValueError("Future result leakage")
    errors=[(x["final_home"]-x["home_points"],x["final_away"]-x["away_points"]) for x in train]
    center_h=sum(a for a,b in errors)/len(errors)
    center_a=sum(b for a,b in errors)/len(errors)
    bh,ba=bias(train,game,variant)
    seed=int(hashlib.sha256((game["game_id"]+"|"+variant+"|v09").encode()).hexdigest()[:16],16)
    rng=random.Random(seed)
    margins=[];totals=[];sh=sa=win=cover=over=0
    spread=game["market"]["home_spread"];line=game["market"]["total"]
    for _ in range(trials):
        x,y=errors[rng.randrange(len(errors))]
        home=max(0.,game["home_points"]+bh+x-center_h)
        away=max(0.,game["away_points"]+ba+y-center_a)
        sh+=home;sa+=away
        m=home-away;t=home+away
        margins.append(m);totals.append(t)
        win+=m>0
        if spread is not None:cover+=m+spread>0
        if line is not None:over+=t>line
    margins.sort();totals.sort()
    hp=sh/trials;ap=sa/trials
    quant=lambda xs:[round(xs[int((trials-1)*p)],2) for p in (.05,.5,.95)]
    return {"variant":variant,"trials":trials,"training_games":len(train),
            "home_points":round(hp,3),"away_points":round(ap,3),
            "margin":round(hp-ap,3),"total":round(hp+ap,3),
            "home_win_probability":round(win/trials,5),
            "home_cover_probability":round(cover/trials,5) if spread is not None else None,
            "over_probability":round(over/trials,5) if line is not None else None,
            "margin_p05_p50_p95":quant(margins),"total_p05_p50_p95":quant(totals),
            "home_bias_adjustment":round(bh,3),"away_bias_adjustment":round(ba,3),
            "model_promoted":False,"calibration_verified":False}

def _pick(x):return "HOME" if x>0 else "AWAY" if x<0 else "PASS"
def _grade(selection,actual):
    return int(selection==actual) if selection not in (None,"PASS") and actual!="PUSH" else None
def _rate(values):
    x=[n for n in values if n is not None]
    return {"graded":len(x),"wins":sum(x),"losses":len(x)-sum(x),
            "win_rate":round(sum(x)/len(x),4) if x else None}
def grade(rows,version):
    md=[];td=[];su=[];ats=[];ou=[];brier=[]
    for g in rows:
        p=g["v04"] if version=="v04" else g["variants"][version]
        actual_margin=g["final_home"]-g["final_away"]
        actual_total=g["final_home"]+g["final_away"]
        md.append(abs(p["margin"]-actual_margin))
        td.append(abs(p["total"]-actual_total))
        su.append(_grade(_pick(p["margin"]),_pick(actual_margin).replace("PASS","PUSH")))
        spread=g["market"]["home_spread"];line=g["market"]["total"]
        ats.append(_grade(_pick(p["margin"]+spread),
                          _pick(actual_margin+spread).replace("PASS","PUSH")) if spread is not None else None)
        ou.append(_grade("OVER" if p["total"]>line else "UNDER" if p["total"]<line else "PASS",
                         "OVER" if actual_total>line else "UNDER" if actual_total<line else "PUSH") if line is not None else None)
        if version!="v04" and actual_margin:
            brier.append((p["home_win_probability"]-int(actual_margin>0))**2)
    return {"games":len(rows),"margin_mae":round(sum(md)/len(md),4) if md else None,
            "total_mae":round(sum(td)/len(td),4) if td else None,
            "winner":_rate(su),"ats":_rate(ats),"over_under":_rate(ou),
            "home_win_brier":round(sum(brier)/len(brier),5) if brier else None}

def evaluate(games,now,min_train=24,trials=1200):
    if type(min_train) is not int or not 2<=min_train<=200:
        raise ValueError("Invalid earlier sample minimum")
    ordered=sorted(games,key=lambda x:(x["kickoff_utc"],x["game_id"]))
    tested=[];skipped=defaultdict(int)
    for g in ordered:
        cutoff=parse_time(g["forecast_utc"])
        past=[x for x in ordered if x["game_id"]!=g["game_id"] and
              parse_time(x["result_known_utc"])<=cutoff and
              parse_time(x["kickoff_utc"])<parse_time(g["kickoff_utc"])]
        if len(past)<min_train:
            skipped["insufficient_earlier_settled_v04_residuals"]+=1;continue
        if len({parse_time(x["kickoff_utc"]).astimezone(ET).date() for x in past})<2:
            skipped["only_one_past_football_date"]+=1;continue
        r={key:g[key] for key in ("game_id","home","away","kickoff_utc",
          "forecast_utc","capture_utc","source_run","snapshot_sha256",
          "result_sha256","result_known_utc","final_home","final_away","market")}
        r["v04"]={"home_points":g["home_points"],"away_points":g["away_points"],
                  "margin":g["home_points"]-g["away_points"],
                  "total":g["home_points"]+g["away_points"]}
        r["variants"]={v:simulate(g,past,v,trials) for v in
                       ("uncorrected","global","team_form")}
        tested.append(r)
    versions=("v04","uncorrected","global","team_form")
    weeks={}
    for wk in sorted({parse_time(x["kickoff_utc"]).astimezone(ET).strftime("%G-W%V") for x in tested}):
        match=[x for x in tested if parse_time(x["kickoff_utc"]).astimezone(ET).strftime("%G-W%V")==wk]
        weeks[wk]={"games":len(match),"metrics":{v:grade(match,v) for v in versions}}
    return {"status":STATUS,"season":2026,"evaluation_utc":parse_time(now).isoformat(),
            "model_promoted":False,"safe_for_betting":False,
            "betting_status":"PASS_UNVALIDATED",
            "simulation_type":"PAIRED_HISTORICAL_SCORE_RESIDUALS_NOT_DRIVE_SIMULATION",
            "matched_original_pre_kickoff_v04":True,
            "historical_source_publication_not_fully_authenticated":True,
            "historical_market_not_verified_closing_line":True,
            "minimum_prior_settled_games":min_train,"trials_per_variant":trials,
            "eligible_games":len(tested),"skipped":dict(skipped),
            "metrics":{v:grade(tested,v) for v in versions},"weeks":weeks,"games":tested,
            "promotion_eligible":False,
            "limits":[
                "Only immutable pre-kickoff saved V04 score receipts, never current team profiles.",
                "Earlier independent final-settlement clocks define the calibration training set.",
                "Historical raw 2026 source publication times are not fully authenticated.",
                "This is a score distribution, not the existing drive-level simulation engine.",
                "No unknown odds are imputed; win rates do not establish profitability.",
                "No model promotion without additional independent future football dates."
            ]}

def run(root,output,now=None,min_train=24,trials=1200):
    at=parse_time(now or dt.datetime.now(dt.timezone.utc).isoformat())
    games,source=read_frozen(root,at)
    report=evaluate(games,at,min_train,trials)
    report["archive_coverage"]=source
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:report[k] for k in ("status","archive_coverage",
          "eligible_games","skipped","metrics","weeks","promotion_eligible")},sort_keys=True))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--min-train",type=int,default=24)
    p.add_argument("--trials",type=int,default=1200)
    a=p.parse_args()
    run(a.archive_root,a.output,min_train=a.min_train,trials=a.trials)

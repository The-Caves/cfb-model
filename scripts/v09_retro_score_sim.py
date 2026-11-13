"""V09 retrospective score Monte Carlo, with strict earlier-week training.

Rebuilds 2026 V04 predictions chronologically via v04_score_benchmark; game
source publication times are NOT historically authenticated. Compared against
authentic archived pre-kickoff sportsbook quotes when available. Research only.
"""
import argparse,csv,datetime as dt,hashlib,json,math,random
from collections import defaultdict
from pathlib import Path
from scripts.game_context import parse_time
from scripts.site_history import _load,_digest,ARCHIVE_STATUS

STATUS="V09_RETROSPECTIVE_WEEKLY_V04_SCORE_SIM_RESEARCH_ONLY"
VERSIONS=("v04","bootstrap","global","team_form")
def number(v):return type(v) in (float,int) and math.isfinite(v)
def choice(x):return "HOME" if x>0 else "AWAY" if x<0 else "PASS"
def grade(p,a):return int(p==a) if p not in (None,"PASS") and a!="PUSH" else None
def binary(v):
    x=[a for a in v if a is not None]
    return {"graded":len(x),"wins":sum(x),"losses":len(x)-sum(x),
            "win_rate":round(sum(x)/len(x),4) if x else None}

def archived_markets(root,games,now):
    if not root:return {}
    root=Path(root)
    index=json.loads((root/"research_2026/site_board_snapshots/index.json").read_text())
    if index.get("status")!=ARCHIVE_STATUS or index.get("schema_version")!=1:
        raise ValueError("Untrusted saved market index")
    quotes={}
    for ref in sorted(index["runs"],key=lambda a:a["capture_utc"]):
        cap=parse_time(ref["capture_utc"])
        if cap>now:continue
        snap=_load(root,ref["path"])
        if (_digest(snap)!=ref["sha256"] or
            snap.get("status")!=ARCHIVE_STATUS or
            snap.get("betting_status")!="PASS_UNVALIDATED" or
            snap.get("capture_utc")!=ref["capture_utc"] or
            str(snap.get("dashboard_run_id"))!=str(ref["run_id"])):
            raise ValueError("Market snapshot provenance failed")
        for r in snap.get("rows",[]):
            gid=str(r.get("game_id",""))
            g=games.get(gid)
            if gid in quotes or not g or not r.get("market_provider") or not r.get("market_observed_utc"):
                continue
            kick=parse_time(g["kickoff_utc"]);observed=parse_time(r["market_observed_utc"])
            if (g["home"]!=r.get("home") or g["away"]!=r.get("away")
                or abs((parse_time(r["kickoff_utc"])-kick).total_seconds())>900
                or not observed<=cap<kick):continue
            sp=r.get("market_home_spread");total=r.get("market_total")
            spread=float(sp) if number(sp) and abs(sp)<80 else None
            line=float(total) if number(total) and 0<total<150 else None
            if spread is None and line is None:continue
            quotes[gid]={"home_spread":spread,"total":line,
                         "provider":r["market_provider"],"observed_at_utc":r["market_observed_utc"],
                         "snapshot_sha256":ref["sha256"],"not_closing_line":True}
    return quotes

def load_rows(benchmark,game_csv,market_root,now):
    doc=json.loads(Path(benchmark).read_text())
    if (doc.get("status")!="V04_DIRECT_SCORE_PAIRED_WALKFORWARD_RESEARCH_ONLY"
        or doc.get("season")!=2026 or doc.get("betting_status")!="PASS_UNVALIDATED"
        or doc.get("safe_for_betting") is not False or
        doc.get("historical_original_pbp_publication_authenticated") is not False
        or not isinstance(doc.get("predictions"),list)):
        raise ValueError("Untrusted V04 reconstructed walk-forward")
    original={g["game_id"]:g for g in csv.DictReader(open(game_csv,encoding="utf-8-sig",newline=""))}
    if len(original)<100:raise ValueError("Insufficient 2026 source games")
    quotes=archived_markets(market_root,original,now)
    rows=[];seen=set()
    for p in doc["predictions"]:
        gid=str(p["game_id"]);g=original.get(gid)
        if not g or gid in seen:raise ValueError("Unmatched or duplicated V04 predicted game")
        seen.add(gid)
        date=dt.date.fromisoformat(g["date"]);cutoff=dt.date.fromisoformat(p["cutoff"])
        if (not cutoff<=date<cutoff+dt.timedelta(days=7)
            or abs(p["actual_margin"]-(int(g["home_score"])-int(g["away_score"])))>.01
            or abs(p["actual_total"]-(int(g["home_score"])+int(g["away_score"])))>.01
            or abs(p["v04_home_points"]-p["v04_away_points"]-p["v04_margin"])>.05
            or abs(p["v04_home_points"]+p["v04_away_points"]-p["v04_total"])>.05):
            raise ValueError("Retrospective score identity or held-out period mismatch")
        rows.append({"game_id":gid,"home":g["home"],"away":g["away"],
          "date":g["date"],"cutoff":p["cutoff"],"kickoff_utc":g["kickoff_utc"],
          "home_points":float(p["v04_home_points"]),
          "away_points":float(p["v04_away_points"]),
          "final_home":int(g["home_score"]),"final_away":int(g["away_score"]),
          "market":quotes.get(gid,{"home_spread":None,"total":None,"provider":None}),
          "v03_margin":float(p["v03_margin"]),"v03_total":float(p["v03_total"])})
    if len(rows)!=doc["matched_games"]:
        raise ValueError("V04 historical benchmark expected more games")
    rows.sort(key=lambda r:(r["cutoff"],r["kickoff_utc"],r["game_id"]))
    return rows,{"benchmark_games":doc["matched_games"],"benchmarked_weeks":doc["n_folds"],
                 "matched_source_observed_pregame_market_quotes":sum(
                    r["market"]["home_spread"] is not None or r["market"]["total"] is not None for r in rows)}

def correction(past,target,variant):
    if variant=="bootstrap":return (0.,0.)
    n=len(past)
    mh=sum(g["final_home"]-g["home_points"] for g in past)/n
    ma=sum(g["final_away"]-g["away_points"] for g in past)/n
    value=[max(-4.,min(4.,m*n/(n+80))) for m in (mh,ma)]
    if variant=="global":return tuple(value)
    if variant!="team_form":raise ValueError("Unknown score variant")
    def team_error(name,offense):
        history=[]
        for g in past:
            if g["home"]==name:
                error=(g["final_home"]-g["home_points"]) if offense else (g["final_away"]-g["away_points"])
            elif g["away"]==name:
                error=(g["final_away"]-g["away_points"]) if offense else (g["final_home"]-g["home_points"])
            else:continue
            history.append(error)
        if len(history)<3:return 0.
        recent=history[-6:]
        return max(-3.,min(3.,(sum(recent)/len(recent)-(mh+ma)/2)*len(history)/(len(history)+12)))
    value[0]+=(team_error(target["home"],True)+team_error(target["away"],False))/2
    value[1]+=(team_error(target["away"],True)+team_error(target["home"],False))/2
    return tuple(max(-7.,min(7.,v)) for v in value)

def simulate(target,past,variant,trials=1200):
    if not past or not 100<=trials<=5000:raise ValueError("Insufficient training or trials")
    if any(g["game_id"]==target["game_id"] or
           g["cutoff"]>=target["cutoff"] or g["date"]>=target["cutoff"] for g in past):
        raise ValueError("Same or later football week leaked into training")
    errors=[(g["final_home"]-g["home_points"],g["final_away"]-g["away_points"]) for g in past]
    mh=sum(v[0] for v in errors)/len(errors);ma=sum(v[1] for v in errors)/len(errors)
    dh,da=correction(past,target,variant)
    rng=random.Random(int(hashlib.sha256((target["game_id"]+variant+"v09").encode()).hexdigest()[:16],16))
    homes=aways=wins=covers=overs=0
    margins=[];totals=[]
    sp=target["market"].get("home_spread");line=target["market"].get("total")
    for _ in range(trials):
        eh,ea=errors[rng.randrange(len(errors))]
        h=max(0.,target["home_points"]+dh+eh-mh)
        a=max(0.,target["away_points"]+da+ea-ma)
        homes+=h;aways+=a
        m=h-a;t=h+a
        margins.append(m);totals.append(t)
        wins+=m>0
        if sp is not None:covers+=m+sp>0
        if line is not None:overs+=t>line
    margins.sort();totals.sort()
    h=homes/trials;a=aways/trials
    qs=lambda arr:[round(arr[int((trials-1)*p)],2) for p in (.05,.5,.95)]
    return {"home_points":round(h,3),"away_points":round(a,3),
            "margin":round(h-a,3),"total":round(h+a,3),
            "home_win_probability":round(wins/trials,5),
            "home_cover_probability":round(covers/trials,5) if sp is not None else None,
            "over_probability":round(overs/trials,5) if line is not None else None,
            "margin_p05_p50_p95":qs(margins),"total_p05_p50_p95":qs(totals),
            "prior_fold_errors":len(past),"home_correction":round(dh,3),
            "away_correction":round(da,3),"model_promoted":False}

def metrics(rows,version):
    md=[];td=[];su=[];ats=[];ou=[];brier=[];market_md=[];market_td=[]
    for g in rows:
        p=g["v04"] if version=="v04" else g["simulations"][version]
        am=g["final_home"]-g["final_away"];at=g["final_home"]+g["final_away"]
        md.append(abs(p["margin"]-am));td.append(abs(p["total"]-at))
        su.append(grade(choice(p["margin"]),choice(am).replace("PASS","PUSH")))
        sp=g["market"].get("home_spread");line=g["market"].get("total")
        ats.append(grade(choice(p["margin"]+sp),choice(am+sp).replace("PASS","PUSH")) if sp is not None else None)
        ou.append(grade("OVER" if p["total"]>line else "UNDER" if p["total"]<line else "PASS",
                        "OVER" if at>line else "UNDER" if at<line else "PUSH") if line is not None else None)
        if sp is not None:market_md.append(abs(-sp-am))
        if line is not None:market_td.append(abs(line-at))
        if version!="v04" and am:brier.append((p["home_win_probability"]-int(am>0))**2)
    return {"games":len(rows),
      "margin_mae":round(sum(md)/len(md),4) if md else None,
      "total_mae":round(sum(td)/len(td),4) if td else None,
      "straight_up":binary(su),"hypothetical_ats":binary(ats),
      "hypothetical_ou":binary(ou),
      "book_spread_mae":round(sum(market_md)/len(market_md),4) if market_md else None,
      "book_total_mae":round(sum(market_td)/len(market_td),4) if market_td else None,
      "home_win_brier":round(sum(brier)/len(brier),5) if brier else None}

def evaluate(games,min_train=35,trials=1200):
    if not 2<=min_train<=200 or not 100<=trials<=5000:raise ValueError("Invalid evaluation settings")
    tested=[];excluded=defaultdict(int)
    for g in games:
        past=[r for r in games if r["cutoff"]<g["cutoff"] and r["date"]<g["cutoff"]]
        if len(past)<min_train:
            excluded["insufficient_previous_weeks"]+=1;continue
        row={k:g[k] for k in ("game_id","home","away","date","cutoff","kickoff_utc",
                                "final_home","final_away","market")}
        row["v04"]={"home_points":g["home_points"],"away_points":g["away_points"],
                    "margin":g["home_points"]-g["away_points"],
                    "total":g["home_points"]+g["away_points"]}
        row["simulations"]={v:simulate(g,past,v,trials)
                            for v in ("bootstrap","global","team_form")}
        tested.append(row)
    weeks={}
    for cutoff in sorted({g["cutoff"] for g in tested}):
        cohort=[r for r in tested if r["cutoff"]==cutoff]
        weeks[cutoff]={"games":len(cohort),"models":{v:metrics(cohort,v)
                     for v in ("v04","bootstrap","global","team_form")}}
    return {"status":STATUS,"season":2026,"betting_status":"PASS_UNVALIDATED",
        "safe_for_betting":False,"model_promoted":False,"promotion_eligible":False,
        "historical_publication_timing_authenticated":False,
        "simulation_type":"PAIRED_PAST_SCORE_RESIDUALS_NOT_DRIVE_SIMULATOR",
        "minimum_past_fold_games":min_train,"trials_per_variant":trials,
        "eligible_games":len(tested),"excluded":dict(excluded),
        "models":{v:metrics(tested,v) for v in ("v04","bootstrap","global","team_form")},
        "weeks":weeks,"games":tested,
        "limitations":["V04 is refitted from earlier 2026 games for each past week, never today's profile.",
          "Source game/PBP publication times at those historic cutoffs are not authenticated.",
          "Residuals for each simulation are drawn only from previous held-out football weeks.",
          "This is NOT full possession simulation; reviewed game-drive history is still missing.",
          "ATS and OU are HYPOTHETICAL directional leans, not authentic PASS-gated V04 bets.",
          "Only genuine archived pregame lines are scored; they are not verified closing odds.",
          "No promotion without independent later games and a sufficient out-of-sample cohort."]}

def run(benchmark,games,market_root,output,min_train=35,trials=1200):
    now=dt.datetime.now(dt.timezone.utc)
    source,coverage=load_rows(benchmark,games,market_root,now)
    result=evaluate(source,min_train,trials)
    result["source_coverage"]=coverage
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:result[k] for k in
          ("status","source_coverage","eligible_games","excluded","models","weeks",
           "promotion_eligible")},sort_keys=True))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--benchmark",required=True)
    p.add_argument("--games",required=True)
    p.add_argument("--market-root")
    p.add_argument("--output",required=True)
    p.add_argument("--min-train",type=int,default=35)
    p.add_argument("--trials",type=int,default=1200)
    args=p.parse_args()
    run(args.benchmark,args.games,args.market_root,args.output,args.min_train,args.trials)

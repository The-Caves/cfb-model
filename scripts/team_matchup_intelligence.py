"""2026 source-audited team-style and opponent matchup intelligence.

Run/pass offense and run/pass defense are distinct: a defense's pass EPA
allowed is the opponent's verified offensive pass EPA IN THE SAME GAME.
Everything is computed from earlier completed Eastern football dates.
Turnovers require separately score-validated ESPN two-sided boxscores.
"Struggles when run stopped" is an observational conditional split, NOT
a causal finding. No synthetic totals/unders or sportsbook prices.
"""
import argparse,csv,datetime as dt,json,math
from collections import defaultdict
from pathlib import Path
from scripts.model_v03 import load_inputs,build_weekly_games,fit_ridge,predict,rate,group_by_date
from scripts.personnel_features import BASE_FIELDS

STATUS="TEAM_OPPONENT_MATCHUP_STYLE_RESEARCH_ONLY"
STYLE_FIELDS=("home_run_edge","away_run_edge","home_pass_edge","away_pass_edge",
              "home_run_success_edge","away_run_success_edge",
              "home_pass_success_edge","away_pass_success_edge",
              "pass_rate_difference","home_explosive_pass_edge","away_explosive_pass_edge",
              "home_rush_disruption_dependency","away_rush_disruption_dependency")
SITUATIONAL_FIELDS=("home_pressure_exposure","away_pressure_exposure",
                    "home_redzone_conversion","away_redzone_conversion",
                    "home_drive_tempo","away_drive_tempo")
TURNOVER_FIELDS=("home_giveaway_minus_away_takeaway","away_giveaway_minus_home_takeaway")
MIN_QB_MATCHUP_SAMPLE_GAMES=2
def mean(values):
    xs=[float(x) for x in values if x is not None and math.isfinite(float(x))]
    return sum(xs)/len(xs) if xs else None
def diff(a,b):
    return a-b if a is not None and b is not None else None
def _team_game(g,team,advanced,turnover=None):
    other=g["away"] if team==g["home"] else g["home"]
    grouped=advanced.get(str(g["game_id"]),{})
    offense=grouped.get(team,{})
    opponent=grouped.get(other,{})
    def pct(a,n,d):return rate(a,n,d) if a else None
    player_turnover=turnover.get((str(g["game_id"]),team)) if turnover else None
    return {"game_id":str(g["game_id"]),"date":g["date"],"team":team,
      "opponent":other,"points":int(g["home_score"] if team==g["home"] else g["away_score"]),
      "margin":int(g["home_score"])-int(g["away_score"]) if team==g["home"] else
                   int(g["away_score"])-int(g["home_score"]),
      "run_off":pct(offense,"rush_epa_sum","rush_epa_plays"),
      "pass_off":pct(offense,"pass_epa_sum","pass_epa_plays"),
      "run_def_allowed":pct(opponent,"rush_epa_sum","rush_epa_plays"),
      "pass_def_allowed":pct(opponent,"pass_epa_sum","pass_epa_plays"),
      "run_success_off":pct(offense,"rush_success_count","rush_success_plays"),
      "pass_success_off":pct(offense,"pass_success_count","pass_success_plays"),
      "run_success_allowed":pct(opponent,"rush_success_count","rush_success_plays"),
      "pass_success_allowed":pct(opponent,"pass_success_count","pass_success_plays"),
      "pass_rate":pct(offense,"pass_plays","scrimmage_plays"),
      "run_explosive_off":pct(offense,"explosive_rush","rush_plays"),
      "pass_explosive_off":pct(offense,"explosive_pass","pass_plays"),
      "pass_explosive_allowed":pct(opponent,"explosive_pass","pass_plays"),
      "pressure_allowed":pct(offense,"pressure_count","pressure_observed"),
      "pressure_generated":pct(opponent,"pressure_count","pressure_observed"),
      "redzone_success":pct(offense,"redzone_success","redzone_plays"),
      "drives":float(offense.get("drives") or 0) or None,
      "plays_per_drive":pct(offense,"drive_plays_sum","drives"),
      "turnovers_committed":(player_turnover.get("turnovers_committed")
                             if player_turnover else None),
      "takeaways":(player_turnover.get("takeaways_observed")
                             if player_turnover else None)}
def _profile(hist):
    last=hist[-6:]
    names=("run_off","pass_off","run_def_allowed","pass_def_allowed",
           "run_success_off","pass_success_off","run_success_allowed",
           "pass_success_allowed","pass_rate","run_explosive_off",
           "pass_explosive_off","pass_explosive_allowed",
           "pressure_allowed","pressure_generated","redzone_success",
           "drives","plays_per_drive","turnovers_committed","takeaways")
    result={k:mean(x.get(k) for x in last) for k in names}
    result["prior_games"]=len(hist)
    def count(key):return sum(x.get(key) is not None for x in last)
    result["pass_off_games"]=count("pass_off")
    result["run_off_games"]=count("run_off")
    result["run_def_games"]=count("run_def_allowed")
    result["pass_def_games"]=count("pass_def_allowed")
    result["turnover_verified_games"]=count("turnovers_committed")
    result["run_stopped_games"]=sum(x["run_off"] is not None and x["run_off"]<=0 for x in last)
    result["run_successful_games"]=sum(x["run_off"] is not None and x["run_off"]>0 for x in last)
    # Running stopped means nonpositive EPA, not simply low raw rushing yards.
    stalled=[x["points"] for x in last if x["run_off"] is not None and x["run_off"]<=0]
    productive=[x["points"] for x in last if x["run_off"] is not None and x["run_off"]>0]
    result["points_when_run_stopped"]=mean(stalled) if len(stalled)>=2 else None
    result["points_when_run_effective"]=mean(productive) if len(productive)>=2 else None
    result["run_disruption_dependency"]=diff(result["points_when_run_effective"],
                                             result["points_when_run_stopped"])
    # The same team can be good when run stopped; negative is allowed.
    return result
def matchup(home,away):
    def edge(off,defender,kind):
        return diff(off.get(kind+"_off"),defender.get(kind+"_def_allowed"))
    def success(off,defender,kind):
        return diff(off.get(kind+"_success_off"),defender.get(kind+"_success_allowed"))
    return {
      "home_run_edge":edge(home,away,"run"),"away_run_edge":edge(away,home,"run"),
      "home_pass_edge":edge(home,away,"pass"),"away_pass_edge":edge(away,home,"pass"),
      "home_run_success_edge":success(home,away,"run"),
      "away_run_success_edge":success(away,home,"run"),
      "home_pass_success_edge":success(home,away,"pass"),
      "away_pass_success_edge":success(away,home,"pass"),
      "pass_rate_difference":diff(home["pass_rate"],away["pass_rate"]),
      "home_explosive_pass_edge":diff(home["pass_explosive_off"],away["pass_explosive_allowed"]),
      "away_explosive_pass_edge":diff(away["pass_explosive_off"],home["pass_explosive_allowed"]),
      "home_rush_disruption_dependency":home["run_disruption_dependency"],
      "away_rush_disruption_dependency":away["run_disruption_dependency"],
      "home_pressure_exposure":diff(home["pressure_allowed"],away["pressure_generated"]),
      "away_pressure_exposure":diff(away["pressure_allowed"],home["pressure_generated"]),
      "home_redzone_conversion":home["redzone_success"],
      "away_redzone_conversion":away["redzone_success"],
      "home_drive_tempo":home["plays_per_drive"],
      "away_drive_tempo":away["plays_per_drive"],
      "home_giveaway_minus_away_takeaway":diff(home["turnovers_committed"],away["takeaways"]),
      "away_giveaway_minus_home_takeaway":diff(away["turnovers_committed"],home["takeaways"])}
def validated_turnovers(bundle,scoreboard):
    if bundle is None:return {}
    if (bundle.get("status")!="ESPN_COMPLETED_BOXSCORE_TURNOVERS_RESEARCH_ONLY" or
        bundle.get("season")!=2026 or
        bundle.get("historical_publication_times_verified") is not False
        or bundle.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Untrusted turnover source")
    games={str(g["game_id"]):g for g in scoreboard}
    out={}
    for r in bundle["rows"]:
        gid=str(r["game_id"]);game=games.get(gid)
        if (game is None or r["team"] not in (game["home"],game["away"])
            or r["opponent"]!=(game["away"] if r["team"]==game["home"] else game["home"])
            or r["date"]!=game["date"] or r["betting_status"]!="PASS_UNVALIDATED"):
            raise ValueError("Turnover record belongs to wrong team/game")
        key=(gid,r["team"])
        if key in out:raise ValueError("Duplicate opponent turnover")
        for field in ("turnovers_committed","takeaways_observed"):
            if type(r[field]) is not int or not 0<=r[field]<=15:
                raise ValueError("Untrusted turnover statistic")
        out[key]=r
    for gid,g in games.items():
        h=out.get((gid,g["home"]));a=out.get((gid,g["away"]))
        if bool(h)!=bool(a):raise ValueError("One-sided turnover data cannot imply no giveaways")
        if h and (h["takeaways_observed"]!=a["turnovers_committed"] or
                  a["takeaways_observed"]!=h["turnovers_committed"]):
            raise ValueError("Two-sided turnover mismatch")
    return out

def augment(games,advanced,turnover=None):
    base={str(r["game_id"]):r for r in build_weekly_games(games,advanced)}
    turnovers=validated_turnovers(turnover,games)
    history=defaultdict(list);snapshots=[]
    for _,group in group_by_date(games):
        for g in group:
            gid=str(g["game_id"])
            h=_profile(history[g["home"]]);a=_profile(history[g["away"]])
            base[gid].update(matchup(h,a))
            snapshots.append({"game_id":gid,"date":g["date"],"home":g["home"],"away":g["away"],
                   "home":h,"away":a})
        # Advance only after the entire football day was evaluated.
        for g in group:
            for team in (g["home"],g["away"]):
                history[team].append(_team_game(g,team,advanced,turnovers))
    return list(base.values())

def build_profile_board(games,advanced,turnover,upcoming,asof):
    cutoff=dt.date.fromisoformat(asof)
    historic=[g for g in games if dt.date.fromisoformat(g["date"])<cutoff]
    if any(dt.date.fromisoformat(g["date"])>=cutoff for g in historic):
        raise ValueError("Future-game source leak")
    turns=validated_turnovers(turnover,games)
    hist=defaultdict(list)
    for g in historic:
        for team in (g["home"],g["away"]):
            hist[team].append(_team_game(g,team,advanced,turns))
    names=sorted(set(hist)|{g[side] for g in upcoming for side in ("home","away")})
    profiles={name:_profile(hist[name]) for name in names}
    matches=[]
    for g in upcoming:
        if dt.datetime.fromisoformat(g["kickoff_utc"].replace("Z","+00:00")).date()<cutoff:
            raise ValueError("Historical matchup in future board")
        home=profiles[g["home"]];away=profiles[g["away"]]
        data=matchup(home,away)
        # TOTALS require both offenses, both defenses, redzone and tempo
        # to be present; no fixed "defensive battle => UNDER" heuristic.
        all_=all(data[k] is not None for k in (
            "home_run_edge","away_run_edge","home_pass_edge","away_pass_edge"))
        matches.append({"game_id":str(g["game_id"]),"home":g["home"],"away":g["away"],
          "kickoff_utc":g["kickoff_utc"],"matchup":data,
          "two_way_run_pass_coverage":all_,
          "both_turnover_records":all(data[k] is not None for k in TURNOVER_FIELDS),
          "total_projection_generated_from_profile":False,
          "betting_status":"PASS_UNVALIDATED"})
    return {"status":STATUS,"season":2026,"cutoff_date_exclusive":asof,
        "historical_publication_authenticated":False,
        "profiles":profiles,"games":matches,
        "summary":{"team_profiles":len(profiles),"games":len(matches),
            "two_way_matchups":sum(r["two_way_run_pass_coverage"] for r in matches),
            "turnover_matchups":sum(r["both_turnover_records"] for r in matches)},
        "model_promoted":False,"safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

VARIANTS={
 "baseline_14":list(BASE_FIELDS),
 "run_pass_vs_defense":list(BASE_FIELDS)+list(STYLE_FIELDS[:8]),
 "run_pass_style_and_dependency":list(BASE_FIELDS)+list(STYLE_FIELDS),
 "situational":list(BASE_FIELDS)+list(SITUATIONAL_FIELDS),
 "turnovers":list(BASE_FIELDS)+list(TURNOVER_FIELDS),
 "all_matchups":list(BASE_FIELDS)+list(STYLE_FIELDS)+list(SITUATIONAL_FIELDS)+list(TURNOVER_FIELDS)}
def evaluate(rows):
    last=max(dt.date.fromisoformat(x["date"]) for x in rows)
    folds=[];out=[]
    for n in range(25):
        begin=dt.date(2026,9,26)+dt.timedelta(days=7*n)
        if begin>last:break
        training=[r for r in rows if dt.date.fromisoformat(r["date"])<begin
                  and min(r["home_games_prior"],r["away_games_prior"])>=1]
        held=[r for r in rows if begin<=dt.date.fromisoformat(r["date"])<begin+dt.timedelta(days=7)
                and min(r["home_games_prior"],r["away_games_prior"])>=1]
        if len(training)<90 or not held:continue
        fold={"cutoff":begin.isoformat(),"training":len(training),"held":len(held),"models":{}}
        for name,fields in VARIANTS.items():
            predictions,_=predict(held,fields,fit_ridge(training,fields))
            values=[]
            for r,p in zip(held,predictions):
                margin=max(-55.,min(55.,float(p[0])))
                total=max(0.,min(110.,float(p[1])))
                values.append({"id":str(r["game_id"]),"margin_error":abs(margin-(r["home_score"]-r["away_score"])),
                       "total_error":abs(total-(r["home_score"]+r["away_score"])),
                       "home_bias":margin-(r["home_score"]-r["away_score"]),
                       "winner":int((margin>0)==(r["home_score"]>r["away_score"])),
                       "margin":round(margin,4),"total":round(total,4)})
            out.extend([{"model":name,"fold":begin.isoformat(),**v} for v in values])
            fold["models"][name]={"games":len(values),
                 "margin_mae":round(mean(v["margin_error"] for v in values),5),
                 "total_mae":round(mean(v["total_error"] for v in values),5),
                 "signed_home_bias":round(mean(v["home_bias"] for v in values),5),
                 "su_accuracy":round(mean(v["winner"] for v in values),5)}
        folds.append(fold)
    summary={}
    for name in VARIANTS:
        data=[r for r in out if r["model"]==name]
        if not data:continue
        summary[name]={"games":len(data),
            "margin_mae":round(mean(x["margin_error"] for x in data),5),
            "total_mae":round(mean(x["total_error"] for x in data),5),
            "signed_home_bias":round(mean(x["home_bias"] for x in data),5),
            "su_accuracy":round(mean(x["winner"] for x in data),5)}
    return {"status":STATUS,"season":2026,"folds":folds,"aggregate":summary,
        "predictions":out,"model_promoted":False,
        "historical_publication_authenticated":False,
        "betting_status":"PASS_UNVALIDATED"}

def run(games_csv,advanced_csv,manifest,turnover_json,context_json,out):
    games,advanced,_=load_inputs(games_csv,advanced_csv,manifest)
    turns=json.loads(Path(turnover_json).read_text()) if turnover_json else None
    context=json.loads(Path(context_json).read_text())
    cutoff=dt.datetime.fromisoformat(context["asof_utc"].replace("Z","+00:00")).date().isoformat()
    board=build_profile_board(games,advanced,turns,context["games"],cutoff)
    output=Path(out);output.mkdir(parents=True,exist_ok=True)
    (output/"team_profiles_and_matchups.json").write_text(
        json.dumps(board,indent=2,allow_nan=False)+"\n")
    result=evaluate(augment(games,advanced,turns))
    (output/"walkforward_matchup_ablation.json").write_text(
        json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":STATUS,"coverage":board["summary"],
        "folds":len(result["folds"]),"models":result["aggregate"],
        "model_promoted":False}))
    return board,result
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("games","advanced","manifest","context","output"):p.add_argument("--"+x,required=True)
    p.add_argument("--turnovers")
    a=p.parse_args();run(a.games,a.advanced,a.manifest,a.turnovers,a.context,a.output)

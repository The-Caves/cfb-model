"""Immutable, time-signed snapshots of exactly displayed model picks and market lines.

Site observations are not the same as synchronized forecast/market decision
snapshots. They can be graded prospectively but must NEVER be treated as
prices observed when the older frozen model originally ran.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
from scripts import context_archive as store
from scripts.game_context import parse_time
from scripts.v04_market_challenger import decide as v04_decide
from scripts.site_depthchart import select_pregame_qb, allowed as depth_url_allowed
from scripts.v05_robust_scores import MODEL as V05_MODEL, STATUS as V05_STATUS
from scripts.personnel_results_archive import _commit_material

ROOT="research_2026/site_board_snapshots"
INDEX=ROOT+"/index.json"
STATUS="IMMUTABLE_DISPLAYED_RESEARCH_MARKET_SNAPSHOT"
VALID_SIDES={"HOME","AWAY","PASS"}
VALID_TOTALS={"OVER","UNDER","PASS"}

def finite(x):
    return type(x) in (int,float) and math.isfinite(x)

def freeze(board,now,run_id):
    if (board.get("schema_version")!=2 or board.get("betting_status")!="PASS_UNVALIDATED"
        or not isinstance(board.get("games"),list) or
        not isinstance(board.get("forecast_sha256"),str)
        or len(board["forecast_sha256"])!=64
        or not isinstance(board.get("model"),str) or not board["model"].strip()
        or not str(run_id).isdigit()):
        raise ValueError("Invalid published research snapshot/identity")
    orig=parse_time(board["forecast_observed_utc"])
    if orig>now:raise ValueError("Forecast from future")
    # External odds timestamps are preserved separately from model timestamps.
    rows=[];ids=set();quote_count=0;ats=0;ou=0;high_disagreement=0
    for g in board["games"]:
        gid=str(g["game_id"])
        kickoff=parse_time(g["kickoff_utc"])
        if gid in ids:raise ValueError("Duplicate game ID")
        ids.add(gid)
        if kickoff<=now:continue  # never create a post-kickoff prospectively graded pick
        if orig>=kickoff:raise ValueError("Prediction after scheduled kickoff")
        home=g["home_team"];away=g["away_team"]
        margin=g["model_home_margin"];total=g["model_total"]
        if (not home or not away or not finite(margin) or not finite(total)
                or margin<=-150 or margin>=150 or not 0<=total<=160):
            raise ValueError("Invalid frozen model output")
        spread=g.get("market_home_spread")
        market_total=g.get("market_total")
        sp=spread is not None
        tt=market_total is not None
        if sp and (not finite(spread) or abs(spread)>=80):raise ValueError("Bad home spread")
        if tt and (not finite(market_total) or market_total<=0 or market_total>=150):
            raise ValueError("Bad market total")
        provider=g.get("market_provider")
        market_observed=g.get("market_observed_utc")
        home_ml=g.get("market_home_moneyline")
        away_ml=g.get("market_away_moneyline")
        ml=home_ml is not None or away_ml is not None
        if ml and not (type(home_ml) is int and type(away_ml) is int and
                       100<=abs(home_ml)<=10000 and 100<=abs(away_ml)<=10000):
            raise ValueError("Bad or incomplete source-provided moneyline")
        if sp or tt or ml:
            if not provider or not market_observed:
                raise ValueError("Unsourced displayed odds")
            observed=parse_time(market_observed)
            if observed>now or observed>=kickoff:
                raise ValueError("Market line collected in future or after kickoff")
            quote_count+=1
        elif provider or market_observed:
            raise ValueError("Provider/clock without a displayed market line")
        side=g.get("model_ats_side")
        over=g.get("model_ou_side")
        if side is not None:
            expected=("PASS" if g.get("home_bias_quarantined") is True else
                      "HOME" if margin+spread>0 else
                      "AWAY" if margin+spread<0 else "PASS")
            if not sp or side not in VALID_SIDES or side!=expected:
                raise ValueError("Displayed ATS selection changed or no source")
            if side!="PASS":ats+=1
        elif sp:
            raise ValueError("Observed ATS line without computed side")
        if over is not None:
            expected="OVER" if total>market_total else "UNDER" if total<market_total else "PASS"
            if not tt or over not in VALID_TOTALS or over!=expected:
                raise ValueError("Displayed totals selection changed or no source")
            if over!="PASS":ou+=1
        elif tt:
            raise ValueError("Observed total without computed side")
        # Preserve the exact expected QB identity shown BEFORE kickoff, so
        # subsequent independently reviewed gamebooks can grade accuracy.
        # Legacy snapshots without this field remain explicitly unobserved.
        qb_identity={}
        for qside in ("home","away"):
            pre=g.get("qb_pregame_"+qside)
            if pre is None:
                qb_identity[qside]=None
                continue
            expected=select_pregame_qb(g,qside,g.get("qb_depth_"+qside) or [])
            if pre!=expected:
                raise ValueError("Published QB selection contradicts source overlay")
            status=pre["status"]
            player=pre["player"]
            source_url=pre["source_url"]
            observed=pre["observed_at_utc"]
            if status in ("CONFIRMED_THIS_GAME","PROJECTED_DEPTH_CHART"):
                if (not isinstance(player,str) or not player or
                    not isinstance(source_url,str) or not source_url.startswith("https://") or
                    not observed or parse_time(observed)>now or
                    parse_time(observed)>=kickoff):
                    raise ValueError("Current QB name lacks pregame source provenance")
                if status=="PROJECTED_DEPTH_CHART" and not depth_url_allowed(source_url):
                    raise ValueError("Projected QB must originate from reviewed depth chart")
            elif status not in ("UNKNOWN","CONFLICT_REVIEW") or player is not None:
                raise ValueError("Unknown QB cannot claim a named active starter")
            qb_identity[qside]={
                "player":player,"status":status,
                "source_url":source_url,"source_observed_at_utc":observed,
                "depth_rank":pre["depth_rank"],
                "game_specific_confirmed":status=="CONFIRMED_THIS_GAME",
                "historical_passer_not_a_starter":True,
                "not_used_to_rewrite_frozen_score":True}
        # Freeze the ACTUALLY DISPLAYED independent V04 research score
        # alongside (never replacing) the original V03 forecast receipts.
        candidate=g.get("v04_direct_scores")
        if candidate is not None:
            if (not isinstance(candidate,dict) or
                candidate.get("status")!="SOURCE_OBSERVED_DIRECT_TEAM_SCORE_MODEL_RESEARCH_ONLY"
                or candidate.get("model")!="V04_INDEPENDENT_OPPONENT_ADJUSTED_SCORES_RESEARCH_ONLY"
                or candidate.get("direct_scoring_fit_uses_v03_total") is not False
                or candidate.get("no_market_lines_in_training") is not True
                or candidate.get("model_promoted") is not False or
                g.get("home_bias_quarantined") is not True):
                raise ValueError("V04 research source/status mismatch")
            home_pts=candidate.get("home_points")
            away_pts=candidate.get("away_points")
            pred_margin=candidate.get("home_margin")
            pred_total=candidate.get("total_points")
            if (not all(finite(v) for v in (home_pts,away_pts,pred_margin,pred_total))
                or min(home_pts,away_pts,pred_total)<0 or
                abs(home_pts+away_pts-pred_total)>.03 or
                abs(home_pts-away_pts-pred_margin)>.03):
                raise ValueError("V04 model score incoherent or unsupported")
        else:
            home_pts=away_pts=pred_margin=pred_total=None
        # V04 decisions are a separate, immutable as-displayed research track.
        # Recompute from the archived board inputs to prevent forged picks.
        research=g.get("v04_market_research")
        qb_out_not_replaced=any(
            isinstance(g.get("official_longterm_qb_absence_"+side),dict) and
            g["official_longterm_qb_absence_"+side].get("status")==
                "OFFICIAL_SEASON_OUT_VERIFIED_AFTER_SOURCE_REVIEW" and
            g["official_longterm_qb_absence_"+side].get("verified_replacement_starter") is False
            for side in ("home","away"))
        if research is not None:
            if not isinstance(research,dict) or candidate is None:
                raise ValueError("V04 research decision without independent score")
            expected_research=v04_decide(
                candidate,spread,market_total,provider,market_observed,
                g["kickoff_utc"],now.isoformat(),g.get("qb_starters_verified",0),
                qb_confirmed_season_out_unverified_replacement=qb_out_not_replaced)
            if research!=expected_research:
                raise ValueError("V04 research policy changed or forged")
        # A distinct V05 immutable shadow receipt: no retrospective
        # recomputation and no model / ATS decision replacement.
        v05=g.get("v05_robust_scores")
        if v05 is not None:
            if (not isinstance(v05,dict) or
                v05.get("status")!=V05_STATUS or v05.get("model")!=V05_MODEL or
                v05.get("variant")!="v05_full" or
                v05.get("no_market_lines_in_training") is not True or
                v05.get("no_v03_forecast_reuse") is not True or
                v05.get("no_qb_or_injury_inference") is not True or
                v05.get("model_promoted") is not False or
                v05.get("uncertainty_not_calibrated") is not True or
                g.get("home_bias_quarantined") is not True):
                raise ValueError("V05 research source/status mismatch")
            v05_hp=v05.get("home_points");v05_ap=v05.get("away_points")
            v05_m=v05.get("home_margin");v05_t=v05.get("total_points")
            if (not all(finite(z) for z in (v05_hp,v05_ap,v05_m,v05_t)) or
                min(v05_hp,v05_ap,v05_t)<0 or
                abs(v05_hp+v05_ap-v05_t)>.03 or
                abs(v05_hp-v05_ap-v05_m)>.03 or
                type(v05.get("thin_history_warning")) is not bool or
                type(v05.get("source_training_games")) is not int or
                v05["source_training_games"]<90):
                raise ValueError("V05 incoherent or untrusted score receipt")
        else:
            v05_hp=v05_ap=v05_m=v05_t=None
        # Freeze the separately published, non-promoted V09 score
        # distribution for prospective grading. Never turn it into a V04 pick.
        v09=g.get("v09_score_shadows")
        if v09 is not None:
            if (not isinstance(v09,dict) or
                v09.get("status")!="V09_SOURCE_TIMED_SCORE_MONTE_CARLO_SHADOW_RESEARCH_ONLY" or
                v09.get("source_provenance")!="IMMUTABLE_CAPTURED_PREKICKOFF_SETTLED_V04" or
                v09.get("model_promoted") is not False or
                v09.get("safe_for_betting") is not False or
                v09.get("calibrated_betting_probability") is not False or
                v09.get("published_scores_unchanged") is not True or
                v09.get("historical_grades_unchanged") is not True or
                v09.get("forecast_observed_utc")!=board["forecast_observed_utc"] or
                parse_time(v09["generated_at_utc"])>now or
                parse_time(v09["generated_at_utc"])>=kickoff or
                type(v09.get("earlier_settled_v04_games")) is not int or
                v09["earlier_settled_v04_games"]<24 or
                candidate is None):
                raise ValueError("Untrusted, postkickoff or overpromoted V09 forecast")
            versions=v09.get("projections") or {}
            if set(versions)!={"global","team_form"}:
                raise ValueError("Missing prospective V09 simulation comparison")
            for name,pred in versions.items():
                h,a=pred.get("home_points"),pred.get("away_points")
                m,t=pred.get("margin"),pred.get("total")
                prob=pred.get("home_win_probability")
                if (not all(finite(x) for x in (h,a,m,t,prob)) or
                    h<0 or a<0 or not 0<=prob<=1 or
                    abs(h-a-m)>.01 or abs(h+a-t)>.01 or
                    pred.get("model_promoted") is not False or
                    type(pred.get("trials")) is not int or pred["trials"]<100):
                    raise ValueError("Untrusted V09 simulation score/probability")
        # Freeze V13 probability-only shadow as a prospective research receipt.
        # A new version NEVER rewrites original V04 means or V03 selections.
        v13=g.get("v13_probability_shadow")
        if v13 is not None:
            if (not isinstance(v13,dict) or candidate is None or
                v13.get("site_status")!="V13_SOURCE_TIMED_V04_PROBABILITY_SHADOW" or
                v13.get("status")!="V13_V04_ANCHORED_PROBABILITIES_RESEARCH_ONLY" or
                v13.get("variant")!="prior_variance" or
                v13.get("scoring_foundation")!="UNCHANGED_V04" or
                v13.get("v04_mean_scores_unchanged") is not True or
                v13.get("model_promoted") is not False or
                v13.get("safe_for_betting") is not False or
                v13.get("calibration_prospectively_proven") is not False or
                v13.get("research_probability_not_certified_betting_edge") is not True or
                v13.get("original_v04_score_checksum_unchanged") is not True or
                v13.get("previous_frozen_grades_unchanged") is not True or
                v13.get("source_provenance")!="IMMUTABLE_CAPTURED_PREKICKOFF_SETTLED_V04" or
                v13.get("original_forecast_observed_utc")!=board["forecast_observed_utc"] or
                str(v13.get("game_id"))!=gid or
                v13.get("home")!=home or v13.get("away")!=away or
                v13.get("kickoff_utc")!=g["kickoff_utc"] or
                parse_time(v13["generated_at_utc"])>now or
                parse_time(v13["generated_at_utc"])>=kickoff or
                str(v13.get("source_run_id"))!=str(board["forecast_run_id"]) or
                type(v13.get("calibration_earlier_games")) is not int or
                v13["calibration_earlier_games"]<35 or
                type(v13.get("calibration_earlier_weeks")) is not int or
                v13["calibration_earlier_weeks"]<2 or
                not all(finite(v13.get(k)) for k in ("home_points_mean","away_points_mean",
                    "margin_mean","total_mean","margin_sd","total_sd",
                    "home_win_probability","margin_p10","margin_p90",
                    "total_p10","total_p90")) or
                abs(v13["home_points_mean"]-home_pts)>.02 or
                abs(v13["away_points_mean"]-away_pts)>.02 or
                abs(v13["margin_mean"]-pred_margin)>.02 or
                abs(v13["total_mean"]-pred_total)>.02 or
                not (8<=v13["margin_sd"]<=30 and 8<=v13["total_sd"]<=30 and
                     0<=v13["home_win_probability"]<=1 and
                     v13["margin_p10"]<v13["margin_p90"] and
                     v13["total_p10"]<v13["total_p90"])):
                raise ValueError("Untrusted or modified pregame V13 probability receipt")
            # Recompute all mathematically derived probabilities and bands
            # to reject a tampered displayed forecast before immutable archive.
            def expected_cdf(z):
                return .5*math.erfc(-z/math.sqrt(2))
            if (abs(v13["home_win_probability"]-
                    expected_cdf(v13["margin_mean"]/v13["margin_sd"]))>.00005 or
                abs(v13["margin_p10"]-
                    (v13["margin_mean"]-1.2815515655446004*v13["margin_sd"]))>.002 or
                abs(v13["margin_p90"]-
                    (v13["margin_mean"]+1.2815515655446004*v13["margin_sd"]))>.002 or
                abs(v13["total_p10"]-
                    (v13["total_mean"]-1.2815515655446004*v13["total_sd"]))>.002 or
                abs(v13["total_p90"]-
                    (v13["total_mean"]+1.2815515655446004*v13["total_sd"]))>.002):
                raise ValueError("V13 displayed probability or interval forged")
            if v13.get("market_quote_eligible") is True:
                if not provider or not market_observed or not (sp or tt):
                    raise ValueError("V13 market probability missing authentic quote")
                checks=(
                    (v13.get("home_cover_probability"),
                     expected_cdf((v13["margin_mean"]+spread)/v13["margin_sd"])
                     if sp else None),
                    (v13.get("over_probability"),
                     expected_cdf((v13["total_mean"]-market_total)/v13["total_sd"])
                     if tt else None))
                for actual,expected in checks:
                    if expected is None:
                        if actual is not None:
                            raise ValueError("V13 inferred a missing bookmaker line")
                    elif not finite(actual) or abs(actual-expected)>.00005:
                        raise ValueError("Unverified V13 market-conditioned probability")
            elif (v13.get("home_cover_probability") is not None or
                  v13.get("over_probability") is not None):
                raise ValueError("V13 probabilities cannot infer unsourced bookmaker lines")
        # V14 is a distinct source-timed, not-promoted scoring challenger.
        # This freezes its predicted points alongside the original V04 and
        # V13 receipts; NEVER substitutes a V14 pick for displayed V04/V03.
        v14=g.get("v14_matchup_shadow")
        if v14 is not None:
            if (not isinstance(v14,dict) or candidate is None or
                g.get("home_bias_quarantined") is not True or
                v14.get("site_status")!="V14_SOURCE_TIMED_OPPONENT_MATCHUP_SCORE_SHADOW" or
                v14.get("status")!="V14_REGULARIZED_V04_MATCHUP_RESIDUAL_RESEARCH_ONLY" or
                v14.get("variant")!="joint_close" or
                v14.get("original_v04_score_unchanged") is not True or
                v14.get("matchup_evidence_ready") is not True or
                v14.get("model_promoted") is not False or
                v14.get("safe_for_betting") is not False or
                v14.get("historical_source_first_publication_verified") is not False or
                v14.get("historical_research_not_prospective_backtest") is not True or
                v14.get("source_cutoff_exclusive") is None or
                str(v14.get("game_id"))!=gid or
                v14.get("home")!=home or v14.get("away")!=away or
                v14.get("kickoff_utc")!=g["kickoff_utc"] or
                str(v14.get("forecast_run_id"))!=str(board["forecast_run_id"]) or
                v14.get("original_v04_forecast_observed_utc")!=board["forecast_observed_utc"] or
                parse_time(v14["source_observed_utc"])>now or
                parse_time(v14["source_observed_utc"])>=kickoff or
                parse_time(v14["source_observed_utc"])<orig or
                type(v14.get("earlier_matchup_training_games")) is not int or
                v14["earlier_matchup_training_games"]<55 or
                not all(finite(v14.get(k)) for k in
                    ("home_points","away_points","margin","total","v04_margin",
                     "v04_total","margin_adjustment","total_adjustment")) or
                min(v14["home_points"],v14["away_points"])<0 or
                abs(v14["home_points"]-v14["away_points"]-v14["margin"])>.02 or
                abs(v14["home_points"]+v14["away_points"]-v14["total"])>.02 or
                abs(v14["v04_margin"]-pred_margin)>.02 or
                abs(v14["v04_total"]-pred_total)>.02 or
                abs(v14["margin"]-pred_margin-v14["margin_adjustment"])>.02 or
                abs(v14["total"]-pred_total-v14["total_adjustment"])>.02 or
                abs(v14["margin_adjustment"])>6.01 or
                abs(v14["total_adjustment"])>6.01):
                raise ValueError("V14 pregame shadow is unsourced, tampered or overpromoted")
            probs=v14.get("probabilities")
            if probs is not None:
                if (v13 is None or not isinstance(probs,dict) or
                    probs.get("model_promoted") is not False or
                    probs.get("safe_for_betting") is not False or
                    probs.get("reliability_requires_future_validation") is not True or
                    not finite(probs.get("home_win")) or
                    abs(probs["home_win"]-
                        .5*math.erfc(-v14["margin"]/
                        (v13["margin_sd"]*math.sqrt(2))))>.00005):
                    raise ValueError("Unverified V14 win probability")
                for name,line,expected in (
                    ("home_cover",spread,sp),
                    ("over",market_total,tt)):
                    key=name+"_raw";calkey=name+"_calibrated"
                    actual=probs.get(key);cal=probs.get(calkey)
                    if not expected:
                        if actual is not None or cal is not None:
                            raise ValueError("V14 invented a missing bookmaker line")
                    else:
                        sd=v13["margin_sd"] if name=="home_cover" else v13["total_sd"]
                        mean=v14["margin"]+line if name=="home_cover" else v14["total"]-line
                        required=.5*math.erfc(-mean/(sd*math.sqrt(2)))
                        if (not finite(actual) or not finite(cal) or
                            abs(actual-required)>.00005 or not 0<=cal<=1 or
                            not provider or not market_observed):
                            raise ValueError("V14 market probability has no authenticated quote")
        discrepancy=round(abs(margin+spread),4) if sp else None
        risk="HIGH_MODEL_MARKET_DISAGREEMENT" if discrepancy is not None and discrepancy>=10 else "NONE"
        high_disagreement+=int(risk!="NONE")
        rows.append({
            "model_market_margin_disagreement":discrepancy,
            "calibration_review_flag":risk,
            "game_id":gid,"home":home,"away":away,"kickoff_utc":g["kickoff_utc"],
            "frozen_forecast_home_margin":margin,"frozen_forecast_total":total,
            "frozen_forecast_run_id":str(board["forecast_run_id"]),
            "forecast_model_version":board["model"],
            "frozen_forecast_observed_utc":board["forecast_observed_utc"],
            "frozen_forecast_sha256":board["forecast_sha256"],
            "market_home_spread":spread,"market_total":market_total,
            "market_home_moneyline":home_ml,"market_away_moneyline":away_ml,
            "market_provider":provider,"market_observed_utc":market_observed,
            "displayed_ats_side":side,"displayed_ou_side":over,
            "home_bias_quarantined":g.get("home_bias_quarantined") is True,
            "opponent_rating_shadow_model":(
                g["opponent_rating"]["model"] if isinstance(g.get("opponent_rating"),dict)
                else None),
            "opponent_rating_shadow_margin":(
                g["opponent_rating"]["predicted_home_margin"]
                if isinstance(g.get("opponent_rating"),dict) else None),
            "v04_direct_score_model":candidate.get("model") if candidate else None,
            "v04_direct_home_points":home_pts,
            "v04_direct_away_points":away_pts,
            "v04_direct_home_margin":pred_margin,
            "v04_direct_total_points":pred_total,
            "v04_direct_source_no_v03_total_reuse":(
                candidate["direct_scoring_fit_uses_v03_total"] is False
                if candidate else None),
            "v04_research_not_promoted":candidate.get("model_promoted") is False
                if candidate else None,
            "qb_verified_at_forecast":g.get("qb_starters_verified",0),
            "qb_pregame_expected_home":qb_identity["home"],
            "qb_pregame_expected_away":qb_identity["away"],
            "v05_shadow_model":v05["model"] if v05 else None,
            "v05_shadow_status":v05["status"] if v05 else None,
            "v05_shadow_home_points":v05_hp,
            "v05_shadow_away_points":v05_ap,
            "v05_shadow_home_margin":v05_m,
            "v05_shadow_total_points":v05_t,
            "v05_shadow_thin_history":v05["thin_history_warning"] if v05 else None,
            "v05_shadow_source_training_games":v05["source_training_games"] if v05 else None,
            "v05_shadow_not_promoted":v05["model_promoted"] is False if v05 else None,
            "v09_frozen_score_simulation":v09 if v09 else None,
            "v13_frozen_probability_shadow":v13 if v13 else None,
            "v14_frozen_matchup_shadow":v14 if v14 else None,
            "v04_research_status":research["status"] if research else None,
            "v04_research_policy":research["policy"] if research else None,
            "v04_research_ats_side":research["ats_side"] if research else None,
            "v04_research_ou_side":research["ou_side"] if research else None,
            "v04_research_ats_reason":research["ats_reason"] if research else None,
            "v04_research_ou_reason":research["ou_reason"] if research else None,
            "v04_research_ats_gap":research["raw_ats_model_market_gap"] if research else None,
            "v04_research_ou_gap":research["raw_ou_model_market_gap"] if research else None,
            "v04_research_anchored_margin":research["market_anchored_home_margin"] if research else None,
            "v04_research_anchored_total":research["market_anchored_total"] if research else None,
            "v04_research_qb_unknown":research["missing_verified_qb_warning"] if research else None,
            "v04_research_qb_official_out_unverified_replacement":(
                research["qb_confirmed_season_out_unverified_replacement"]
                if research else None),
            "official_longterm_qb_absence_sources":[
                {"side":side,"player":g["official_longterm_qb_absence_"+side]["player"],
                 "source_url":g["official_longterm_qb_absence_"+side]["source_url"],
                 "first_eligible_at_utc":g["official_longterm_qb_absence_"+side]["first_eligible_at_utc"]}
                for side in ("home","away")
                if isinstance(g.get("official_longterm_qb_absence_"+side),dict)],
        })
    if not rows:raise ValueError("No unstarted games to archive")
    rows.sort(key=lambda g:(g["kickoff_utc"],g["game_id"]))
    return {"status":STATUS,"schema_version":1,"betting_status":"PASS_UNVALIDATED",
            "capture_utc":now.isoformat(),"dashboard_run_id":str(run_id),
            "model_forecast_sha256":board["forecast_sha256"],
            "model_version":board["model"],
            "model_forecast_observed_utc":board["forecast_observed_utc"],
            "comparison_timing":"MARKET_MAY_HAVE_BEEN_OBSERVED_AFTER_FROZEN_MODEL_FORECAST",
            "market_publication_time_authenticated":False,
            "not_an_executed_bet":True,"eligible_for_future_verified_outcome_grading":True,
            "summary":{"future_games":len(rows),"games_with_line":quote_count,
                       "ats_decisions":ats,"total_decisions":ou,
                       "model_market_high_disagreements":high_disagreement},
            "rows":rows}

def archive(snapshot):
    if snapshot["status"]!=STATUS:raise ValueError("Invalid snapshot")
    run=str(snapshot["dashboard_run_id"])
    path=ROOT+"/"+parse_time(snapshot["capture_utc"]).strftime("%Y/%m/%d")+"/run-"+run+".json.gz"
    blob=store.pack(snapshot)
    old=store.get_blob_file(path)
    if old is not None:
        if old!=blob:raise ValueError("Different decisions for a preexisting run; refusing rewrite")
        return {"status":"ALREADY_ARCHIVED","path":path,"summary":snapshot["summary"]}
    saved=store.get_blob_file(INDEX)
    index=json.loads(saved) if saved else {"status":STATUS,"schema_version":1,"runs":[]}
    if (index.get("status")!=STATUS or index.get("schema_version")!=1
        or not isinstance(index.get("runs"),list)
        or any(x["run_id"]==run for x in index["runs"])):
        raise ValueError("Duplicate or corrupted model decision index")
    index["runs"].append({"run_id":run,"path":path,
                         "sha256":hashlib.sha256(store.encode(snapshot)).hexdigest(),
                         "capture_utc":snapshot["capture_utc"],
                         **snapshot["summary"]})
    _commit_material({path:blob,INDEX:store.encode(index)},run)
    return {"status":"ARCHIVED","path":path,"summary":snapshot["summary"]}

def run(input_file,now=None,run_id=None,persist=True):
    now=now or dt.datetime.now(dt.timezone.utc)
    run_id=run_id or os.environ.get("GITHUB_RUN_ID","")
    board=json.loads(Path(input_file).read_text(encoding="utf-8"))
    frozen=freeze(board,now,run_id)
    if not persist:return frozen
    return archive(frozen)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dashboard",required=True)
    a=p.parse_args()
    print(json.dumps(run(a.dashboard),sort_keys=True))

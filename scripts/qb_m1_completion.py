"""Milestone 1 acceptance report: distinguish implemented research from real coverage.

Validates exact team/game identities and source-time order across previously
created expected-QB, confirmation, conditioned shadow, and trainability audits.
A green CI build cannot substitute for verified starters, independent QB1/QB2
labels, or prospective held-out forecast lift. The report is research-only.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.game_context import parse_time
from scripts.qb_expected_starters import STATUS as EXPECTED
from scripts.qb_confirmation_coverage import STATUS as COVERAGE
from scripts.qb_conditional_forecast import STATUS as SHADOW
from scripts.qb_trainability_audit import STATUS as TRAINABILITY
from scripts.candidate_shadow_grade import STATUS as GRADES

STATUS="CFB_MILESTONE1_QB_COMPLETION_AUDIT_V1"
MIN_VERIFIED_SLOTS_FRACTION=.25
MIN_GRADED_GAMES=100
MIN_REPLACEMENT_EVENTS=25


def _trusted(item,status,clock=None):
    if (not isinstance(item,dict) or item.get("status")!=status or
        item.get("betting_status")!="PASS_UNVALIDATED" or
        item.get("model_promoted") is not False):
        raise ValueError("Untrusted milestone audit input: "+status)
    if clock and parse_time(item[clock]).tzinfo is None:
        raise ValueError("Unzoned source evidence")


def assess(expected,coverage,shadow,trainability,grades=None,now=None):
    _trusted(expected,EXPECTED,"observed_at_utc")
    _trusted(coverage,COVERAGE,"observed_at_utc")
    _trusted(shadow,SHADOW,"observed_at_utc")
    if (not isinstance(trainability,dict) or
        trainability.get("status")!=TRAINABILITY or
        trainability.get("betting_status")!="PASS_UNVALIDATED" or
        trainability.get("automatic_model_promotion") is not False or
        trainability.get("trained_qb_replacement_value") is not False or
        not isinstance(trainability.get("checks"),dict)):
        raise ValueError("Untrusted QB replacement trainability report")
    now=parse_time(now or dt.datetime.now(dt.timezone.utc).isoformat())
    clocks=[parse_time(x["observed_at_utc"]) for x in (expected,coverage,shadow)]
    if any(t>now for t in clocks) or clocks[1]<clocks[0] or clocks[2]<clocks[0]:
        raise ValueError("QB audit inputs observed outside safe forecast chronology")
    expected_rows=expected.get("games")
    coverage_rows=coverage.get("rows")
    shadow_rows=shadow.get("games")
    if any(not isinstance(v,list) for v in (expected_rows,coverage_rows,shadow_rows)):
        raise ValueError("Missing real source-aligned QB row arrays")
    def slots(rows):
        result={}
        for r in rows:
            key=(str(r["game_id"]),r["team"])
            if key in result:raise ValueError("Duplicate QB team/game")
            result[key]=r
        return result
    exp=slots(expected_rows)
    cov=slots(coverage_rows)
    if set(exp)!=set(cov) or expected.get("team_slots")!=len(exp):
        raise ValueError("Expected and review QB game/team cohorts differ")
    fixtures={}
    for key,e in exp.items():
        c=cov[key]
        if (e["team"]!=c["team"] or e["opponent"]!=c["opponent"] or
            parse_time(e["kickoff_utc"])!=parse_time(c["kickoff_utc"]) or
            parse_time(e["kickoff_utc"])<=clocks[0] or
            bool(e["is_confirmed_starter"])!=bool(c["confirmed_starter"]) or
            e.get("starter")!=c.get("expected_starter")):
            raise ValueError("QB source/review identity or starter claim changed")
        gid=key[0]
        slot=fixtures.setdefault(gid,{"teams":set(),"kickoffs":set()})
        slot["teams"].add(e["team"])
        slot["kickoffs"].add(parse_time(e["kickoff_utc"]))
    if any(len(v["teams"])!=2 or len(v["kickoffs"])!=1 for v in fixtures.values()):
        raise ValueError("Missing or malformed two-sided football matchup")
    shadow_games={}
    for s in shadow_rows:
        gid=str(s["game_id"])
        if gid in shadow_games:raise ValueError("Duplicate QB scenario forecast")
        shadow_games[gid]=s
        if (s.get("home") not in fixtures.get(gid,{}).get("teams",set()) or
            s.get("away") not in fixtures[gid]["teams"] or
            s["home"]==s["away"] or
            parse_time(s["kickoff_utc"]) not in fixtures[gid]["kickoffs"] or
            s.get("candidate",{}).get("model_promoted") is not False):
            raise ValueError("QB shadow is not the same pregame source fixture")
    if not set(shadow_games).issubset(fixtures):
        raise ValueError("QB shadow contains unmatched game")
    confirmed=sum(e["is_confirmed_starter"] is True for e in exp.values())
    if (confirmed!=coverage.get("summary",{}).get("confirmed") or
        confirmed!=expected.get("summary",{}).get("confirmed_starters")):
        raise ValueError("Contradictory verified starter counts")
    n=len(exp)
    research_coverage=confirmed/n if n else 0.
    source_ready=research_coverage>=MIN_VERIFIED_SLOTS_FRACTION
    conditional=sum(s["candidate"].get("status")=="QB_PLAYER_CONDITIONAL_SHADOW"
                    for s in shadow_rows)
    if conditional!=shadow.get("summary",{}).get("games_with_qb_conditional_adjustment"):
        raise ValueError("Untrusted player-conditioned forecast count")
    training_checks=trainability["checks"]
    independently_ready=trainability.get("ready_to_train_injury_qb_model") is True and all(training_checks.values())
    actual_events=trainability.get("summary",{}).get("independently_labeled_in_game_qb_replacements",0)
    if type(actual_events) is not int or actual_events<0:
        raise ValueError("Invalid actual QB switch count")
    if independently_ready and actual_events<MIN_REPLACEMENT_EVENTS:
        raise ValueError("Trainable QB estimator without verified replacement labels")
    graded=0; baseline=None; qb_mae=None; v04_mae=None; v04_paired=0
    v04_source_verified=False; v04_graded_archive_verified=False
    post_paired=0;post_eligible=0;post_coverage=None
    post_qb_mae=None;post_v04_mae=None;post_v03_mae=None
    post_dates=0;post_source_verified=False;post_prospective_lift=False
    if grades is not None:
        _trusted(grades,GRADES,"evaluated_at_utc")
        if parse_time(grades["evaluated_at_utc"])>now:
            raise ValueError("Unobserved future QB shadow grades")
        group=grades.get("metrics",{}).get("qb_conditional") or {}
        graded=group.get("games",0)
        if type(graded) is not int or graded<0:
            raise ValueError("Invalid paired forecast grade count")
        qb_mae=group.get("margin_mae")
        baseline=group.get("same_game_baseline_v03_mae")
        # V03 is quarantined because of home bias. Surpassing its MAE
        # cannot certify a modern QB challenger. Until a separate archived
        # same-game V04 score comparator is source-verified, keep 1D blocked.
        v04_mae=group.get("same_game_baseline_v04_mae")
        v04_paired=group.get("same_game_baseline_v04_games",0)
        v04_source_verified=group.get("same_game_v04_pregame_source_hashed") is True
        audit=grades.get("v04_comparison_audit")
        if isinstance(audit,dict) and audit.get("status")==(
              "QB_SHADOW_EARLIER_WEBSITE_V04_PAIRED_AUDIT_RESEARCH_ONLY"):
            scored=[r for r in grades.get("per_game",[])
                    if "qb_conditional" in r.get("model_results",{})]
            if len(scored)!=graded or audit.get("qb_candidate_games")!=graded:
                raise ValueError("Source-hashed V04 paired report grade denominator mismatch")
            paired=[r for r in scored if isinstance(r.get("v04_paired_reference"),dict)]
            if audit.get("same_game_v04_pair_count")!=len(paired):
                raise ValueError("Source-hashed V04 pair count differs from attached receipts")
            dates=set()
            for r in paired:
                z=r["v04_paired_reference"]
                capture=parse_time(z["capture_utc"])
                qb_capture=parse_time(z["qb_shadow_observed_utc"])
                kickoff=parse_time(z["kickoff_utc"])
                dates.add(kickoff.astimezone(ZoneInfo("America/New_York")).date().isoformat())
                kind=z.get("v04_source_kind","EARLIER_WEBSITE_SNAPSHOT")
                stamp=z.get("v04_source_receipt_sha256",z.get("site_snapshot_sha256"))
                if (kind not in ("SAME_INTAKE_BEFORE_QB_SHADOW",
                                 "EARLIER_WEBSITE_SNAPSHOT") or
                    (kind=="SAME_INTAKE_BEFORE_QB_SHADOW" and
                     (z.get("site_snapshot_sha256") is not None or
                      z.get("site_snapshot_run_id") is not None)) or
                    capture>qb_capture or kickoff<=qb_capture or
                    not 0<=(qb_capture-capture).total_seconds()<=21600 or
                    not isinstance(stamp,str) or len(stamp)!=64 or
                    z.get("source_hashed_before_qb_decision") is not True or
                    z.get("no_hindsight_recalculation") is not True or
                    z.get("market_odds_not_used") is not True):
                    raise ValueError("Untrusted predecision V04 score receipt")
            if audit.get("distinct_paired_football_dates")!=len(dates):
                raise ValueError("V04 paired football-date audit mismatch")
            v04_graded_archive_verified=(
                audit.get("predecision_source_hashed_no_hindsight") is True and
                audit.get("fully_matched_cohort") is True and
                len(dates)>=3 and len(paired)==graded and graded>0)
            if audit.get("post_instrumentation_eligible_games") is not None:
                source_cohort=[r for r in scored
                    if r.get("v04_same_intake_instrumented") is True]
                post_pairs=[r for r in source_cohort
                    if isinstance(r.get("v04_paired_reference"),dict)]
                post_dates=len({parse_time(r["v04_paired_reference"]["kickoff_utc"])
                    .astimezone(ZoneInfo("America/New_York")).date().isoformat()
                    for r in post_pairs})
                post_eligible=len(source_cohort)
                post_paired=len(post_pairs)
                if (audit["post_instrumentation_eligible_games"]!=post_eligible or
                    audit.get("post_instrumentation_paired_games")!=post_paired or
                    audit.get("post_instrumentation_distinct_game_dates")!=post_dates or
                    group.get("post_instrumentation_eligible_qb_games")!=post_eligible or
                    group.get("post_instrumentation_paired_qb_games")!=post_paired or
                    group.get("post_instrumentation_distinct_game_dates")!=post_dates):
                    raise ValueError("Post-instrumentation source cohort count mismatch")
                if any(r["v04_paired_reference"].get("v04_source_kind")!=
                       "SAME_INTAKE_BEFORE_QB_SHADOW" for r in post_pairs):
                    raise ValueError("Post-instrumentation source was not frozen same-intake V04")
                post_coverage=post_paired/post_eligible if post_eligible else None
                if post_eligible and (type(audit.get("post_instrumentation_pair_fraction"))
                    not in (int,float) or
                    abs(audit["post_instrumentation_pair_fraction"]-post_coverage)>1e-4):
                    raise ValueError("Post-instrumentation missingness hidden")
                if post_paired:
                    def mean(values):
                        if any(type(v) not in (int,float) or not math.isfinite(v)
                               for v in values):
                            raise ValueError("Untrusted post-instrumentation score")
                        return sum(values)/len(values)
                    post_qb_mae=mean([
                        r["v04_paired_reference"]["qb_conditional_abs_error"]
                        for r in post_pairs])
                    post_v04_mae=mean([
                        r["v04_paired_reference"]["v04_abs_error"]
                        for r in post_pairs])
                    post_v03_mae=mean([r["baseline_v03_abs_error"] for r in post_pairs])
                    for key,computed in (
                        ("post_instrumentation_qb_mae",post_qb_mae),
                        ("post_instrumentation_v04_mae",post_v04_mae),
                        ("post_instrumentation_no_qb_v03_mae",post_v03_mae)):
                        val=group.get(key)
                        if type(val) not in (int,float) or not math.isfinite(val) or
                           abs(val-computed)>1e-4:
                            raise ValueError("Post-instrumentation same-cohort MAE mismatch")
                post_source_verified=(audit.get("predecision_source_hashed_no_hindsight") is True
                     and post_paired>0 and all(
                         r["v04_paired_reference"].get("source_hashed_before_qb_decision") is True
                         for r in post_pairs))
                post_prospective_lift=(
                    post_source_verified and post_paired>=MIN_GRADED_GAMES and
                    post_eligible>=MIN_GRADED_GAMES and
                    post_coverage is not None and post_coverage>=.90 and
                    post_dates>=3 and post_qb_mae is not None and
                    post_qb_mae<post_v04_mae and post_qb_mae<post_v03_mae)
    legacy_measurable=(graded>=MIN_GRADED_GAMES and
                v04_graded_archive_verified and
                type(qb_mae) in (int,float) and math.isfinite(qb_mae) and
                type(v04_mae) in (int,float) and math.isfinite(v04_mae) and
                type(v04_paired) is int and v04_paired==graded and
                v04_source_verified and
                type(baseline) in (int,float) and math.isfinite(baseline) and
                qb_mae < baseline and qb_mae < v04_mae)
    measurable=legacy_measurable or post_prospective_lift
    sections={
        "1A_verified_starting_qb_coverage":{
            "engineering_ready":True,
            "evidence_ready":source_ready,
            "confirmed_game_team_slots":confirmed,"future_game_team_slots":n,
            "verified_fraction":round(research_coverage,5),
            "minimum_coverage_fraction":MIN_VERIFIED_SLOTS_FRACTION},
        "1B_qb_specific_historical_profiles":{
            "engineering_ready":True,
            "evidence_ready":conditional>0,
            "prospective_conditional_games":conditional,
            "historical_publication_time_authenticated":False},
        "1C_measured_qb_replacement_value":{
            "engineering_ready":True,
            "evidence_ready":independently_ready,
            "actual_independently_labeled_replacements":actual_events,
            "required_replacement_events":MIN_REPLACEMENT_EVENTS,
            "trainability_blockers":trainability.get("blocking_reasons",[]),
            "causal_player_points_validated":False},
        "1D_prospective_qb_validation":{
            "engineering_ready":True,
            "evidence_ready":measurable and independently_ready,
            "paired_qb_games":graded,"minimum_graded_games":MIN_GRADED_GAMES,
            "qb_candidate_margin_mae":qb_mae,
            "same_cohort_legacy_v03_mae":baseline,
            "same_cohort_baseline_mae":v04_mae,
            "same_cohort_required_baseline":"V04_FROZEN_PREDECISION_SAME_GAME",
            "same_game_v04_paired_games":v04_paired,
            "same_game_v04_source_hashed":v04_source_verified,
            "v04_per_game_source_receipts_verified":v04_graded_archive_verified,
            "requires_independent_v04_comparison":True,
            "post_instrumentation_eligible_games":post_eligible,
            "post_instrumentation_v04_paired_games":post_paired,
            "post_instrumentation_pair_fraction":(
                round(post_coverage,5) if post_coverage is not None else None),
            "minimum_post_instrumentation_coverage_fraction":.90,
            "post_instrumentation_distinct_football_dates":post_dates,
            "post_instrumentation_qb_mae":(
                round(post_qb_mae,5) if post_qb_mae is not None else None),
            "post_instrumentation_v04_mae":(
                round(post_v04_mae,5) if post_v04_mae is not None else None),
            "post_instrumentation_no_qb_v03_mae":(
                round(post_v03_mae,5) if post_v03_mae is not None else None),
            "post_instrumentation_source_verified":post_source_verified,
            "post_instrumentation_won_same_game_both_baselines":post_prospective_lift,
            "requires_at_least_3_independent_football_dates":True,
            "requires_improvement_over_v03_no_qb_ablation":True,
            "calibrated_ats_betting_edge":False}
    }
    complete=all(s["evidence_ready"] for s in sections.values()) and independently_ready
    blocked=[k for k,v in sections.items() if not v["evidence_ready"]]
    return {"status":STATUS,"season":2026,"asof_utc":now.isoformat(),
        "engineering_workflow_integrated":True,
        "milestone_1_evidence_complete":complete,
        "milestone_1_ready_for_model_promotion":False,
        "sections":sections,"blocked_sections":blocked,
        "remaining_roadmap_milestones":[
            "2_Evolving_team_and_individual_intelligence",
            "3_Advanced_opponent_specific_matchups",
            "4_Validated_drive_level_game_simulation",
            "5_Paired_prospective_model_competition"],
        "unverified_starter_not_assumed_healthy":True,
        "historical_forecasts_not_rewritten":True,
        "automatic_score_adjustment_from_qb_absence":False,
        "betting_status":"PASS_UNVALIDATED","model_promoted":False}


def run(expected,coverage,shadow,trainability,output,grades=None):
    def load(p):
        return json.loads(Path(p).read_text(encoding="utf-8"))
    result=assess(load(expected),load(coverage),load(shadow),
                  load(trainability),load(grades) if grades else None)
    path=Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError("Cannot overwrite milestone evidence")
    path.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",
                    encoding="utf-8")
    print(json.dumps({"status":STATUS,
         "engineering_workflow_integrated":True,
         "milestone_1_evidence_complete":result["milestone_1_evidence_complete"],
         "blocked_sections":result["blocked_sections"]},sort_keys=True))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("expected","coverage","shadow","trainability","output"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--grades")
    a=p.parse_args()
    run(a.expected,a.coverage,a.shadow,a.trainability,a.output,a.grades)

"""Fail-closed trainability audit for a future 2026 QB replacement-value model.

Step 3E records are authentic as-of *game features* and separately observed
final scores. This gate distinguishes confirmed starter coverage, injury
coverage, and actual participation/replacement outcomes. A QB1/QB2 depth
chart and previous-game passing leader are never labeled game-day QB1.
No player effects are estimated here.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from scripts.game_context import parse_time
from scripts.personnel_features import BASE_FIELDS, QB_FIELDS, COVERAGE_FIELDS, STATUS_FIELDS

STATUS="QB_REPLACEMENT_TRAINING_READINESS_RESEARCH_ONLY"
REQUIRED_FEATURES=set(BASE_FIELDS+QB_FIELDS+COVERAGE_FIELDS+STATUS_FIELDS)
PREDECLARED={"minimum_labeled_games":110,
    "minimum_chronological_folds":3,
    "minimum_heldout_games":60,
    "minimum_both_reviewed_starters_games":60,
    "minimum_independently_verified_replacement_events":25,
    "minimum_two_sided_report_fraction":0.60}

def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def _count(value,name):
    if type(value) is not int or value<0:
        raise ValueError("Invalid nonnegative count: "+name)
    return value

def assess(quality,features,labels):
    if not isinstance(quality,dict) or (
        quality.get("status")!="STEP3E_AUDITED_OBSERVED_DATASET_RESEARCH_ONLY" or
        quality.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Untrusted Step3E QA")
    qa=quality.get("quality",{})
    slots=_count(qa.get("team_slots"),"team_slots")
    policy_games=_count(qa.get("eligible_observation_game_ids_asof"),"policy games")
    observed_verified=_count(qa.get("reviewed_qb_slots"),"verified QB slots")
    both_reports=_count(qa.get("matchups_both_reports_verified"),"both reports")
    if slots!=2*policy_games or observed_verified>slots or both_reports>policy_games:
        raise ValueError("Inconsistent policy-selected evidence population")
    if not isinstance(features,list) or not isinstance(labels,list):
        raise ValueError("Separate pregame features and postgame labels required")
    if len(features)!=len(labels):
        raise ValueError("Only point-in-time games with verified finals may enter this gate")
    if len(features)!=_count(qa.get("labeled_final_games_known_at_evaluation"),"labeled finals"):
        raise ValueError("Outcome totals disagree with Step3E QA")
    idx={}
    for lab in labels:
        gid=str(lab.get("game_id"))
        if gid in idx:
            raise ValueError("Duplicate final game ID")
        idx[gid]=lab
    seen=set()
    counts=Counter()
    for g in features:
        gid=str(g.get("game_id"))
        if gid in seen or gid not in idx:
            raise ValueError("Duplicate/missing paired pregame feature")
        seen.add(gid)
        lab=idx[gid]
        if g.get("betting_status")!="PASS_UNVALIDATED":
            raise ValueError("Pregame feature not labeled research-only")
        vals=g.get("features")
        if not isinstance(vals,dict) or set(vals)!=REQUIRED_FEATURES:
            raise ValueError("Unexpected input schema or outcome leakage")
        if (lab.get("evidence_status")!="OBSERVED_POSTGAME_FINAL" or
            g.get("home")!=lab.get("home") or g.get("away")!=lab.get("away") or
            parse_time(g["kickoff_utc"])!=parse_time(lab["kickoff_utc"]) or
            not parse_time(g["capture_utc"])<parse_time(g["kickoff_utc"])<
            parse_time(lab["outcome_known_at_utc"])):
            raise ValueError("Invalid final source, identity or as-of chronology")
        if (type(lab.get("home_score")) is not int or
            type(lab.get("away_score")) is not int or
            min(lab["home_score"],lab["away_score"])<0):
            raise ValueError("Invalid postgame scoring label")
        states=[]
        for side in ("home","away"):
            indicator=vals[side+"_qb_reviewed"]
            report=vals[side+"_report_verified"]
            if indicator not in (0,1) or type(indicator) is not int or report not in (0,1) or type(report) is not int:
                raise ValueError("Missing/invalid QB or injury report indicator")
            counts["reviewed_starter_slots_in_labeled_games"]+=indicator
            counts["verified_report_slots_in_labeled_games"]+=report
            states.append((indicator,report))
        if states[0][0] and states[1][0]:
            counts["games_both_qbs_reviewed"]+=1
        elif states[0][0] or states[1][0]:
            counts["games_one_qb_reviewed"]+=1
        if states[0][1] and states[1][1]:
            counts["games_both_availability_reports_reviewed"]+=1
        for field in STATUS_FIELDS:
            if vals[field] is not None and not (states[0][1] and states[1][1]):
                raise ValueError("Non-pregame injury differential without both verified reports")
        if vals["availability_qb_out_diff"] is not None:
            counts["games_with_verified_qb_out_differential"]+=1
        counts["games_with_archived_verified_final"]+=1
    if seen!=set(idx):raise ValueError("Final game without pregame source")
    if counts["reviewed_starter_slots_in_labeled_games"]>observed_verified:
        raise ValueError("Labeled starter counts exceed archive observations")
    count=counts["games_with_archived_verified_final"]
    report_ratio=counts["games_both_availability_reports_reviewed"]/count if count else 0.
    # Step3E exports only reviewed boolean coverage, not player identities,
    # games-started, QB snaps, mobility/replacement labels, or postgame
    # starter identity. NEVER infer verified replacement events from a
    # reported quarterback being OUT or another QB's passing stats.
    named_starter_game_rows=0
    actual_replacement_participation_events=0
    checks={
        "labeled_sample_sufficient":count>=PREDECLARED["minimum_labeled_games"],
        "both_starters_confirmed_coverage":counts["games_both_qbs_reviewed"]>=PREDECLARED["minimum_both_reviewed_starters_games"],
        "verified_two_sided_reports":report_ratio>=PREDECLARED["minimum_two_sided_report_fraction"],
        "named_starter_by_game_in_audited_input":named_starter_game_rows>0,
        "independent_postgame_qb_participation_and_switch_labels":actual_replacement_participation_events>=PREDECLARED["minimum_independently_verified_replacement_events"],
        "original_model_publication_time_attested":False,
        "sufficient_heldout_chronological_folds":False}
    blocked=[k for k,v in checks.items() if not v]
    return {
        "status":STATUS,"season":2026,"betting_status":"PASS_UNVALIDATED",
        "selected_policy":"LATEST_OBSERVED_24_TO_72_HOURS_PREKICKOFF",
        "asof_utc":quality["evaluated_at_utc"],
        "summary":{
            "historical_policy_games":policy_games,
            "historical_policy_team_slots":slots,
            "reviewed_starters_in_policy_slots":observed_verified,
            "games_with_verified_finals":count,
            **{k:int(v) for k,v in sorted(counts.items())},
            "named_starter_matchups_in_step3e":named_starter_game_rows,
            "independently_labeled_in_game_qb_replacements":actual_replacement_participation_events,
            "verified_two_sided_report_fraction_labeled":round(report_ratio,5)},
        "preregistered_requirements":PREDECLARED,"checks":checks,"blocking_reasons":blocked,
        "data_sources_not_equivalent_to_starters":[
            "third-party depth-chart QB1","previous-game leading passer",
            "conference AVAILABLE or QUESTIONABLE QB","official team roster"],
        "missing_evidence":[
            "timestamped independently reviewed explicit starter identity per team and THIS game",
            "official player-level game participation/starter and snap information recorded POSTGAME",
            "QB switch/absence examples paired with original pregame source and subsequent final",
            "enough distinct prior observed QB-change cases for chronological held-out tests"],
        "trained_qb_replacement_value":False,
        "automatic_model_promotion":False,
        "ready_to_train_injury_qb_model":all(checks.values()),
        "source_time_leakage_guard":True,
        "note":"This Step3E record contains boolean reviewed-QB coverage, not player identity or actual replacements. Do not turn a zero-coverage archive into synthetic injury effects."}

def run(directory,output):
    root=Path(directory)
    report=assess(_read(root/"quality.json"),_read(root/"pregame_features.json"),_read(root/"postgame_labels.json"))
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():raise FileExistsError("Refuse overwriting research gate")
    dest.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":STATUS,"summary":report["summary"],
        "ready":report["ready_to_train_injury_qb_model"],
        "blocking_reasons":report["blocking_reasons"]}))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dataset-dir",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.dataset_dir,a.output)

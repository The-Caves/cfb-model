"""Step 3F: pre-registered prospective validation-readiness checks.

A deterministic gate over Step 3E files; no live bets, no predicted picks,
no automatic model promotion or retrospective health inference. This module
never turns a passing *research* metric into a validated model.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

from scripts.game_context import parse_time
from scripts.personnel_ablation import VARIANTS
from scripts.personnel_features import FEATURE_FIELDS

STATUS = "STEP3F_PROSPECTIVE_VALIDATION_READINESS_ONLY"
BASE_MIN_TRAIN = 90
BASE_MIN_TEST_PER_FOLD = 20
MIN_FOLDS = 3
MIN_TOTAL_HELDOUT = 60
# These are predeclared *coverage diagnostic* thresholds, not effect sizes.
MIN_BOTH_TEAM_REPORT_COVERAGE = 0.60
MIN_VERIFIED_QB_SLOTS = 0.25
MAX_ALL_FEATURE_NULL_RATE = 0.50
POLICY = "LATEST_OBSERVED_24_TO_72_HOURS_PREKICKOFF"
VALUES = set(FEATURE_FIELDS)


def at(value):
    return parse_time(value)


def _zero_or_pos_int(value):
    return type(value) is int and value >= 0


def _count(q, name):
    value = q.get(name)
    if not _zero_or_pos_int(value):
        raise ValueError("Invalid 2026 dataset count: " + name)
    return value


def _check_features(rows, labels, evaluation):
    if not isinstance(rows,list) or not isinstance(labels,list):
        raise ValueError("2026 dataset files must contain lists")
    if len(rows) != len(labels):
        raise ValueError("Pregame/features and final labels must be paired")
    pregame = {}
    for row in rows:
        if not isinstance(row,dict) or row.get("betting_status") != "PASS_UNVALIDATED":
            raise ValueError("Unvalidated pregame record required")
        gid = str(row["game_id"])
        if gid in pregame:
            raise ValueError("Duplicate observed pregame game")
        capture = at(row["capture_utc"])
        kickoff = at(row["kickoff_utc"])
        delta = (kickoff - capture).total_seconds()/3600
        if not 24 <= delta <= 72:
            raise ValueError("Wrong prospective 24-to-72h prediction cutoff")
        if capture > evaluation:
            raise ValueError("Future pregame capture")
        if not isinstance(row.get("record_sha256"),str) or len(row["record_sha256"])!=64 or any(
            c not in "0123456789abcdef" for c in row["record_sha256"]):
            raise ValueError("Missing original archived feature checksum")
        feats = row.get("features")
        if not isinstance(feats,dict) or set(feats) != VALUES:
            raise ValueError("Mismatched frozen feature schema")
        for name,value in feats.items():
            if value is not None and (type(value) not in (int,float) or not math.isfinite(value)):
                raise ValueError("Non-numeric or malformed pregame feature: "+name)
        for banned in ("home_score","away_score","result","settlement","actual_margin","actual_total"):
            if banned in row or banned in feats:
                raise ValueError("Postgame outcome appears in pregame data")
        pregame[gid]=row
    seen = set()
    for label in labels:
        if not isinstance(label,dict) or label.get("evidence_status") != "OBSERVED_POSTGAME_FINAL":
            raise ValueError("Unverified postgame label")
        gid = str(label["game_id"])
        if gid in seen or gid not in pregame:
            raise ValueError("Unmatched or duplicate final label")
        seen.add(gid)
        row = pregame[gid]
        if (row["home"],row["away"],at(row["kickoff_utc"])) != (
            label["home"],label["away"],at(label["kickoff_utc"])):
            raise ValueError("Final label and pregame event disagree")
        if any(type(label.get(k)) is not int or label[k] < 0
               for k in ("home_score","away_score")):
            raise ValueError("Final score must be an observed nonnegative integer")
        known = at(label["outcome_known_at_utc"])
        if not at(row["kickoff_utc"]) < known <= evaluation:
            raise ValueError("Outcome was unavailable at audit time")
        source = label.get("source_url")
        if source != "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard":
            raise ValueError("Unverified observed scoreboard source")
    return pregame


def _check_report(quality, eval_report, rows, labels):
    if not isinstance(quality,dict) or quality.get("status") != "STEP3E_AUDITED_OBSERVED_DATASET_RESEARCH_ONLY" or (
        quality.get("betting_status") != "PASS_UNVALIDATED"):
        raise ValueError("Step 3E quality report not authenticated")
    if (not isinstance(eval_report,dict) or
        eval_report.get("status") != "OBSERVED_PERSONNEL_ABLATION_RESEARCH_ONLY" or
        eval_report.get("betting_status") != "PASS_UNVALIDATED" or
        eval_report.get("model_promoted") is not False):
        raise ValueError("Not a valid research-only evaluation report")
    q=quality.get("quality")
    if not isinstance(q,dict):
        raise ValueError("Missing Step 3E source coverage audit")
    instant = at(quality["evaluated_at_utc"])
    games = _check_features(rows,labels,instant)
    total = _count(q,"distinct_archived_game_ids")
    eligible = _count(q,"eligible_observation_game_ids_asof")
    linked = _count(q,"linked_final_game_ids_total")
    matched = _count(q,"labeled_final_games_known_at_evaluation")
    team = _count(q,"team_slots")
    both = _count(q,"matchups_both_reports_verified") if eligible else 0
    qbs = _count(q,"reviewed_qb_slots") if eligible else 0
    reports = _count(q,"verified_report_slots") if eligible else 0
    if not (0<=len(rows)==len(labels)==matched<=linked<=total and
            eligible<=total and matched<=eligible and
            team==2*eligible and both<=eligible and
            qbs<=team and reports<=team):
        raise ValueError("Inconsistent archived roster/coverage population counts")
    missing = q.get("missing_features_among_selected_games",{})
    if not isinstance(missing,dict) or q.get("missing_value_denominator_game_ids") != eligible:
        raise ValueError("Invalid per-feature missingness denominator")
    if any(name not in VALUES or not _zero_or_pos_int(count) or count>eligible
           for name,count in missing.items()):
        raise ValueError("Invalid pregame null feature audit")
    if eval_report.get("game_selection_policy") != POLICY:
        raise ValueError("Unregistered prediction observation policy")
    if quality.get("evaluation_gate",{}).get("model_ready_for_promotion") is not False or (
        quality["evaluation_gate"].get("model_promoted") is not False):
        raise ValueError("Potentially promoted unvalidated personnel model")
    return q,instant


def _validate_folds(evaluation, games, labels, asof):
    folds = evaluation.get("folds")
    comparisons = evaluation.get("comparisons")
    aggregates = evaluation.get("aggregates")
    if not isinstance(folds,list) or not isinstance(comparisons,dict) or (
        not isinstance(aggregates,dict)):
        raise ValueError("Missing preregistered research fold diagnostics")
    by_game={str(r["game_id"]):r for r in games}
    by_label={str(r["game_id"]):r for r in labels}
    if len(by_game)!=len(games) or set(by_game)!=set(by_label):
        raise ValueError("Historical fold universe contains duplicates or unpaired labels")
    seen_cutoff=set()
    seen_heldout_ids=set()
    last_cutoff=None
    heldout=0
    qualifying=0
    comparable={key:0 for key in VARIANTS if key!="profile_baseline"}
    lack_of_variation={key:0 for key in VARIANTS if key!="profile_baseline"}
    for fold in folds:
        cutoff=at(fold["train_before_utc"])
        if last_cutoff and cutoff <= last_cutoff or cutoff in seen_cutoff:
            raise ValueError("Unordered or duplicate training-fold cutoff")
        seen_cutoff.add(cutoff)
        last_cutoff=cutoff
        train=fold["train_games"]
        test=fold["test_games"]
        if not _zero_or_pos_int(train) or not _zero_or_pos_int(test):
            raise ValueError("Malformed training/heldout game counts")
        train_ids=fold.get("train_game_ids")
        test_ids=fold.get("test_game_ids")
        if (not isinstance(train_ids,list) or not isinstance(test_ids,list) or
            any(type(gid) is not str for gid in train_ids+test_ids) or
            train_ids!=sorted(set(train_ids)) or test_ids!=sorted(set(test_ids)) or
            len(train_ids)!=train or len(test_ids)!=test or
            set(train_ids)&set(test_ids)):
            raise ValueError("Missing, duplicate or overlapping per-fold game IDs or membership")
        beginning=cutoff.date()
        ending=beginning+dt.timedelta(days=7)
        prior=sorted(gid for gid,r in by_game.items()
            if at(r["kickoff_utc"]) < cutoff and
            at(by_label[gid]["outcome_known_at_utc"]) < cutoff)
        test_window=sorted(gid for gid,r in by_game.items()
            if beginning <= at(r["kickoff_utc"]).date() < ending)
        if train_ids!=prior or test_ids!=test_window:
            raise ValueError("Historical train/test game ID membership or label as-of mismatch")
        if cutoff>asof and (train or test):
            raise ValueError("A future validation fold attempted to use observations")
        if fold["status"]=="RESEARCH_FOLD_EVALUATED":
            if train < BASE_MIN_TRAIN or test < BASE_MIN_TEST_PER_FOLD or cutoff > asof:
                raise ValueError("Insufficient or future-labeled evaluated fold")
            models=fold["models"]
            base=models.get("profile_baseline",{})
            if base.get("status") != "RETROSPECTIVE_EVALUATION_OF_CAPTURED_EVIDENCE" or (
                base.get("games") != test):
                raise ValueError("Inconsistent baseline held-out games")
            for metric in ("su_accuracy","margin_mae","total_mae"):
                v=base.get(metric)
                if v is not None and (type(v) not in (int,float) or not math.isfinite(v)):
                    raise ValueError("Invalid baseline score")
            if seen_heldout_ids.intersection(test_ids):
                raise ValueError("Repeated held-out matchup in multiple folds")
            seen_heldout_ids.update(test_ids)
            qualifying+=1
            heldout+=test
            for name in comparable:
                model=models.get(name,{})
                if model.get("status") == "RETROSPECTIVE_EVALUATION_OF_CAPTURED_EVIDENCE":
                    if model.get("games") != test:
                        raise ValueError("Unequal variant and baseline test games")
                    comparable[name]+=test
                elif model.get("status")=="SKIPPED_NO_TRAINING_FEATURE_VARIATION":
                    lack_of_variation[name]+=1
                else:
                    raise ValueError("Unrecognized variant fold result")
        elif fold["status"]!="INSUFFICIENT_OBSERVED_TRAINING_OR_TEST":
            raise ValueError("Unknown research validation-fold status")
    # The source report itself must not certify a model promotion.
    if evaluation.get("model_promoted") is not False or (
        aggregates.get("profile_baseline") is not None and
        aggregates["profile_baseline"].get("games") != heldout):
        raise ValueError("Reported baseline aggregate diverges from held-out folds")
    for name in comparable:
        summary=aggregates.get(name)
        if summary is not None and summary.get("games") != comparable[name]:
            raise ValueError("Variant aggregate does not match source fold game counts")
    return {"evaluated_folds":qualifying,"heldout_games":heldout,
            "paired_variant_games":comparable,
            "folds_without_personnel_feature_variation":lack_of_variation}


def assess(quality,features,labels,evaluation):
    """Audit Step 3E outputs, then preregister the next evidence gates."""
    q,when = _check_report(quality,evaluation,features,labels)
    folds = _validate_folds(evaluation,features,labels,when)
    eligible=q["eligible_observation_game_ids_asof"]
    matched=q["labeled_final_games_known_at_evaluation"]
    sides=q.get("team_slots",0)
    both=q.get("matchups_both_reports_verified",0)
    quarterbacks=q.get("reviewed_qb_slots",0)
    missing=q.get("missing_features_among_selected_games",{})
    fields=len(VALUES)*eligible
    nulls=sum(missing.values())
    report_rate=both/eligible if eligible else None
    qb_rate=quarterbacks/sides if sides else None
    null_rate=nulls/fields if fields else None
    nfold=folds["evaluated_folds"]
    ntest=folds["heldout_games"]
    sample_ok=(nfold>=MIN_FOLDS and ntest>=MIN_TOTAL_HELDOUT and
               matched >= BASE_MIN_TRAIN+BASE_MIN_TEST_PER_FOLD)
    variants_ok=all(n==ntest and n>0 for n in folds["paired_variant_games"].values())
    report_ok=(report_rate is not None and report_rate>=MIN_BOTH_TEAM_REPORT_COVERAGE)
    qb_ok=(qb_rate is not None and qb_rate>=MIN_VERIFIED_QB_SLOTS)
    null_ok=(null_rate is not None and null_rate<=MAX_ALL_FEATURE_NULL_RATE)
    checks={
        "at_least_90_prior_observed_train_and_20_test_each_fold":sample_ok,
        "at_least_3_nonoverlapping_evaluated_folds":nfold>=MIN_FOLDS,
        "at_least_60_matched_heldout_games":ntest>=MIN_TOTAL_HELDOUT,
        "all_personnel_variants_compared_on_same_games":variants_ok,
        "at_least_60pct_two_team_reports_verified":report_ok,
        "at_least_25pct_qb_slots_reviewed":qb_ok,
        "at_most_50pct_missing_feature_cells":null_ok,
        "independent_historical_pbp_publication_verified":False,
        "independent_source_clock_and_archive_immutability_verified":False,
        "authentic_predecision_market_spreads_totals_verified":False,
        "out_of_sample_statistical_significance_verified":False}
    blocked=[k for k,v in checks.items() if not v]
    # Clear preconditions for the *next investigation*, not betting clearance.
    research_ready=(sample_ok and variants_ok and report_ok and qb_ok and null_ok)
    return {
        "status":STATUS,"season":2026,
        "evaluation_asof_utc":when.isoformat(),
        "model_version":"v0.4 Step 3F prospective validation preregistration",
        "observation_policy":POLICY,
        "observed_archived_game_ids":q["distinct_archived_game_ids"],
        "policy_eligible_game_ids":eligible,
        "linked_final_game_ids":q["linked_final_game_ids_total"],
        "valid_paired_game_ids":matched,
        "folds":folds,
        "missingness":{"null_feature_cells":nulls,
                       "all_feature_cells":fields,
                       "null_fraction":round(null_rate,5) if null_rate is not None else None,
                       "two_sided_report_matchup_fraction":round(report_rate,5) if report_rate is not None else None,
                       "verified_starting_qb_slot_fraction":round(qb_rate,5) if qb_rate is not None else None},
        "preregistered_thresholds":{
            "min_previous_training_games":BASE_MIN_TRAIN,
            "min_test_games_per_fold":BASE_MIN_TEST_PER_FOLD,
            "min_nonoverlapping_folds":MIN_FOLDS,
            "min_total_heldout":MIN_TOTAL_HELDOUT,
            "min_two_sided_report_rate":MIN_BOTH_TEAM_REPORT_COVERAGE,
            "min_qb_starter_review_rate":MIN_VERIFIED_QB_SLOTS,
            "max_null_feature_cell_rate":MAX_ALL_FEATURE_NULL_RATE},
        "checks":checks,
        "blocking_reasons":blocked,
        "observed_personnel_research_comparison_ready":research_ready,
        "market_outcomes_available":False,
        "validated_prediction_improvement":False,
        "model_ready_for_promotion":False,
        "model_promoted":False,
        "safe_for_betting":False,
        "betting_status":"PASS_UNVALIDATED"}


def run(dataset_dir, output):
    source=Path(dataset_dir)
    q=json.loads((source/"quality.json").read_text())
    f=json.loads((source/"pregame_features.json").read_text())
    l=json.loads((source/"postgame_labels.json").read_text())
    e=json.loads((source/"personnel_ablation.json").read_text())
    result=assess(q,f,l,e)
    path=Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as handle:
        json.dump(result,handle,indent=2,sort_keys=True,allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status":STATUS,"policy_eligible_games":result["policy_eligible_game_ids"],
                     "valid_paired_games":result["valid_paired_game_ids"],
                     "research_ready":result["observed_personnel_research_comparison_ready"],
                     "blocking_reasons":result["blocking_reasons"],
                     "betting_status":"PASS_UNVALIDATED"}))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dataset-dir",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.dataset_dir,a.output)

"""Deterministic V05 challenger acceptance audit; never self-promotes a model.

A green research CI run does *not* mean a score model is better, or an ATS
selection is valid. Score changes require independent, immutable prospective
evidence, and a separate explicit promotion decision.
"""
import argparse
import json
import math
from pathlib import Path

from scripts.v05_score_benchmark import STATUS as BENCHMARK_STATUS

STATUS="V05_COMPETITION_EVIDENCE_GATE_RESEARCH_ONLY"
MIN_HISTORICAL_GAMES=200
MIN_FOLDS=4
MIN_PROSPECTIVE_GAMES=250
MIN_PROSPECTIVE_WEEKS=4
MIN_SCORE_IMPROVEMENT=.02
MAX_HOME_FRACTION_GAP=.10
MIN_INTERVAL_COVERAGE=.75


def _number(x):
    return type(x) in (int,float) and math.isfinite(x)


def assess(report,prospective=None):
    if (not isinstance(report,dict) or report.get("status")!=BENCHMARK_STATUS or
        report.get("season")!=2026 or
        report.get("same_team_and_game_ids_for_all_models") is not True or
        report.get("score_model_promoted") is not False or
        report.get("betting_status")!="PASS_UNVALIDATED" or
        report.get("historical_market_lines_used") is not False):
        raise ValueError("Unverified or modified historical challenger report")
    models=report.get("models",{})
    old=models.get("v04",{})
    new=models.get("v05_full",{})
    if (not _number(old.get("margin_mae")) or not _number(new.get("margin_mae")) or
        not _number(old.get("total_mae")) or not _number(new.get("total_mae")) or
        not _number(old.get("su_accuracy")) or not _number(new.get("su_accuracy")) or
        min(old["margin_mae"],new["margin_mae"],old["total_mae"],new["total_mae"])<=0 or
        old.get("games")!=report.get("matched_games") or
        new.get("games")!=report.get("matched_games")):
        raise ValueError("Incomplete paired validation metrics")
    intervals=report.get("v05_interval_diagnostics",{})
    baseline=report.get("naive_home_winner_control",{})
    predicted_home=new.get("predicted_home_fraction")
    home_observed=baseline.get("su_accuracy")
    if not (_number(predicted_home) and _number(home_observed)):
        raise ValueError("Missing independently observed home-side reference")
    checks={
        "sample_at_least_200":report["matched_games"]>=MIN_HISTORICAL_GAMES,
        "at_least_four_chronological_weeks":report.get("n_folds",0)>=MIN_FOLDS,
        "margin_improvement_at_least_2pct":new["margin_mae"]<=
            old["margin_mae"]*(1-MIN_SCORE_IMPROVEMENT),
        "total_improvement_at_least_2pct":new["total_mae"]<=
            old["total_mae"]*(1-MIN_SCORE_IMPROVEMENT),
        "su_accuracy_not_worse_than_v04":new["su_accuracy"]>=old["su_accuracy"],
        "home_prediction_rate_near_observed":abs(predicted_home-home_observed)<=MAX_HOME_FRACTION_GAP,
        "both_intervals_75pct_or_better":(
            intervals.get("calibrated_games",0)>=50 and
            _number(intervals.get("margin_coverage")) and
            _number(intervals.get("total_coverage")) and
            intervals["margin_coverage"]>=MIN_INTERVAL_COVERAGE and
            intervals["total_coverage"]>=MIN_INTERVAL_COVERAGE and
            intervals.get("only_prior_heldout_week_residuals") is True),
    }
    check_prospective={"independently_frozen":False,
        "sample_at_least_250":False,
        "at_least_four_weeks":False,
        "synchronized_quoted_market_baseline":False,
        "independent_outcomes_and_source_provenance":False}
    if prospective is not None:
        if not isinstance(prospective,dict):
            raise ValueError("Bad prospective evidence contract")
        check_prospective={
            "independently_frozen":prospective.get("immutable_pregame_forecasts_verified") is True,
            "sample_at_least_250":type(prospective.get("paired_games")) is int and
                              prospective["paired_games"]>=MIN_PROSPECTIVE_GAMES,
            "at_least_four_weeks":type(prospective.get("completed_weeks")) is int and
                              prospective["completed_weeks"]>=MIN_PROSPECTIVE_WEEKS,
            "synchronized_quoted_market_baseline":prospective.get(
                              "market_quotes_at_decision_time_authenticated") is True,
            "independent_outcomes_and_source_provenance":prospective.get(
                              "independent_final_outcomes_verified") is True
                              and prospective.get("historical_publication_authentication") is True,
        }
    # This audit is NEVER an authority to update a production model.
    blocked=[k for k,v in {**checks,**{"prospective_"+k:v
                 for k,v in check_prospective.items()}}.items() if not v]
    return {
        "status":STATUS,"historical_screening":checks,
        "prospective_evidence_checks":check_prospective,
        "nonpassing_checks":blocked,"n_nonpassing_checks":len(blocked),
        "historical_screening_all_passed":all(checks.values()),
        "verified_prospective_cohort_complete":all(check_prospective.values()),
        "research_candidate_ready_for_manual_review":(
            all(checks.values()) and all(check_prospective.values())),
        "automatic_model_promotion":False,
        "production_model_unchanged":True,
        "model_promoted":False,
        "validated_betting_edge":False,
        "betting_status":"PASS_UNVALIDATED",
        "paired_games":report["matched_games"],
        "paired_folds":report["n_folds"],
        "v04_margin_mae":old["margin_mae"],
        "v05_margin_mae":new["margin_mae"],
        "v04_total_mae":old["total_mae"],
        "v05_total_mae":new["total_mae"],
        "v04_su":old["su_accuracy"],"v05_su":new["su_accuracy"],
        "notes":"Historical scores were retrospectively sourced; model comparison is research only. This gate cannot authorize wagering or deployment."
    }


def run(benchmark_path,output_path):
    with open(benchmark_path,encoding="utf-8") as f:
        benchmark=json.load(f)
    result=assess(benchmark)
    path=Path(output_path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(result,sort_keys=True))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--benchmark",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    run(args.benchmark,args.output)

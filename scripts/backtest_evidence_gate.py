"""Audit whether retrospective results qualify as a point-in-time betting backtest.

This deliberately refuses to relabel retrospectively retrieved EPA, unknown
historical prices, weather, or player availability as verified pregame evidence.
"""
import argparse
import json
from pathlib import Path

STATUS = "BACKTEST_EVIDENCE_GATE_RESEARCH_ONLY"
REQUIREMENTS = {
    "epa_pbp": "historical_pregame_source_provenance_verified",
    "historical_market": "historical_market_quotes_verified",
    "pregame_weather": "historical_weather_forecasts_verified",
    "player_replacement": "historical_player_replacement_values_validated",
}

def audit(retrospective, evidence=None):
    if retrospective.get("status") != "RETROSPECTIVE_RESEARCH_ONLY":
        raise ValueError("Unexpected retrospective model report")
    if retrospective.get("season") != 2026 or retrospective.get("betting_status") != "PASS_UNVALIDATED":
        raise ValueError("Wrong season or research clearance")
    if retrospective.get("safe_for_betting") is not False:
        raise ValueError("Unsafe retrospective clearance")
    evidence = evidence or {}
    if not isinstance(evidence, dict):
        raise ValueError("Invalid evidence manifest")
    checks = {}
    for name, key in REQUIREMENTS.items():
        # Independent evidence is not inferred from model metrics. Require an
        # explicit verified manifest plus actual supporting records.
        record = evidence.get(name)
        supported = (isinstance(record, dict) and
                     record.get("verified") is True and
                     type(record.get("eligible_games")) is int and
                     record["eligible_games"] > 0 and
                     isinstance(record.get("source_manifest_sha256"), str) and
                     len(record["source_manifest_sha256"]) == 64)
        checks[name] = {"verified": bool(supported), "eligible_games":
                        record["eligible_games"] if supported else 0,
                        "reason": "EXTERNAL_EVIDENCE_MANIFEST_REQUIRED" if not supported else "EVIDENCE_DECLARED_REQUIRES_INDEPENDENT_AUDIT"}
    # Manifest declarations alone never establish a leak-free betting backtest.
    return {"status": STATUS, "season": 2026, "checks": checks,
            "research_folds": len(retrospective.get("weekly_folds", [])),
            "chronological_research_possible": bool(retrospective.get("weekly_folds")),
            "authenticated_betting_backtest_ready": False,
            "blockers": [name for name, check in checks.items() if not check["verified"]],
            "independent_source_time_audit_required": True,
            "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"}

def run(backtest, output, evidence=None):
    source = json.loads(Path(backtest).read_text(encoding="utf-8"))
    manifest = json.loads(Path(evidence).read_text(encoding="utf-8")) if evidence else None
    report = audit(source, manifest)
    dest = Path(output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": STATUS, "blockers": report["blockers"],
                      "authenticated_betting_backtest_ready": False}))
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--evidence")
    args = parser.parse_args()
    run(args.backtest, args.output, args.evidence)

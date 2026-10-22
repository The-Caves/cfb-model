"""Build research-only QB/injury joins from the *same* actual context capture.

No retrospective injury replay or unreviewed news promotion. Outputs remain
unvalidated and are artifacts, not production picks or bet instructions.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from scripts.game_context import parse_time
from scripts.qb_review_queue import build_queue
from scripts.qb_history import observe as observe_qb
from scripts.injury_history import observe as observe_injury
from scripts.personnel_features import join_capture
from scripts.personnel_ablation import ablate


def build(capture, context):
    captured = parse_time(capture["captured_at_utc"])
    cutoff = parse_time(context["captured_at_utc"])
    if not parse_time(context["asof_utc"]) <= cutoff <= captured:
        raise ValueError("Context unavailable before capture")
    if parse_time(capture["sources"]["context_captured_utc"]) != cutoff or (
        parse_time(capture["sources"]["context_asof_utc"]) != parse_time(context["asof_utc"])):
        raise ValueError("Profile capture context identity mismatch")
    # This queue explicitly says NO news source was queried in this workflow.
    # Reviewed QB confirmations can only originate in the validated context.
    no_news = {"manifest": {"status": "OFFICIAL_NEWS_REVIEW_ONLY",
                            "asof_utc": cutoff.isoformat(), "feed_status": {}},
               "candidates": []}
    queue = build_queue(context, no_news, cutoff.isoformat())
    quarterback = observe_qb(context, queue, cutoff.isoformat())
    availability = observe_injury(context, cutoff.isoformat())
    joined = join_capture(capture, [quarterback], [availability])
    return joined


def run(capture_path, context_path, output_dir):
    capture = json.loads(Path(capture_path).read_text())
    context = json.loads(Path(context_path).read_text())
    joined = build(capture, context)
    report = ablate([joined], [], dt.datetime.now(dt.timezone.utc).isoformat())
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    a = root/("personnel-joined-"+str(joined["run_id"])+".json")
    b = root/("personnel-ablation-"+str(joined["run_id"])+".json")
    # File naming keyed to the existing GitHub run, never silently overwrite.
    with a.open("x", encoding="utf-8") as handle:
        json.dump(joined, handle, indent=2, allow_nan=False)
        handle.write("\n")
    with b.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status": joined["status"],
                      "games_joined": joined["summary"]["matchups"],
                      "complete_availability": joined["summary"]["matchups_with_both_availability_reports"],
                      "reviewed_qb_slots": joined["summary"]["reviewed_qb_slots"],
                      "ablation_validated": report["evidence_sufficient_for_real_ablation"],
                      "betting_status": "PASS_UNVALIDATED"}))
    return joined, report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--capture", required=True)
    p.add_argument("--context", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    run(args.capture, args.context, args.output)

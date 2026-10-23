"""Offline historical odds snapshot importer to the existing PRIVATE quote vault.

Never requests paid APIs, invents opener/closer labels, or publishes prices.
A retrospectively imported quote is not treated as a live captured price.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from scripts.game_context import parse_time
from scripts.market_quotes import normalize
from scripts.market_vault import default_path, safe_path, store

STATUS = "PRIVATE_HISTORICAL_MARKET_IMPORT_RESEARCH_ONLY"

def ingest(paths, vault, retrieved_at_utc=None, bookmakers=("fanduel",)):
    if not paths or len(paths) > 1000:
        raise ValueError("Supply 1 to 1000 explicit historical snapshot paths")
    target = safe_path(vault, create=True)
    now = retrieved_at_utc or dt.datetime.now(dt.timezone.utc).isoformat()
    parse_time(now)
    seen = set()
    counts = {"files": 0, "snapshots_added": 0, "quotes_added": 0,
              "rejected_market_groups": 0, "duplicate_snapshots": 0}
    for name in paths:
        path = Path(name).resolve()
        if not path.is_file() or path.suffix.lower() != ".json":
            raise ValueError("Only local JSON snapshot files are accepted")
        if path in seen:
            raise ValueError("Repeated snapshot file")
        seen.add(path)
        if path.stat().st_size > 10_000_000:
            raise ValueError("Snapshot exceeds size limit")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("timestamp"), str):
            raise ValueError("Historical provider timestamp required")
        result = normalize(payload, now, historical=True, allowed_books=set(bookmakers))
        saved = store(target, result)
        counts["files"] += 1
        counts["snapshots_added"] += saved["snapshots_added"]
        counts["quotes_added"] += saved["quotes_added"]
        counts["rejected_market_groups"] += len(result["rejected"])
        counts["duplicate_snapshots"] += int(saved["status"] == "DUPLICATE_SNAPSHOT")
    return {"status": STATUS, **counts, "private_vault": True,
            "historical_retrieval_after_decision_must_not_be_live": True,
            "true_opening_or_closing_lines_verified": False,
            "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--vault", default=str(default_path()))
    p.add_argument("--retrieved-at")
    p.add_argument("snapshots", nargs="+")
    args = p.parse_args()
    print(json.dumps(ingest(args.snapshots, args.vault, args.retrieved_at), indent=2))

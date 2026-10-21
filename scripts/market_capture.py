"""Explicit/manual FanDuel capture to a LOCAL private quote vault.

There is NO background schedule, GitHub Actions job, purchase, or bet placement.
Never print API credentials or bookmaker selections/prices.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
from scripts.game_context import parse_time
from scripts.market_client import fetch
from scripts.market_quotes import normalize
from scripts.market_vault import default_path,store

def capture(vault_path=None,bookmakers="fanduel",fixture_path=None,
            execute_network=False,historical_date=None,acknowledge_paid_historical=False,
            retrieved_at_utc=None,fetcher=fetch):
    if not bookmakers or any(not b or not b.replace("_","").isalnum()
                              for b in bookmakers.split(",")):
        raise ValueError("Invalid bookmaker keys")
    books=set(bookmakers.split(","))
    if fixture_path and execute_network:
        raise ValueError("Choose offline fixture OR explicit provider fetch")
    if fixture_path:
        payload=json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        usage={}
    else:
        if not execute_network:
            raise ValueError("Network fetching disabled; pass --execute-network explicitly")
        if os.environ.get("GITHUB_ACTIONS","").lower()=="true":
            raise ValueError("Private odds captures cannot run in public GitHub Actions")
        if historical_date and not acknowledge_paid_historical:
            raise ValueError("Paid historical snapshots require explicit acknowledgement")
        api_key=os.environ.get("ODDS_API_KEY")
        if not api_key:
            raise ValueError("Configure ODDS_API_KEY privately before fetching")
        payload,usage=fetcher(api_key,bookmakers,historical_date)
    if historical_date:
        parse_time(historical_date)
    # Normalizer owns as-of provenance. A downloaded historical snapshot's
    # true observation time comes from its provider timestamp, not this clock.
    now=retrieved_at_utc or dt.datetime.now(dt.timezone.utc).isoformat()
    normalized=normalize(payload,now,historical=historical_date is not None,
                         allowed_books=books)
    saved=store(vault_path or default_path(),normalized,usage)
    return {"capture_status":saved["status"],"snapshots_added":saved["snapshots_added"],
            "quotes_added":saved["quotes_added"],
            "provider_market_rejections":len(normalized["rejected"]),
            "bookmakers_configured":sorted(books),
            "credits_remaining":usage.get("x-requests-remaining"),
            "credits_used_total":usage.get("x-requests-used"),
            "credits_last":usage.get("x-requests-last"),
            "observation_kind":"HISTORICAL_PROVIDER_SNAPSHOT" if historical_date else "LIVE_CAPTURE",
            "betting_status":"PASS_UNVALIDATED",
            "note":"Quotes are stored only in a private local vault; no model picks"}

if __name__=="__main__":
    p=argparse.ArgumentParser(description="Private, opt-in FanDuel market capture")
    p.add_argument("--vault",default=str(default_path()))
    p.add_argument("--bookmakers",default="fanduel")
    p.add_argument("--offline-json",default=None)
    p.add_argument("--execute-network",action="store_true")
    p.add_argument("--historical-date",default=None)
    p.add_argument("--acknowledge-paid-historical",action="store_true")
    a=p.parse_args()
    report=capture(vault_path=a.vault,bookmakers=a.bookmakers,
                   fixture_path=a.offline_json,execute_network=a.execute_network,
                   historical_date=a.historical_date,
                   acknowledge_paid_historical=a.acknowledge_paid_historical)
    # Only sanitized metadata is ever emitted to terminal.
    print(json.dumps(report,indent=2))

"""Step 5A offline market-data coverage audit; no API calls or credential access.

Inspect a locally held provider v4 sample against a timestamped ESPN snapshot.
Write counts and quarantine reasons only; never export licensed prices to git.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from scripts.market_quotes import normalize
from scripts.market_event_crosswalk import load_registry,crosswalk

def audit(provider_payload,espn_context,registry_path,retrieved_at_utc,
          historical=False,bookmakers=("fanduel",)):
    aliases,conflicts=load_registry(registry_path)
    normalized=normalize(provider_payload,retrieved_at_utc,historical=historical,
                         allowed_books=set(bookmakers))
    result=crosswalk(normalized,espn_context,aliases,conflicts)
    markets=Counter()
    matched_markets=Counter()
    seen_market=set()
    for quote in result["quotes"]:
        name=(quote["bookmaker"],quote["market"])
        market_key=(quote["provider_event_id"],*name)
        if market_key not in seen_market:
            markets[name]+=1
            if quote["match_status"]=="MATCHED_ASOF":
                matched_markets[name]+=1
            seen_market.add(market_key)
    result_meta={
        "status":"RESEARCH_ONLY_COVERAGE_AUDIT",
        "betting_status":"PASS_UNVALIDATED",
        "safe_for_betting":False,
        "historical_provider_snapshot":bool(historical),
        "observed_at_utc":normalized["observed_at_utc"],
        "retrieved_at_utc":normalized["retrieved_at_utc"],
        "espn_context_asof_utc":espn_context["asof_utc"],
        "source_snapshot_sha256":normalized["source_snapshot_sha256"],
        "bookmakers":sorted(bookmakers),
        "source_quarantined_quote_markets":len(normalized["rejected"]),
        "source_quote_count":len(normalized["quotes"]),
        "source_alias_collisions":len(conflicts),
        "provider_event_coverage":result["coverage"],
        "market_event_counts":[
            {"bookmaker":book,"market":market,"observed_provider_events":n,
             "matched_provider_events":matched_markets[(book,market)]}
            for (book,market),n in sorted(markets.items())],
        "limitations":"No real market odds authenticated; no verified opener/close, value estimate or bet recommendation."
    }
    return result_meta

def run(provider_path,espn_path,registry_path,output_path,retrieved_at_utc,
        historical=False,bookmakers=("fanduel",)):
    provider=json.loads(Path(provider_path).read_text(encoding="utf-8"))
    espn=json.loads(Path(espn_path).read_text(encoding="utf-8"))
    report=audit(provider,espn,registry_path,retrieved_at_utc,historical,bookmakers)
    out=Path(output_path)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--provider-payload",required=True)
    p.add_argument("--espn-context",required=True)
    p.add_argument("--alias-registry",default="data/archive/2026_team_aliases.csv")
    p.add_argument("--retrieved-at-utc",required=True)
    p.add_argument("--historical",action="store_true")
    p.add_argument("--bookmakers",default="fanduel")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    books=tuple(x.strip() for x in a.bookmakers.split(","))
    if not all(books):raise SystemExit("Invalid bookmaker selection")
    run(a.provider_payload,a.espn_context,a.alias_registry,a.output,
        a.retrieved_at_utc,a.historical,books)

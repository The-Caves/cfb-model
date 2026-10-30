"""No-charge offline importer for provider-asserted historical NCAAF props.

2026 player box scores are NOT sportsbook prop history. The Odds API v4
historical event-odds endpoint is paid; this module makes no HTTP calls.
Local SHA-256 does not independently authenticate the original provider
timestamp or freeze any retroactive prediction.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from scripts.game_context import parse_time
from scripts.player_prop_history import STATUS as PLAYER_HISTORY
from scripts.player_prop_quote_capture import normalize

STATUS="NCAAF_HISTORICAL_PROP_MARKET_COVERAGE_RESEARCH_ONLY"
BASE="https://api.the-odds-api.com/v4/historical/sports/americanfootball_ncaaf/events/"
PROVIDER="the-odds-api-v4"

def _sha(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),
        allow_nan=False).encode()).hexdigest()

def _source(url,event):
    try:
        p=urlsplit(url)
        return (p.scheme=="https" and p.netloc=="api.the-odds-api.com"
                and p.path==urlsplit(BASE+str(event)+"/odds").path
                and not p.query and not p.fragment and not p.username)
    except (ValueError,TypeError):
        return False

def audit(history,snapshots=None,fixtures=None,athletes=None,asof_utc=None,
          allowed_books=("fanduel",)):
    if (history.get("status")!=PLAYER_HISTORY or
        history.get("retrospective_first_publication_authenticated") is not False
        or history.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Expected explicitly retrospective player-box source")
    if asof_utc is None:raise ValueError("Actual audit date required")
    now=parse_time(asof_utc)
    keys=set();games=set()
    for row in history.get("rows",[]):
        if row.get("source_status")!="RETROSPECTIVE_REVISED_PLAYER_BOX_ONLY":
            raise ValueError("Unsupported player game record")
        key=(str(row["game_id"]),str(row["team_id"]),str(row["player_id"]))
        if key in keys:raise ValueError("Duplicate player game")
        keys.add(key);games.add(key[0])
    snapshots=[] if snapshots is None else snapshots
    fixtures={} if fixtures is None else fixtures
    athletes={} if athletes is None else athletes
    if not isinstance(snapshots,list) or not isinstance(fixtures,dict) or not isinstance(athletes,dict):
        raise ValueError("Invalid import manifest")
    seen=set();quotes=[];receipts=[];quarantined=[]
    for item in snapshots:
        if item.get("provider")!=PROVIDER or item.get("format")!="v4_historical_event_odds":
            raise ValueError("Not The Odds API historical EVENT odds response")
        raw=item["response"]
        if not isinstance(raw,dict) or not isinstance(raw.get("data"),dict):
            raise ValueError("Invalid historical event odds envelope")
        event=raw["data"]
        eventid=str(event.get("id",""))
        if not eventid or event.get("sport_key")!="americanfootball_ncaaf":
            raise ValueError("Historical event identity missing or wrong sport")
        if not _source(item.get("source_endpoint"),eventid):
            raise ValueError("Source must identify the official credential-free historical endpoint path")
        stamp=parse_time(raw["timestamp"])
        requested=parse_time(item["requested_snapshot_utc"])
        retrieved=parse_time(item["retrieved_at_utc"])
        if not stamp<=requested<retrieved<=now:
            raise ValueError("Historical provider time, request and retrieval out of order")
        if raw.get("previous_timestamp") is not None and parse_time(raw["previous_timestamp"])>=stamp:
            raise ValueError("Invalid preceding historical provider snapshot")
        if raw.get("next_timestamp") is not None and parse_time(raw["next_timestamp"])<=stamp:
            raise ValueError("Invalid succeeding historical provider snapshot")
        gid=str(item.get("espn_game_id",""))
        if gid not in games or gid not in fixtures:
            quarantined.append({"game_id":gid,"reason":"NO_MATCHED_PLAYER_GAME_OR_VERIFIED_FIXTURE"})
            continue
        fixture=fixtures[gid]
        if (str(fixture.get("espn_game_id"))!=gid or
            str(fixture.get("provider_event_id"))!=eventid or
            stamp>=parse_time(fixture["kickoff_utc"]) or
            requested>=parse_time(fixture["kickoff_utc"])):
            raise ValueError("Postkickoff snapshot or incorrect ESPN/provider fixture link")
        unique=(gid,eventid,stamp.isoformat())
        if unique in seen:raise ValueError("Duplicate historical snapshot")
        seen.add(unique)
        parsed=normalize(event,fixture,athletes.get(gid,{}),stamp.isoformat(),
                         allowed_books=allowed_books)
        digest=_sha(raw)
        receipts.append({"game_id":gid,"event_id":eventid,
            "provider_asserted_snapshot_utc":stamp.isoformat(),
            "requested_snapshot_utc":requested.isoformat(),
            "actually_retrieved_at_utc":retrieved.isoformat(),
            "snapshot_sha256":digest,"matched_two_sided_quotes":len(parsed["quotes"]),
            "original_snapshot_independently_authenticated":False})
        for quote in parsed["quotes"]:
            quotes.append({**quote,"historical_provider_response_sha256":digest,
                "provider_asserted_snapshot_utc":stamp.isoformat(),
                "actually_retrieved_at_utc":retrieved.isoformat(),
                "retrospective_only":True,
                "eligible_as_prospectively_frozen_forecast":False,
                "original_provider_snapshot_independently_authenticated":False})
        for issue in parsed["rejected"]:
            quarantined.append({"game_id":gid,"snapshot_utc":stamp.isoformat(),**issue})
    quote_games={r["espn_game_id"] for r in quotes}
    return {
        "status":STATUS,"season":2026,"audit_at_utc":now.isoformat(),
        "ESPN_player_box_games":len(games),
        "ESPN_player_game_rows":len(keys),
        "historical_snapshots_imported":len(receipts),
        "historical_two_sided_quote_snapshots":len(quotes),
        "ESPN_games_with_some_imported_valid_quote":len(quote_games),
        "ESPN_games_without_imported_valid_quote":len(games-quote_games),
        "observed_quote_metrics":dict(Counter(q["metric"] for q in quotes)),
        "historical_market_status":("SOME_PROVIDER_ASSERTED_SNAPSHOTS" if receipts
                                     else "HISTORICAL_BOOK_PROP_LINES_NOT_COLLECTED"),
        "total_actual_bookmaker_market_universe":None,
        "true_historical_market_coverage_fraction":None,
        "provider_original_snapshot_independently_authenticated":False,
        "retrospective_archive_receipts":receipts,
        "retrospective_bookmaker_quotes":quotes,
        "quarantined_source_items":quarantined,
        "paid_api_calls_executed":0,
        "no_lines_reconstructed_from_player_box_scores":True,
        "model_promoted":False,"safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

def run(history,output,asof,imports=None,fixtures=None,athletes=None):
    if len([x for x in (imports,fixtures,athletes) if x is not None]) not in (0,3):
        raise ValueError("Imports require fixture and pre-snapshot athlete crosswalks")
    read=lambda p:json.loads(Path(p).read_text(encoding="utf-8"))
    result=audit(read(history),read(imports) if imports else [],
                 read(fixtures) if fixtures else {},read(athletes) if athletes else {},asof)
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({"history_games":result["ESPN_player_box_games"],
          "historical_prop_quotes":result["historical_two_sided_quote_snapshots"],
          "status":result["historical_market_status"],"paid_calls":0}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True);p.add_argument("--output",required=True)
    p.add_argument("--asof",required=True)
    p.add_argument("--imports");p.add_argument("--fixtures");p.add_argument("--athletes")
    a=p.parse_args()
    run(a.history,a.output,a.asof,a.imports,a.fixtures,a.athletes)

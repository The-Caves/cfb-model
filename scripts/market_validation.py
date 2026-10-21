"""Step 5B repeatable offline end-to-end market-pipeline smoke test.

Uses wholly FABRICATED sportsbook/game data; makes zero network requests,
never reads an API key, and never writes sportsbook quote data to GitHub.
The temporary SQLite database is destroyed when this test exits.
"""
import json
import tempfile
from pathlib import Path
from scripts.market_quotes import normalize,movement
from scripts.market_event_crosswalk import crosswalk,norm
from scripts.market_vault import store,audit,asof_quotes

KICK="2026-10-24T20:00:00Z"
TIMES=("2026-10-21T17:00:00Z","2026-10-21T18:00:00Z","2026-10-21T19:00:00Z")
H="Fictional Home Institute"
A="Fictional Away Institute"
EVENT="synthetic_event_001"
ESPN_ID="synthetic_espn_game_001"

def fabricated_payload(stamp,spread,total,home_price):
    """Mock The Odds API v4 featured-markets shape, NOT actual FanDuel odds."""
    return [{"id":EVENT,"sport_key":"americanfootball_ncaaf",
             "commence_time":KICK,"home_team":H,"away_team":A,
             "bookmakers":[{"key":"fanduel","last_update":stamp,
                "markets":[
                 {"key":"spreads","outcomes":[
                     {"name":H,"point":spread,"price":-110},
                     {"name":A,"point":-spread,"price":-110}]},
                 {"key":"totals","outcomes":[
                     {"name":"Over","point":total,"price":-112},
                     {"name":"Under","point":total,"price":-108}]},
                 {"key":"h2h","outcomes":[
                     {"name":H,"price":home_price},
                     {"name":A,"price":170}]}]}]}]

def verify():
    games={"asof_utc":"2026-10-21T16:00:00Z",
           "games":[{"game_id":ESPN_ID,"home":H,"away":A,
                     "home_id":"synthetic_home","away_id":"synthetic_away",
                     "kickoff_utc":KICK,"neutral":False,"completed":False}]}
    aliases={norm(H):H,norm(A):A}
    specs=[(TIMES[0],-4.5,49.5,-190,False,TIMES[0]),
           (TIMES[1],-5.5,50.5,-210,False,TIMES[1]),
           (TIMES[2],-6.5,51.5,-220,True,"2026-10-26T12:00:00Z")]
    bundles=[]
    with tempfile.TemporaryDirectory(prefix="cfb-market-e2e-") as tmp:
        vault=Path(tmp)/"quotes.sqlite3"
        for stamp,spread,total,home_price,is_history,retrieved in specs:
            payload=fabricated_payload(stamp,spread,total,home_price)
            raw={"timestamp":stamp,"data":payload} if is_history else payload
            normalized=normalize(raw,retrieved,historical=is_history)
            joined=crosswalk(normalized,games,aliases)
            if joined["coverage"]["matched"]!=1:
                raise AssertionError("Expected one verified synthetic ESPN event")
            if len(normalized["quotes"])!=6 or len(normalized["rejected"])!=0:
                raise AssertionError("Unexpected synthetic quote normalization")
            # Store already-joined source records, retaining the original
            # snapshot hash and observed/retrieved timestamps on each row.
            validated={**normalized,"quotes":joined["quotes"]}
            stored=store(vault,validated,{"x-requests-last":30 if is_history else 3})
            if stored["snapshots_added"]!=1 or stored["quotes_added"]!=6:
                raise AssertionError("Synthetic snapshot did not persist")
            bundles.append(validated)
        repeated=store(vault,bundles[0])
        if repeated["status"]!="DUPLICATE_SNAPSHOT":
            raise AssertionError("Duplicate snapshot was not deduplicated")
        early=asof_quotes(vault,EVENT,"fanduel","SPREAD","HOME",
                          "2026-10-21T17:30:00Z")
        later=asof_quotes(vault,EVENT,"fanduel","SPREAD","HOME",
                          "2026-10-21T18:30:00Z")
        # The newest backfilled price was OBSERVED at 19:00, but only
        # RETRIEVED on October 26. It must not displace a genuinely seen
        # live quote when reconstructing a 19:30 decision.
        mixed=asof_quotes(vault,EVENT,"fanduel","SPREAD","HOME",
                          "2026-10-21T19:30:00Z")
        movement_live=movement(bundles[0]["quotes"]+bundles[1]["quotes"],
                EVENT,"fanduel","SPREAD","HOME","2026-10-21T18:30:00Z")
        started=asof_quotes(vault,EVENT,"fanduel","SPREAD","HOME",
                            "2026-10-24T20:01:00Z")
        stats=audit(vault)
        if (early["line_points"],later["line_points"],mixed["line_points"])!=(-4.5,-5.5,-5.5):
            raise AssertionError("As-of quote chronology failed")
        if (early["status"],later["status"],mixed["status"])!=(
                "OBSERVED_PRICE","OBSERVED_PRICE","OBSERVED_PRICE"):
            raise AssertionError("Live-vs-backfill source flags failed")
        if movement_live["line_movement_points"]!=-1.0:
            raise AssertionError("Incorrect same-book synthetic movement")
        if started["status"]!="GAME_ALREADY_STARTED":
            raise AssertionError("Post-kickoff quote suppression failed")
        if (stats["snapshots"],stats["quotes"])!=(3,18):
            raise AssertionError("Wrong append-only vault counts")
        # A reversed provider listing cannot be automatically matched.
        reversal=fabricated_payload(TIMES[0],-4.5,49.5,-190)
        reversal[0]["home_team"],reversal[0]["away_team"]=A,H
        reversal[0]["bookmakers"][0]["markets"][0]["outcomes"][0]["name"]=A
        reversal[0]["bookmakers"][0]["markets"][0]["outcomes"][1]["name"]=H
        reversal[0]["bookmakers"][0]["markets"][2]["outcomes"][0]["name"]=A
        reversal[0]["bookmakers"][0]["markets"][2]["outcomes"][1]["name"]=H
        reverse_normalized=normalize(reversal,TIMES[0])
        reverse_join=crosswalk(reverse_normalized,games,aliases)
        if reverse_join["coverage"]["matched"]!=0 or reverse_join["coverage"]["reasons"].get("HOME_AWAY_REVERSED")!=1:
            raise AssertionError("Reversed sportsbook matchup was misjoined")
        return {
            "validation":"SYNTHETIC_END_TO_END_PASS",
            "source":"FABRICATED_FIXTURES_NO_REAL_FANDUEL_MARKETS",
            "provider_events_matched":3,"snapshots":stats["snapshots"],
            "quote_rows":stats["quotes"],
            "duplicates_blocked":1,
            "reversed_matchups_quarantined":1,
            "chronology_verified":True,
            "retrospective_market_leakage_blocked":True,
            "same_book_line_movement_verified":True,
            "after_kickoff_prices_suppressed":True,
            "market_credits_used":0,"api_calls":0,
            "public_market_data_written":False,
            "betting_status":"PASS_UNVALIDATED",
            "safe_for_betting":False
        }

if __name__=="__main__":
    print(json.dumps(verify(),indent=2))

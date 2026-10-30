"""One-event NCAA player prop bookmaker quote capture (provided JSON only).

No paid APIs, no price invention, no name-only player identity match.
Provider player names must match an independently reviewed ESPN athlete ID.
The v4 The Odds API event-odds result may contain one/two-sided markets;
we accept only complete Over+Under pairs from the same source snapshot.
"""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from scripts.game_context import parse_time
from scripts.market_quotes import decimal_price

STATUS="NCAAF_PLAYER_PROP_SOURCE_CAPTURE_RESEARCH_ONLY"
MARKETS={
 "player_pass_yds":"passing_yards",
 "player_pass_attempts":"passing_attempts",
 "player_pass_completions":"passing_completions",
 "player_pass_tds":"passing_touchdowns",
 "player_pass_interceptions":"interceptions",
 "player_rush_yds":"rushing_yards",
 "player_rush_attempts":"rushing_attempts",
 "player_rush_tds":"rushing_touchdowns",
 "player_receptions":"receptions",
 "player_reception_yds":"receiving_yards",
 "player_reception_tds":"receiving_touchdowns",
}

def _url(value):
    try:
        p=urlsplit(value)
        return p.scheme=="https" and bool(p.hostname) and not p.username
    except (TypeError,ValueError):return False

def _number(value):
    return type(value) in (int,float) and math.isfinite(value)

def _implied(price):
    return 1/decimal_price(price)

def normalize(event,fixture,player_crosswalk,observed_at_utc,allowed_books=("fanduel",)):
    observed=parse_time(observed_at_utc)
    kickoff=parse_time(fixture["kickoff_utc"])
    if not observed<kickoff or fixture.get("home")==fixture.get("away") or not fixture.get("espn_game_id"):
        raise ValueError("Missing true pregame fixture")
    if (event.get("sport_key")!="americanfootball_ncaaf" or
        str(event.get("id"))!=str(fixture.get("provider_event_id")) or
        parse_time(event.get("commence_time"))!=kickoff or
        event.get("home_team")!=fixture.get("home") or event.get("away_team")!=fixture.get("away")):
        raise ValueError("Book event cannot be verified against specified fixture")
    if not allowed_books or not isinstance(event.get("bookmakers"),list):
        raise ValueError("Bookmakers or trusted data missing")
    sha=hashlib.sha256(json.dumps(event,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    quotes=[];rejected=[];identities=set()
    for bookmaker in event["bookmakers"]:
        if bookmaker.get("key") not in allowed_books:continue
        book=bookmaker["key"]
        try:
            if parse_time(bookmaker["last_update"])>observed:
                raise ValueError("Future bookmaker update")
        except (ValueError,TypeError,KeyError):
            rejected.append({"bookmaker":book,"reason":"UNVERIFIED_OR_FUTURE_BOOK_TIME"})
            continue
        for market in bookmaker.get("markets",[]):
            key=market.get("key")
            if key not in MARKETS:continue
            try:
                updated=parse_time(market["last_update"])
                if updated>observed:raise ValueError("Future market update")
                outcomes=market["outcomes"]
                if not isinstance(outcomes,list):raise ValueError("Missing outcomes")
            except (ValueError,TypeError,KeyError):
                rejected.append({"bookmaker":book,"market":key,"reason":"UNVERIFIED_MARKET_TIME"})
                continue
            grouped=defaultdict(list)
            for outcome in outcomes:
                if not isinstance(outcome,dict):continue
                grouped[str(outcome.get("description","")).strip()].append(outcome)
            for player_name,rows in grouped.items():
                try:
                    link=player_crosswalk.get(player_name)
                    if (not player_name or not isinstance(link,dict) or
                        not link.get("verified_espn_player_id") or
                        link.get("team") not in (fixture["home"],fixture["away"]) or
                        link.get("identity_verified") is not True or
                        not _url(link.get("source_url")) or
                        parse_time(link.get("verified_at_utc"))>observed):
                        raise ValueError("NO_PREDECISION_VERIFIED_ATHLETE_CROSSWALK")
                    if len(rows)!=2 or {r.get("name") for r in rows}!={"Over","Under"}:
                        raise ValueError("INCOMPLETE_TWO_SIDED_PROP")
                    over=next(r for r in rows if r["name"]=="Over")
                    under=next(r for r in rows if r["name"]=="Under")
                    line=over.get("point")
                    if not _number(line) or line<0 or under.get("point")!=line:
                        raise ValueError("UNMATCHED_OR_INVALID_PROP_LINE")
                    p_over=over.get("price");p_under=under.get("price")
                    if type(p_over) is not int or type(p_under) is not int:
                        raise ValueError("INVALID_MARKET_PRICES")
                    prob_o=_implied(p_over);prob_u=_implied(p_under)
                    if prob_o+prob_u<=0:
                        raise ValueError("INVALID_MARKET_PRICES")
                    ident=(book,key,str(link["verified_espn_player_id"]))
                    if ident in identities:raise ValueError("DUPLICATE_PLAYER_MARKET")
                    identities.add(ident)
                    quotes.append({
                        "status":"OBSERVED_TWO_SIDED_PREDECISION_PROP",
                        "provider":"the-odds-api-v4","bookmaker":book,
                        "espn_game_id":str(fixture["espn_game_id"]),
                        "provider_event_id":str(event["id"]),
                        "team":link["team"],"player_name":player_name,
                        "player_id":str(link["verified_espn_player_id"]),
                        "metric":MARKETS[key],"market_key":key,
                        "line":float(line),"over_american_odds":p_over,
                        "under_american_odds":p_under,
                        "implied_over_no_vig":round(prob_o/(prob_o+prob_u),6),
                        "observed_at_utc":observed.isoformat(),
                        "book_updated_at_utc":parse_time(bookmaker["last_update"]).isoformat(),
                        "market_updated_at_utc":updated.isoformat(),
                        "kickoff_utc":kickoff.isoformat(),
                        "identity_evidence_url":link["source_url"],
                        "source_snapshot_sha256":sha,
                        "betting_status":"PASS_UNVALIDATED",
                    })
                except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc:
                    rejected.append({"bookmaker":book,"market":key,
                                     "player":player_name,"reason":str(exc)})
    return {"status":STATUS,"season":2026,"observed_at_utc":observed.isoformat(),
            "espn_game_id":str(fixture["espn_game_id"]),"source_sha256":sha,
            "quotes":quotes,"rejected":rejected,"complete_player_lines":len(quotes),
            "paid_provider_call_made":False,
            "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
            "model_promoted":False}

def run(event_path,fixture_path,links_path,asof,output):
    source=json.loads(Path(event_path).read_text(encoding="utf-8"))
    fixture=json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    links=json.loads(Path(links_path).read_text(encoding="utf-8"))
    result=normalize(source,fixture,links,asof)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":STATUS,"paired_player_quotes":len(result["quotes"]),
                      "rejected":len(result["rejected"]),"model_promoted":False}))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--event",required=True);p.add_argument("--fixture",required=True)
    p.add_argument("--links",required=True);p.add_argument("--asof",required=True)
    p.add_argument("--output",required=True);a=p.parse_args()
    run(a.event,a.fixture,a.links,a.asof,a.output)

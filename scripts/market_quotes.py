"""Step 5 research-only bookmaker quote normalization and as-of line movement.

Inputs use The Odds API v4 featured-market response format. This module never
fetches odds and cannot authenticate, settle, or submit wagers. A sportsbook
quote becomes a model input only after an independently verified ESPN join.
"""
import datetime as dt
import hashlib
import json
from collections import defaultdict
from scripts.game_context import parse_time

SPORT = "americanfootball_ncaaf"
SUPPORTED = {"h2h": "MONEYLINE", "spreads": "SPREAD", "totals": "TOTAL"}
STATUS = "PASS_UNVALIDATED"

def utc(iso):
    return parse_time(iso).astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z")

def decimal_price(american):
    if type(american) is not int or (-100 < american < 100):
        raise ValueError("Invalid American odds")
    return round(1 + (american / 100 if american > 0 else 100 / -american),6)

def normalize(payload, retrieved_at_utc, historical=False, allowed_books=None):
    """Return quote rows plus quarantine and provenance; never guess an opener.

    For a paid historical response, the provider's envelope timestamp is the
    actual snapshot date. Today's retrieval of an old snapshot is NOT the
    historical availability time of that quote.
    """
    downloaded=utc(retrieved_at_utc)
    if historical:
        if (not isinstance(payload,dict) or not isinstance(payload.get("data"),list)
            or not isinstance(payload.get("timestamp"),str) or not payload["timestamp"]):
            raise ValueError("Historical response requires timestamped data envelope")
        observed=utc(payload["timestamp"])
        events=payload["data"]
    else:
        if not isinstance(payload,list):
            raise ValueError("Current response must be an event list")
        observed=downloaded
        events=payload
    if parse_time(observed)>parse_time(downloaded):
        raise ValueError("Provider snapshot cannot be later than retrieval")
    raw_sha=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    allowed=set(allowed_books) if allowed_books is not None else {"fanduel"}
    if not allowed or not all(isinstance(book,str) and book for book in allowed):
        raise ValueError("Choose explicit sportsbook keys")
    result=[];rejected=[];accepted=set()
    for event in events:
        gid=event.get("id") if isinstance(event,dict) else None
        try:
            if not isinstance(event,dict) or event.get("sport_key")!=SPORT:
                raise ValueError("Wrong sport or event structure")
            eventid=str(event["id"])
            kickoff=utc(event["commence_time"])
            home=str(event["home_team"]).strip()
            away=str(event["away_team"]).strip()
            if not eventid or not home or not away or home==away:
                raise ValueError("Invalid event identity")
            if parse_time(observed)>=parse_time(kickoff):
                raise ValueError("In-play or post-kickoff quote is not a pregame quote")
            books=event.get("bookmakers")
            if not isinstance(books,list):
                raise ValueError("Missing sportsbook list")
        except (KeyError,TypeError,ValueError) as exc:
            rejected.append({"provider_event_id":str(gid or "UNKNOWN"),"reason":str(exc)})
            continue
        for book in books:
            if not isinstance(book,dict) or book.get("key") not in allowed: continue
            bookkey=book["key"]
            for market in book.get("markets",[]):
                if not isinstance(market,dict) or market.get("key") not in SUPPORTED: continue
                kind=SUPPORTED[market["key"]]
                try:
                    updated=market.get("last_update") or book.get("last_update")
                    if updated and parse_time(updated)>parse_time(observed):
                        raise ValueError("Market update later than observed snapshot")
                    sides=market["outcomes"]
                    if not isinstance(sides,list) or len(sides)!=2:
                        raise ValueError("Missing two-sided market")
                    expected={home,away} if kind!="TOTAL" else {"Over","Under"}
                    if {item["name"] for item in sides}!=expected:
                        raise ValueError("Unrecognized market selections")
                    if kind!="MONEYLINE":
                        points=[item.get("point") for item in sides]
                        if not all(type(x) in (int,float) for x in points):
                            raise ValueError("Missing line points")
                        if kind=="SPREAD" and abs(sum(points))>1e-6:
                            raise ValueError("Sides do not have opposite spread points")
                        if kind=="TOTAL" and abs(points[0]-points[1])>1e-6:
                            raise ValueError("Over and under do not share total")
                    rows=[]
                    for side in sides:
                        price=side["price"]
                        decimal=decimal_price(price)
                        selection=("HOME" if side["name"]==home else "AWAY") if kind!="TOTAL" else side["name"].upper()
                        identity=(eventid,bookkey,kind,selection,observed)
                        if identity in accepted:
                            raise ValueError("Duplicate bookmaker-event-market-selection observation")
                        rows.append({
                            "provider":"the-odds-api-v4","sport":SPORT,
                            "provider_event_id":eventid,"espn_game_id":None,
                            "match_status":"UNMATCHED_PROVIDER_EVENT",
                            "home_team_source":home,"away_team_source":away,
                            "kickoff_utc":kickoff,"bookmaker":bookkey,
                            "market":kind,"selection":selection,
                            "line_points":float(side["point"]) if kind!="MONEYLINE" else None,
                            "american_odds":price,"decimal_odds":decimal,
                            "observed_at_utc":observed,"retrieved_at_utc":downloaded,
                            "provider_last_update_utc":utc(updated) if updated else None,
                            "observation_kind":"HISTORICAL_PROVIDER_SNAPSHOT" if historical else "LIVE_CAPTURE",
                            "quote_role":"OBSERVED_NOT_AUTHENTICATED_OPEN_OR_CLOSE",
                            "snapshot_sha256":raw_sha,"betting_status":STATUS})
                    for row in rows:
                        accepted.add((eventid,bookkey,kind,row["selection"],observed))
                    result.extend(rows)
                except (ValueError,TypeError,KeyError) as exc:
                    rejected.append({"provider_event_id":eventid,"bookmaker":bookkey,
                                     "market":kind,"reason":str(exc)})
    return {"quotes":result,"rejected":rejected,"source_snapshot_sha256":raw_sha,
            "observed_at_utc":observed,"retrieved_at_utc":downloaded,
            "market_source":"the-odds-api-v4","safe_for_betting":False,
            "betting_status":STATUS}

def movement(quotes,provider_event_id,bookmaker,market,selection,asof_utc):
    """First observed and latest pre-cutoff quote, never claim the true open."""
    asof=parse_time(asof_utc)
    matches=sorted([r for r in quotes if
        r["provider_event_id"]==provider_event_id and r["bookmaker"]==bookmaker
        and r["market"]==market and r["selection"]==selection
        and parse_time(r["observed_at_utc"])<=asof
        and parse_time(r["observed_at_utc"])<parse_time(r["kickoff_utc"])],
        key=lambda r:r["observed_at_utc"])
    if not matches:return {"status":"NO_OBSERVED_QUOTE","betting_status":STATUS}
    initial,latest=matches[0],matches[-1]
    line_change=(round(latest["line_points"]-initial["line_points"],2)
                 if initial["line_points"] is not None and latest["line_points"] is not None
                 else None)
    return {"status":"OBSERVED_ONLY","bookmaker":bookmaker,"market":market,
            "selection":selection,"first_observed_at_utc":initial["observed_at_utc"],
            "first_observed_line":initial["line_points"],
            "latest_at_utc":latest["observed_at_utc"],
            "latest_line":latest["line_points"],
            "line_movement_points":line_change,
            "first_observed_american_odds":initial["american_odds"],
            "latest_american_odds":latest["american_odds"],
            "true_opening_line_verified":False,"closing_line_verified":False,
            "betting_status":STATUS}

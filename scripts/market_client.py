"""Opt-in NCAAF market collector for The Odds API v4, FanDuel by default.

No scheduled task calls this script unless explicitly added. Read the API key
from environment only; never write its value to stdout, a file, or git.
Normalization never equates a newly fetched quote with an actual opening line.
"""
import argparse,datetime as dt,json,os,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from scripts.market_quotes import normalize
from scripts.game_context import parse_time

URL_BASE="https://api.the-odds-api.com/v4"
SPORT="americanfootball_ncaaf"
MARKETS="h2h,spreads,totals"

def build_query(key,bookmakers="fanduel",historical_date=None):
    if not isinstance(key,str) or not key.strip():
        raise ValueError("ODDS_API_KEY environment secret is required")
    if not bookmakers or any(not x.isascii() or not x.replace("_","").isalnum() for x in bookmakers.split(",")):
        raise ValueError("Invalid bookmaker list")
    if historical_date is not None:
        historical_date=parse_time(historical_date).isoformat().replace("+00:00","Z")
    params={"apiKey":key,"bookmakers":bookmakers,"markets":MARKETS,
            "oddsFormat":"american","dateFormat":"iso"}
    if historical_date:params["date"]=historical_date
    path=("/historical/sports/"+SPORT+"/odds" if historical_date else
          "/sports/"+SPORT+"/odds")
    return URL_BASE+path+"?"+urllib.parse.urlencode(params)

def fetch(key,bookmakers="fanduel",historical_date=None,timeout=20,opener=None):
    url=build_query(key,bookmakers,historical_date)
    req=urllib.request.Request(url,headers={"User-Agent":"cfb-market-research/0.1",
                                               "Accept":"application/json"})
    try:
        response=(opener or urllib.request.urlopen)(req,timeout=timeout)
        with response as stream:
            raw=stream.read(10_000_001)
            headers=stream.headers
    except urllib.error.HTTPError as exc:
        # Never expose the URL: query parameters include our secret.
        raise RuntimeError("Odds provider returned HTTP "+str(exc.code)) from None
    except (urllib.error.URLError,TimeoutError,OSError):
        raise RuntimeError("Odds provider request failed; credentials not logged") from None
    if len(raw)>10_000_000:raise ValueError("Odds payload exceeded maximum size")
    try:payload=json.loads(raw)
    except (ValueError,UnicodeDecodeError):
        raise ValueError("Invalid JSON from odds provider") from None
    counts={}
    for field in ("x-requests-remaining","x-requests-used","x-requests-last"):
        value=headers.get(field)
        if value is not None and value.isdigit():counts[field]=int(value)
    return payload,counts

def run(out,bookmakers="fanduel",historical_date=None,provider_response=None,
        retrieved_at_utc=None):
    # provider_response is only used for offline tests and fixtures.
    key=os.environ.get("ODDS_API_KEY","")
    if provider_response is None:
        payload,usage=fetch(key,bookmakers,historical_date)
    else:payload,usage=provider_response,{}
    retrieved=retrieved_at_utc or dt.datetime.now(dt.timezone.utc).isoformat()
    result=normalize(payload,retrieved,historical=bool(historical_date),
                     allowed_books=set(bookmakers.split(",")))
    result["metadata"]={
        "historical_query_at_utc":historical_date,
        "provider_usage":usage,"requested_bookmakers":bookmakers.split(","),
        "quote_count":len(result["quotes"]),"quarantined_count":len(result["rejected"]),
        "note":"No event mapped to ESPN yet; no model or bet submission"}
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--bookmakers",default="fanduel")
    parser.add_argument("--historical-date",default=None)
    args=parser.parse_args()
    run(args.output,args.bookmakers,args.historical_date)

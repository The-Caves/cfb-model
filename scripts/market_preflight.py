"""Offline cost preview for The Odds API featured markets; NEVER makes a request.

This is a conservative upper estimate, not billed credits or proof of coverage.
Only configured FEATURED markets are counted. Exact billing may differ if
requested markets have no odds available. Verify provider terms before use.
"""
import argparse,json,math
MARKETS=("h2h","spreads","totals")
def estimate(bookmakers="fanduel", markets=MARKETS, historical=False, requests=1):
    if type(requests) is not int or not 1<=requests<=100000:
        raise ValueError("Number of requests must be positive and bounded")
    if isinstance(bookmakers,str):
        bookmakers=[b.strip() for b in bookmakers.split(",")]
    if isinstance(markets,str):
        markets=[m.strip() for m in markets.split(",")]
    if not bookmakers or len(set(bookmakers))!=len(bookmakers) or any(
        not isinstance(b,str) or not b or not b.replace("_","").isalnum() for b in bookmakers
    ):
        raise ValueError("Invalid or duplicate bookmaker names")
    if not markets or len(set(markets))!=len(markets) or any(
        m not in MARKETS for m in markets
    ):
        raise ValueError("Only unique featured h2h, spreads and totals allowed")
    regions=math.ceil(len(bookmakers)/10)
    unit=10 if historical else 1
    per_call=len(markets)*regions*unit
    return {"status":"ESTIMATE_ONLY_NO_API_REQUEST","bookmakers":list(bookmakers),
            "markets":list(markets),"historical":bool(historical),
            "estimated_credits_per_request_max":per_call,
            "requests":requests,"estimated_total_credits_max":per_call*requests,
            "billing_note":"Conservative market-count upper estimate; empty markets may be cheaper.",
            "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}

if __name__=="__main__":
    p=argparse.ArgumentParser(description="Offline sportsbook quota planning")
    p.add_argument("--bookmakers",default="fanduel")
    p.add_argument("--markets",default="h2h,spreads,totals")
    p.add_argument("--historical",action="store_true")
    p.add_argument("--requests",type=int,default=1)
    a=p.parse_args()
    print(json.dumps(estimate(a.bookmakers,a.markets,a.historical,a.requests),indent=2))

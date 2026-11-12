import unittest
from scripts.free_market_capture import normalize

def payload(spread=4.5,total=51.5,provider="ESPN BET",kickoff="2026-10-25T20:00:00Z"):
    return {"events":[{"id":"123","date":kickoff,
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"displayName":"Home"}},
            {"homeAway":"away","team":{"displayName":"Away"}}],
            "odds":[{"spread":spread,"overUnder":total,"provider":{"name":provider}}]}]}]}

class FreeMarketTests(unittest.TestCase):
    def test_pregame_capture_never_guesses_home_spread(self):
        result=normalize(payload(),"2026-10-23T12:00:00Z")
        self.assertEqual(len(result["quotes"]),1)
        self.assertIsNone(result["quotes"][0]["market_home_spread"])
        self.assertEqual(result["quotes"][0]["total_points"],51.5)
        self.assertEqual(result["paid_api_calls"],0)
    def test_american_moneyline_only_observed_not_derived(self):
        p=payload(spread=None,total=None)
        offer=p["events"][0]["competitions"][0]["odds"][0]
        offer["homeTeamOdds"]={"moneyLine":-120}
        offer["awayTeamOdds"]={"moneyLine":"+100"}
        row=normalize(p,"2026-10-23T12:00:00Z")["quotes"][0]
        self.assertEqual(row["market_home_moneyline"],-120)
        self.assertEqual(row["market_away_moneyline"],100)
        self.assertIsNone(row["market_home_spread"])
        self.assertIsNone(row["total_points"])

    def test_missing_or_non_american_moneylines_are_not_synthesized(self):
        p=payload()
        offer=p["events"][0]["competitions"][0]["odds"][0]
        offer["homeTeamOdds"]={"moneyLine":"EVEN"}
        offer["awayTeamOdds"]={"moneyLine":+110}
        row=normalize(p,"2026-10-23T12:00:00Z")["quotes"][0]
        self.assertIsNone(row["market_home_moneyline"])
        self.assertEqual(row["market_away_moneyline"],110)

    def test_after_kickoff_is_not_pregame(self):
        self.assertEqual(normalize(payload(),"2026-10-26T12:00:00Z")["quotes"],[])
    def test_missing_provider_quarantined(self):
        result=normalize(payload(provider=None),"2026-10-23T12:00:00Z")
        self.assertEqual(result["quotes"],[])
        self.assertEqual(result["quarantined"][0]["reason"],"MISSING_PROVIDER")
    def test_no_market_data_is_valid_absence(self):
        self.assertEqual(normalize({"events":[]},"2026-10-23T12:00:00Z")["quotes"],[])

if __name__=="__main__":unittest.main()

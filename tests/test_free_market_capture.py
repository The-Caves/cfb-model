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
    def test_after_kickoff_is_not_pregame(self):
        self.assertEqual(normalize(payload(),"2026-10-26T12:00:00Z")["quotes"],[])
    def test_missing_provider_quarantined(self):
        result=normalize(payload(provider=None),"2026-10-23T12:00:00Z")
        self.assertEqual(result["quotes"],[])
        self.assertEqual(result["quarantined"][0]["reason"],"MISSING_PROVIDER")
    def test_no_market_data_is_valid_absence(self):
        self.assertEqual(normalize({"events":[]},"2026-10-23T12:00:00Z")["quotes"],[])

if __name__=="__main__":unittest.main()

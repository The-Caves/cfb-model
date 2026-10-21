"""No-network credit budget checks: no keys, calls, or sportsbook data."""
import json
import unittest
from scripts.market_preflight import estimate

class MarketPreflightTests(unittest.TestCase):
    def test_fanduel_one_live_request_three_featured_markets(self):
        r=estimate()
        self.assertEqual(r["estimated_credits_per_request_max"],3)
        self.assertEqual(r["estimated_total_credits_max"],3)
        self.assertEqual(r["status"],"ESTIMATE_ONLY_NO_API_REQUEST")
    def test_fanduel_historical_ten_requests(self):
        r=estimate("fanduel","h2h,spreads,totals",historical=True,requests=10)
        self.assertEqual(r["estimated_credits_per_request_max"],30)
        self.assertEqual(r["estimated_total_credits_max"],300)
        self.assertFalse(r["safe_for_betting"])
    def test_extra_provider_books_without_cross_book_mixing(self):
        r=estimate("fanduel,draftkings",markets=("spreads",),requests=5)
        self.assertEqual(r["estimated_credits_per_request_max"],1)
        self.assertEqual(r["estimated_total_credits_max"],5)
    def test_eleven_books_requires_second_group(self):
        books=",".join("book"+str(i) for i in range(11))
        self.assertEqual(estimate(books)["estimated_credits_per_request_max"],6)
    def test_no_duplicate_books_or_markets(self):
        with self.assertRaises(ValueError):estimate(bookmakers="fanduel,fanduel")
        with self.assertRaises(ValueError):estimate(markets="h2h,h2h")
    def test_invalid_and_unbounded_request_counts(self):
        for requests in (0,-1,100001,1.5,True):
            with self.subTest(requests=requests):
                with self.assertRaises(ValueError):estimate(requests=requests)
    def test_does_not_contain_secrets_or_bet_outputs(self):
        r=estimate(historical=True)
        self.assertNotIn("apiKey",json.dumps(r))
        self.assertEqual(r["betting_status"],"PASS_UNVALIDATED")
if __name__=="__main__":unittest.main()

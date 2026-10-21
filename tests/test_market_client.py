import io,json,os,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from scripts.market_client import build_query,fetch,run
from scripts.market_quotes import normalize

DATA=[{"id":"game123","sport_key":"americanfootball_ncaaf",
 "commence_time":"2026-10-24T20:00:00Z","home_team":"Test Home","away_team":"Test Away",
 "bookmakers":[{"key":"fanduel","last_update":"2026-10-21T16:59:00Z",
   "markets":[{"key":"spreads","outcomes":[
      {"name":"Test Home","point":-4.5,"price":-110},
      {"name":"Test Away","point":4.5,"price":-110}]}]}]}]
class ProviderTests(unittest.TestCase):
    def test_live_request_fanduel_only(self):
        u=build_query("secret_test_value")
        self.assertIn("/v4/sports/americanfootball_ncaaf/odds?",u)
        self.assertIn("bookmakers=fanduel",u)
        self.assertIn("markets=h2h%2Cspreads%2Ctotals",u)
    def test_historical_request_and_no_unverified_date(self):
        u=build_query("secret_test_value",historical_date="2026-10-20T16:00:00Z")
        self.assertIn("/historical/sports/americanfootball_ncaaf/odds",u)
        self.assertIn("date=2026-10-20T16%3A00%3A00Z",u)
    def test_missing_key_blocks_network(self):
        with self.assertRaises(ValueError):
            build_query("")
    def test_http_error_does_not_echo_secret(self):
        import urllib.error
        def fail(request,timeout=None):
            raise urllib.error.HTTPError(request.full_url,401,"bad",None,None)
        with self.assertRaises(RuntimeError) as ex:
            fetch("never_print_this_secret",opener=fail)
        self.assertNotIn("never_print_this_secret",str(ex.exception))
        self.assertEqual(str(ex.exception),"Odds provider returned HTTP 401")
    def test_fixture_offline_and_no_assumed_opener(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/"quotes.json"
            result=run(out,provider_response=DATA,retrieved_at_utc="2026-10-21T17:00:00Z")
            self.assertTrue(out.exists())
            self.assertEqual(len(result["quotes"]),2)
            self.assertEqual(result["quotes"][0]["bookmaker"],"fanduel")
            self.assertEqual(result["quotes"][0]["quote_role"],
                             "OBSERVED_NOT_AUTHENTICATED_OPEN_OR_CLOSE")
            self.assertEqual(result["quotes"][0]["match_status"],"UNMATCHED_PROVIDER_EVENT")
            self.assertEqual(result["betting_status"],"PASS_UNVALIDATED")
if __name__=="__main__":unittest.main()

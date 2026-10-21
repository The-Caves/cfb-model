import unittest
from scripts.market_quotes import normalize,movement,decimal_price
OBS="2026-10-21T16:00:00Z"
KICK="2026-10-24T19:00:00Z"
def fixture(spread=-4.5,book="fanduel"):
    return [{"id":"provider123","sport_key":"americanfootball_ncaaf",
     "commence_time":KICK,"home_team":"Team Home","away_team":"Team Away",
     "bookmakers":[{"key":book,"markets":[
       {"key":"h2h","last_update":"2026-10-21T15:55:00Z","outcomes":[
           {"name":"Team Home","price":-200},{"name":"Team Away","price":175}]},
       {"key":"spreads","last_update":"2026-10-21T15:55:00Z","outcomes":[
           {"name":"Team Home","point":spread,"price":-110},
           {"name":"Team Away","point":-spread,"price":-110}]},
       {"key":"totals","last_update":"2026-10-21T15:55:00Z","outcomes":[
           {"name":"Over","point":52.5,"price":-112},
           {"name":"Under","point":52.5,"price":-108}]}]}]}]
class MarketTests(unittest.TestCase):
    def test_fanduel_quotes_and_provenance(self):
        r=normalize(fixture(),OBS)
        self.assertEqual(len(r["quotes"]),6)
        self.assertEqual(r["rejected"],[])
        home=next(x for x in r["quotes"] if x["market"]=="SPREAD" and x["selection"]=="HOME")
        self.assertEqual((home["line_points"],home["american_odds"]),(-4.5,-110))
        self.assertEqual(home["match_status"],"UNMATCHED_PROVIDER_EVENT")
        self.assertEqual(home["observation_kind"],"LIVE_CAPTURE")
        self.assertEqual(r["betting_status"],"PASS_UNVALIDATED")
        self.assertAlmostEqual(decimal_price(-110),1.909091)
    def test_future_book_update_quarantined(self):
        f=fixture()
        f[0]["bookmakers"][0]["markets"][1]["last_update"]="2026-10-22T00:00:00Z"
        r=normalize(f,OBS)
        self.assertEqual(len(r["quotes"]),4)
        self.assertEqual(r["rejected"][0]["market"],"SPREAD")
    def test_inplay_is_not_pregame(self):
        r=normalize(fixture(),"2026-10-25T12:00:00Z")
        self.assertEqual(r["quotes"],[])
        self.assertTrue(r["rejected"])
    def test_historical_snapshot_provenance_separate_from_download(self):
        historic={"timestamp":OBS,"data":fixture()}
        r=normalize(historic,"2026-10-26T20:00:00Z",historical=True)
        self.assertEqual(len(r["quotes"]),6)
        self.assertEqual(r["quotes"][0]["observed_at_utc"],OBS)
        self.assertEqual(r["quotes"][0]["retrieved_at_utc"],"2026-10-26T20:00:00Z")
    def test_reject_unproven_historical_timestamp(self):
        with self.assertRaises(ValueError):
            normalize({"data":fixture()},"2026-10-26T20:00:00Z",historical=True)
    def test_invalid_spread_pairs_quarantined(self):
        f=fixture();f[0]["bookmakers"][0]["markets"][1]["outcomes"][1]["point"]=3.5
        r=normalize(f,OBS)
        self.assertEqual(len(r["quotes"]),4)
    def test_other_bookmarks_explicitly_opt_in(self):
        self.assertEqual(normalize(fixture(book="draftkings"),OBS)["quotes"],[])
        self.assertEqual(len(normalize(fixture(book="draftkings"),OBS,allowed_books={"draftkings"})["quotes"]),6)
    def test_first_seen_vs_actual_open(self):
        a=normalize(fixture(-4.5),OBS)["quotes"]
        b=normalize(fixture(-6.5),"2026-10-23T13:00:00Z")["quotes"]
        changes=movement(a+b,"provider123","fanduel","SPREAD","HOME",
                         "2026-10-23T13:30:00Z")
        self.assertEqual(changes["line_movement_points"],-2.0)
        self.assertFalse(changes["true_opening_line_verified"])
        self.assertFalse(changes["closing_line_verified"])
        self.assertEqual(movement(a+b,"provider123","fanduel","SPREAD","HOME",
                         "2026-10-21T15:00:00Z")["status"],"NO_OBSERVED_QUOTE")
    def test_american_odds_guard(self):
        with self.assertRaises(ValueError):
            decimal_price(-90)
        with self.assertRaises(ValueError):
            decimal_price(True)
if __name__=="__main__":unittest.main()

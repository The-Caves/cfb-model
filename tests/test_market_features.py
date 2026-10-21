"""Completely synthetic sportsbook feature and historical cutoff tests."""
import tempfile,unittest
from pathlib import Path
from scripts.market_quotes import normalize
from scripts.market_vault import store
from scripts.market_features import market_board,raw_implied
from scripts.market_event_crosswalk import norm
HOME,AWAY="Synthetic Home College","Synthetic Away College"
KICK="2026-10-24T20:00:00Z"
GAME={"game_id":"fake401","home":HOME,"away":AWAY,
      "home_id":"111","away_id":"222","kickoff_utc":KICK,"completed":False}
ALIASES={norm(HOME):HOME,norm(AWAY):AWAY}
def slate(asof="2026-10-21T16:00:00Z"):
    return {"asof_utc":asof,"games":[GAME]}
def fake(at="2026-10-21T17:00:00Z",spread=-4.5,home=HOME,away=AWAY,
         book="fanduel",markets=("spreads","totals","h2h"),eid="event-x"):
    options={
      "spreads":[{"name":home,"point":spread,"price":-110},
                 {"name":away,"point":-spread,"price":-110}],
      "totals":[{"name":"Over","point":50.5,"price":-112},
                {"name":"Under","point":50.5,"price":-108}],
      "h2h":[{"name":home,"price":-175},{"name":away,"price":155}]}
    return [{"id":eid,"sport_key":"americanfootball_ncaaf",
             "commence_time":KICK,"home_team":home,"away_team":away,
             "bookmakers":[{"key":book,"markets":[{"key":m,"last_update":at,
               "outcomes":options[m]} for m in markets]}]}]

class MarketFeatureTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.vault=Path(d.name)/"market.sqlite3"
    def add(self,at="2026-10-21T17:00:00Z",spread=-4.5,book="fanduel",
            markets=("spreads","totals","h2h"),retrieved=None,
            home=HOME,away=AWAY,eid="event-x",no_update=False,
            publisher_update=None):
        source=fake(at,spread,home,away,book,markets,eid)
        for market in source[0]["bookmakers"][0]["markets"]:
            if no_update:market.pop("last_update",None)
            elif publisher_update:market["last_update"]=publisher_update
        if retrieved and retrieved!=at:
            parsed=normalize({"timestamp":at,"data":source},retrieved,
                             historical=True,allowed_books={book})
        else:parsed=normalize(source,at,allowed_books={book})
        store(self.vault,parsed)
    def board(self,when="2026-10-21T18:30:00Z",**kw):
        return market_board(self.vault,slate(),ALIASES,when,**kw)
    def test_all_markets_and_no_vig(self):
        self.add()
        result=self.board()
        self.assertEqual(result["qa"]["matched_events"],1)
        self.assertEqual(len(result["events"][0]["markets"]),3)
        spread=result["events"][0]["markets"]["SPREAD"]
        self.assertEqual(spread["selections"]["HOME"]["line_points"],-4.5)
        self.assertGreater(spread["two_way_overround"],1)
        self.assertAlmostEqual(sum(spread["two_way_normalized_probabilities"].values()),1,places=6)
        self.assertTrue(result["events"][0]["all_three_markets_recent"])
        self.assertFalse(spread["true_opener_verified"])
        self.assertFalse(spread["executable_at_fanduel_verified"])
        self.assertEqual(result["betting_status"],"PASS_UNVALIDATED")
    def test_market_movement_same_book(self):
        self.add()
        self.add("2026-10-21T18:00:00Z",-6.5)
        market=self.board()["events"][0]["markets"]["SPREAD"]
        self.assertEqual(market["first_observed_reference_line"],-4.5)
        self.assertEqual(market["latest_reference_line"],-6.5)
        self.assertEqual(market["observed_line_movement_points"],-2)
    def test_never_cross_books(self):
        self.add()
        self.add(book="draftkings",spread=-10.5)
        r=self.board()
        self.assertEqual(r["events"][0]["markets"]["SPREAD"]["latest_reference_line"],-4.5)
    def test_backfilled_history_not_present_as_live(self):
        self.add(retrieved="2026-10-26T12:00:00Z")
        r=self.board()
        self.assertEqual(r["events"],[])
        self.assertEqual(r["qa"]["exclusions"]["historical_backfill_after_decision"],6)
    def test_backfill_cannot_replace_true_earlier_capture(self):
        self.add()
        self.add("2026-10-21T18:00:00Z",-7.5,
                 retrieved="2026-10-26T12:00:00Z")
        self.assertEqual(self.board()["events"][0]["markets"]["SPREAD"]["latest_reference_line"],-4.5)
    def test_future_observation_excluded(self):
        self.add()
        self.assertEqual(self.board("2026-10-21T16:30:00Z")["events"],[])
    def test_stale_quote_remains_flagged(self):
        self.add()
        r=self.board("2026-10-22T17:00:00Z")
        self.assertEqual(r["events"][0]["markets"]["SPREAD"]["status"],"STALE_OR_UNTIMED_PRICE")
        self.assertFalse(r["events"][0]["all_three_markets_recent"])
    def test_missing_markets_remain_missing(self):
        self.add(markets=("spreads",))
        r=self.board()
        self.assertEqual(r["events"][0]["missing_markets"],["MONEYLINE","TOTAL"])
    def test_reversed_site_quarantined(self):
        self.add(home=AWAY,away=HOME)
        r=self.board()
        self.assertEqual(r["events"],[])
        self.assertEqual(r["qa"]["exclusions"]["game_join_HOME_AWAY_REVERSED"],1)
    def test_espn_snapshot_after_quote_quarantined(self):
        self.add()
        r=market_board(self.vault,slate("2026-10-21T17:30:00Z"),ALIASES,
                       "2026-10-21T18:30:00Z")
        self.assertEqual(r["events"],[])
        self.assertEqual(r["qa"]["exclusions"]["no_prior_espn_context"],6)
    def test_no_events_after_game_started(self):
        self.add()
        r=self.board("2026-10-24T20:01:00Z")
        self.assertEqual(r["events"],[])
        self.assertEqual(r["qa"]["exclusions"]["game_started"],6)
    def test_missing_pub_timestamp_cannot_be_fresh(self):
        self.add(no_update=True)
        r=self.board()
        market=r["events"][0]["markets"]["SPREAD"]
        self.assertEqual(market["status"],"STALE_OR_UNTIMED_PRICE")
        self.assertIsNone(market["source_update_age_minutes"])
        self.assertFalse(r["events"][0]["all_three_markets_recent"])
    def test_old_source_update_timestamp_not_fresh_even_with_recent_capture(self):
        self.add(publisher_update="2026-10-21T10:00:00Z")
        market=self.board()["events"][0]["markets"]["SPREAD"]
        self.assertEqual(market["status"],"STALE_OR_UNTIMED_PRICE")
        self.assertGreater(market["source_update_age_minutes"],180)
    def test_conflicting_same_timestamp_quotes_do_not_create_movement(self):
        self.add(spread=-4.5)
        self.add(spread=-7.5)
        r=self.board()
        self.assertEqual(r["events"],[])
        self.assertEqual(r["qa"]["exclusions"]["contradictory_same_time_prices"],3)
    def test_implied_probability(self):
        self.assertAlmostEqual(raw_implied(-110),.52380952,places=7)
        self.assertAlmostEqual(raw_implied(150),.4,places=7)
        with self.assertRaises(ValueError):raw_implied(True)
    def test_reject_later_espn_context_than_decision(self):
        self.add()
        with self.assertRaises(ValueError):
            market_board(self.vault,slate("2026-10-22T16:00:00Z"),ALIASES,
                         "2026-10-21T18:00:00Z")
    def test_duplicate_provider_ids_matching_one_espn_game_blocked(self):
        self.add()
        self.add(eid="event-y")
        r=self.board()
        self.assertEqual(r["events"],[])
        self.assertEqual(r["qa"]["exclusions"]["ambiguous_duplicate_espn_matches"],2)
if __name__=="__main__":unittest.main()

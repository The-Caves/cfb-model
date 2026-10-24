"""Observed-market research-only board comparison safety."""
import datetime as dt
import unittest
from scripts.site_market import quote_selection,enrich
from scripts.free_market_capture import normalize

NOW=dt.datetime(2026,10,24,14,tzinfo=dt.timezone.utc)
KICK="2026-10-24T17:00:00Z"

def board():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED",
        "games":[{"game_id":"42","away_team":"Away","home_team":"Home",
          "kickoff_utc":KICK,"model_home_margin":6.0,"model_total":52.0,
          "market_home_spread":None,"market_total":None}]}

def sample(home_favorite=True,gameid="42",home="Home",away="Away",
           odds=True,spread=3.5,total=48.5):
    offer={"spread":spread,"overUnder":total,
           "provider":{"name":"Official ESPN Odds Provider"}}
    if odds:
        offer.update({"homeTeamOdds":{"favorite":home_favorite},
                      "awayTeamOdds":{"favorite":not home_favorite}})
    return {"events":[{"id":gameid,"date":KICK,"competitions":[{
        "competitors":[{"homeAway":"home","team":{"displayName":home}},
                       {"homeAway":"away","team":{"displayName":away}}],
        "odds":[offer]}]}]}

def snapshot(payload=None,when="2026-10-24T14:00:00Z"):
    return normalize(payload or sample(),when)

class WebsiteMarketTests(unittest.TestCase):
    def test_real_spread_and_total_comparison(self):
        b=quote_selection(board(),[snapshot()],NOW)
        g=b["games"][0]
        self.assertEqual(g["market_home_spread"],-3.5)
        self.assertEqual(g["market_total"],48.5)
        self.assertEqual(g["model_ats_side"],"HOME")
        self.assertEqual(g["model_ou_side"],"OVER")
        self.assertAlmostEqual(g["ats_edge_points"],2.5)
        self.assertAlmostEqual(g["ou_edge_points"],3.5)
        self.assertEqual(b["betting_status"],"PASS_UNVALIDATED")
        self.assertFalse(b["market_display"]["historical_publication_authenticated"])
    def test_opposite_ats(self):
        b=board();b["games"][0]["model_home_margin"]=2
        g=quote_selection(b,[snapshot()],NOW)["games"][0]
        self.assertEqual(g["model_ats_side"],"AWAY")
    def test_missing_favorite_flags_no_signed_spread(self):
        g=quote_selection(board(),[snapshot(sample(odds=False))],NOW)["games"][0]
        self.assertIsNone(g["market_home_spread"])
        self.assertIsNone(g["model_ats_side"])
        self.assertEqual(g["model_ou_side"],"OVER")
    def test_missing_provider_no_synthetic_prices(self):
        bad=sample();bad["events"][0]["competitions"][0]["odds"][0]["provider"]={}
        g=quote_selection(board(),[snapshot(bad)],NOW)["games"][0]
        self.assertIsNone(g["market_home_spread"])
        self.assertIsNone(g["market_total"])
    def test_wrong_matchup_id_rejected(self):
        for p in [sample(home="Other"),sample(gameid="99")]:
            g=quote_selection(board(),[snapshot(p)],NOW)["games"][0]
            self.assertIsNone(g["market_home_spread"])
    def test_future_observation_rejected(self):
        with self.assertRaises(ValueError):
            quote_selection(board(),[snapshot(when="2026-10-24T14:10:00Z")],NOW)
    def test_post_kickoff_absent(self):
        self.assertEqual(snapshot(when="2026-10-24T18:00:00Z")["quotes"],[])
    def test_paid_snapshot_blocked(self):
        s=snapshot();s["paid_api_calls"]=1
        with self.assertRaises(ValueError):quote_selection(board(),[s],NOW)
    def test_market_missing_does_not_invent_pick(self):
        g=quote_selection(board(),[],NOW)["games"][0]
        self.assertIsNone(g["model_ats_side"])
        self.assertIsNone(g["model_ou_side"])
        self.assertEqual(g["market_status"],"NO_OBSERVED_VALID_PREGAME_QUOTE")

if __name__=="__main__":
    unittest.main()

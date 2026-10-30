import unittest
from scripts.player_prop_history import from_box_rows
from scripts.player_prop_historical_market import audit

KICK="2026-10-10T20:00:00Z"
STAMP="2026-10-09T20:00:00Z"
NOW="2026-10-30T22:00:00Z"

def history():
    g={"100":{"game_id":"100","date":"2026-10-10","kickoff_utc":KICK,"home":"A","away":"B"}}
    return from_box_rows([{"game_id":"100","team_id":10,"athlete_id":22,
       "athlete_name":"Receiver One","season":2026,"category":"receiving",
       "receptions":"4","receivingYards":"73","receivingTouchdowns":"1"}],g,
       "2026-10-30T15:00:00Z")
def fixture():
    return {"100":{"espn_game_id":"100","provider_event_id":"evt100",
                    "home":"A","away":"B","kickoff_utc":KICK}}
def identity():
    return {"100":{"Receiver One":{"verified_espn_player_id":"22",
       "team":"A","identity_verified":True,
       "verified_at_utc":"2026-10-09T13:00:00Z",
       "source_url":"https://example.edu/official-player-roster"}}}
def export():
    return {"provider":"the-odds-api-v4","format":"v4_historical_event_odds",
      "espn_game_id":"100",
      "source_endpoint":"https://api.the-odds-api.com/v4/historical/sports/americanfootball_ncaaf/events/evt100/odds",
      "requested_snapshot_utc":"2026-10-09T20:05:00Z",
      "retrieved_at_utc":"2026-10-30T19:00:00Z",
      "response":{"timestamp":STAMP,"previous_timestamp":"2026-10-09T19:55:00Z",
        "data":{"id":"evt100","sport_key":"americanfootball_ncaaf",
          "home_team":"A","away_team":"B","commence_time":KICK,
          "bookmakers":[{"key":"fanduel","last_update":STAMP,
            "markets":[{"key":"player_reception_yds","last_update":STAMP,
              "outcomes":[
                {"name":"Over","description":"Receiver One","point":52.5,"price":-110},
                {"name":"Under","description":"Receiver One","point":52.5,"price":-110}
              ]}]}]}}}

class HistoricalPropTests(unittest.TestCase):
    def test_missing_market_history_is_not_inferred_from_boxes(self):
        x=audit(history(),asof_utc=NOW)
        self.assertEqual(x["historical_two_sided_quote_snapshots"],0)
        self.assertEqual(x["ESPN_games_without_imported_valid_quote"],1)
        self.assertIsNone(x["true_historical_market_coverage_fraction"])
        self.assertEqual(x["historical_market_status"],"HISTORICAL_BOOK_PROP_LINES_NOT_COLLECTED")

    def test_imported_provider_claim_keeps_retrieval_clock_distinct(self):
        x=audit(history(),[export()],fixture(),identity(),NOW)
        self.assertEqual(x["historical_two_sided_quote_snapshots"],1)
        q=x["retrospective_bookmaker_quotes"][0]
        self.assertEqual(q["line"],52.5)
        self.assertEqual(q["implied_over_no_vig"],.5)
        self.assertEqual(q["player_id"],"22")
        self.assertEqual(q["provider_asserted_snapshot_utc"],"2026-10-09T20:00:00+00:00")
        self.assertEqual(q["actually_retrieved_at_utc"],"2026-10-30T19:00:00+00:00")
        self.assertFalse(q["eligible_as_prospectively_frozen_forecast"])
        self.assertEqual(x["paid_api_calls_executed"],0)

    def test_late_player_identity_is_quarantined(self):
        d=identity();d["100"]["Receiver One"]["verified_at_utc"]="2026-10-30T18:00:00Z"
        x=audit(history(),[export()],fixture(),d,NOW)
        self.assertEqual(len(x["retrospective_bookmaker_quotes"]),0)
        self.assertEqual(len(x["quarantined_source_items"]),1)

    def test_postkickoff_provider_snapshot_is_not_pregame(self):
        d=export();d["response"]["timestamp"]="2026-10-10T20:05:00Z"
        d["requested_snapshot_utc"]="2026-10-10T20:10:00Z"
        with self.assertRaises(ValueError):
            audit(history(),[d],fixture(),identity(),NOW)

    def test_bad_provider_or_duplicate_snapshot_rejected(self):
        d=export();d["source_endpoint"]="https://evil.example/odds"
        with self.assertRaises(ValueError):
            audit(history(),[d],fixture(),identity(),NOW)
        d=export()
        with self.assertRaises(ValueError):
            audit(history(),[d,d],fixture(),identity(),NOW)

    def test_future_retrieval_and_no_verified_fixture_rejected_or_quarantined(self):
        d=export();d["retrieved_at_utc"]="2026-11-01T00:00:00Z"
        with self.assertRaises(ValueError):
            audit(history(),[d],fixture(),identity(),NOW)
        x=audit(history(),[export()],{},identity(),NOW)
        self.assertEqual(x["historical_two_sided_quote_snapshots"],0)
        self.assertEqual(x["quarantined_source_items"][0]["reason"],
                         "NO_MATCHED_PLAYER_GAME_OR_VERIFIED_FIXTURE")

if __name__=="__main__":
    unittest.main()

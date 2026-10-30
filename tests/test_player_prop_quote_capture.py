import copy
import unittest
from scripts.player_prop_quote_capture import normalize

NOW="2026-10-30T18:00:00Z"
KICK="2026-10-31T20:00:00Z"
def fixture():
    return {"espn_game_id":"123","provider_event_id":"x88",
       "home":"Team A","away":"Team B","kickoff_utc":KICK}
def links():
    return {"Receiver One":{"verified_espn_player_id":"9001",
        "team":"Team A","identity_verified":True,
        "verified_at_utc":"2026-10-30T17:00:00Z",
        "source_url":"https://example.edu/roster"}}
def event():
    return {"id":"x88","sport_key":"americanfootball_ncaaf",
      "home_team":"Team A","away_team":"Team B","commence_time":KICK,
      "bookmakers":[{"key":"fanduel","last_update":"2026-10-30T17:00:00Z",
      "markets":[{"key":"player_reception_yds",
        "last_update":"2026-10-30T17:00:00Z",
        "outcomes":[
            {"name":"Over","description":"Receiver One","point":65.5,"price":-110},
            {"name":"Under","description":"Receiver One","point":65.5,"price":-110}
        ]}]}]}
class QuoteTests(unittest.TestCase):
    def test_market_two_sides_observed_and_player_verified(self):
        result=normalize(event(),fixture(),links(),NOW)
        self.assertEqual(result["complete_player_lines"],1)
        quote=result["quotes"][0]
        self.assertEqual(quote["metric"],"receiving_yards")
        self.assertEqual(quote["player_id"],"9001")
        self.assertEqual(quote["implied_over_no_vig"],.5)
        self.assertFalse(result["model_promoted"])
        self.assertFalse(result["paid_provider_call_made"])

    def test_no_team_id_or_future_crosswalk_quarantines(self):
        l=links();l["Receiver One"]["identity_verified"]=False
        result=normalize(event(),fixture(),l,NOW)
        self.assertEqual(result["complete_player_lines"],0)
        l=links();l["Receiver One"]["verified_at_utc"]=KICK
        self.assertEqual(normalize(event(),fixture(),l,NOW)["complete_player_lines"],0)

    def test_incomplete_pair_or_mismatched_lines_rejected(self):
        e=event();e["bookmakers"][0]["markets"][0]["outcomes"].pop()
        self.assertEqual(normalize(e,fixture(),links(),NOW)["complete_player_lines"],0)
        e=event();e["bookmakers"][0]["markets"][0]["outcomes"][1]["point"]=66.5
        self.assertEqual(normalize(e,fixture(),links(),NOW)["complete_player_lines"],0)

    def test_kickoff_event_identity_or_future_quote_blocks(self):
        e=event();e["id"]="wrong"
        with self.assertRaises(ValueError):
            normalize(e,fixture(),links(),NOW)
        e=event();e["bookmakers"][0]["markets"][0]["last_update"]=KICK
        self.assertEqual(normalize(e,fixture(),links(),NOW)["complete_player_lines"],0)

    def test_unsupported_market_rejected_without_guessing_line(self):
        e=event();e["bookmakers"][0]["markets"][0]["key"]="player_anytime_td"
        result=normalize(e,fixture(),links(),NOW)
        self.assertEqual(len(result["quotes"]),0)

if __name__=="__main__":
    unittest.main()

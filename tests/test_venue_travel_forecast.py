import datetime as dt,unittest
from scripts.venue_travel_forecast import fixture_trip
def past(i,day,team,away,tid,aid,city,state):
    return {"game_id":str(i),"kickoff_utc":day+"T16:00:00Z","home":team,
      "away":away,"home_id":tid,"away_id":aid,"city":city,"state":state,
      "country":"USA","completed":True,"neutral":False}
class TravelShadowTests(unittest.TestCase):
    def test_cross_country_ranks_distance_and_body_clock(self):
        now=dt.datetime(2026,10,31,16,tzinfo=dt.timezone.utc)
        homes={"1":{"city":"Raleigh","state":"NC","country":"USA"},
               "2":{"city":"Los Angeles","state":"CA","country":"USA"}}
        geo={("Raleigh","NC","USA"):{"latitude":35.78,"longitude":-78.64,"timezone":"America/New_York"},
             ("Los Angeles","CA","USA"):{"latitude":34.05,"longitude":-118.24,"timezone":"America/Los_Angeles"}}
        game={"venue_city":"Raleigh","venue_state":"NC","home_team_id":"1",
              "away_team_id":"2","home_days_since_last_game":7,"away_days_since_last_game":7}
        result=fixture_trip(game,homes,geo,now)
        self.assertEqual(result["away_timezone_shift_hours"],3.)
        self.assertEqual(result["away_body_clock_kickoff_hour"],9)
        self.assertGreater(result["away_approx_straight_line_miles"],2000)
        self.assertEqual(result["home_timezone_shift_hours"],0)
    def test_unknown_school_origin_means_no_travel_penalty(self):
        game={"venue_city":"Raleigh","venue_state":"NC","away_team_id":"99","home_team_id":"1"}
        cache={("Raleigh","NC","USA"):{"latitude":35.7,"longitude":-78.6,"timezone":"America/New_York"}}
        self.assertIsNone(fixture_trip(game,{},cache,dt.datetime.now(dt.timezone.utc)))
if __name__=="__main__":unittest.main()

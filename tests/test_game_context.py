import datetime as dt,unittest
from scripts.game_context import (build_context,extract_game,geocode_match,
                                  home_venue_city,parse_forecast)
UTC=dt.timezone.utc
def evt(game_id,kickoff,home="A",away="B",hid="1",aid="2",completed=False,
        city="Raleigh",state="NC",neutral=False,indoor=False):
    return {"id":game_id,"date":kickoff,"season":{"year":2026},
        "status":{"type":{"completed":completed}},
        "competitions":[{"neutralSite":neutral,
            "venue":{"fullName":"Example Field","indoor":indoor,
                     "address":{"city":city,"state":state,"country":"USA"}},
            "competitors":[
              {"id":hid,"homeAway":"home","team":{"displayName":home}},
              {"id":aid,"homeAway":"away","team":{"displayName":away}}]}]}
class GameContextTests(unittest.TestCase):
    def test_et_kickoff_not_utc_day(self):
        g=extract_game(evt("a","2026-10-25T01:00:00Z"))
        self.assertEqual(g["date_et"],"2026-10-24")
        self.assertEqual(g["city"],"Raleigh")
    def test_infer_home_sites_only_after_two(self):
        p=[extract_game(evt(str(i),"2026-09-0"+str(i)+"T18:00:00Z",
                            home="A",hid="1",completed=True)) for i in (1,2)]
        self.assertEqual(home_venue_city(p)["1"]["home_games_supporting"],2)
        self.assertNotIn("2",home_venue_city(p))
    def test_geocode_filters_wrong_state(self):
        options=[{"name":"Raleigh","admin1":"West Virginia","country_code":"US","latitude":35,"longitude":-81},
                 {"name":"Raleigh","admin1":"North Carolina","country_code":"US","latitude":35.78,"longitude":-78.64}]
        geo=geocode_match(options,"Raleigh","NC")
        self.assertEqual(geo["latitude"],35.78)
        self.assertEqual(geo["precision"],"CITY_CENTROID_NOT_STADIUM_COORDINATE")
    def test_weather_missing_does_not_mean_no_rain(self):
        hourly={"time":["2026-10-24T16:00"],
                "temperature_2m":[None],"wind_speed_10m":[None]}
        self.assertIsNone(parse_forecast(hourly,dt.datetime(2026,10,24,16,tzinfo=UTC)))
    def test_future_context_rest_travel_and_unknown_player_coverage(self):
        old=[extract_game(evt(str(i),"2026-10-0"+str(i)+"T16:00:00Z",
                    home="A",hid="1",away="B",aid="2",city="Raleigh",completed=True))
             for i in (1,2)]
        old += [extract_game(evt("c"+str(i),"2026-10-0"+str(i)+"T16:00:00Z",
                    home="B",hid="2",away="C",aid="3",city="Charlotte",completed=True))
             for i in (3,4)]
        new=extract_game(evt("future","2026-10-24T16:00:00Z",home="A",away="B"))
        def geo(city,state,country):
            return {"latitude":35.78 if city=="Raleigh" else 35.22,
                    "longitude":-78.64 if city=="Raleigh" else -80.84,
                    "precision":"CITY_CENTROID_NOT_STADIUM_COORDINATE"}
        def personnel(game,issue):
            return {"coverage_status":"UNKNOWN","confirmed_qb_starters":{},
                    "injuries":[],"warnings":["Missing sourced injury reports"]}
        rows,qa=build_context([new],old,"2026-10-21T12:00:00Z",
            geo,lambda place,kickoff:{"wind_mph":15,"temperature_f":60},personnel)
        self.assertEqual(len(rows),1)
        self.assertGreater(rows[0]["away_approx_straight_line_miles"],0)
        self.assertEqual(rows[0]["home_approx_straight_line_miles"],0)
        self.assertGreater(rows[0]["away_days_since_last_game"],0)
        self.assertEqual(qa["both_rest_available"],1)
        self.assertEqual(qa["personnel_verified_both_teams"],0)
        self.assertFalse(rows[0]["safe_for_betting"])
if __name__=="__main__":unittest.main()

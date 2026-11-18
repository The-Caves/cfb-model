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
    def test_geocode_preserves_valid_city_timezone_and_rejects_unsupported(self):
        base={"name":"Tucson","admin1":"Arizona","country_code":"US",
              "latitude":32.22,"longitude":-110.97}
        good=geocode_match([dict(base,timezone="America/Phoenix")],"Tucson","AZ")
        self.assertEqual(good["timezone"],"America/Phoenix")
        bad=geocode_match([dict(base,timezone="PST")],"Tucson","AZ")
        self.assertIsNone(bad["timezone"])

    def test_long_haul_direction_and_body_clock_from_observed_named_zones(self):
        old=[]
        for i in (1,2):
            old.append(extract_game(evt("la"+str(i),"2026-10-0"+str(i)+"T17:00:00Z",
                   home="B",hid="2",away="X",aid="7",city="Los Angeles",state="CA",completed=True)))
            old.append(extract_game(evt("nc"+str(i),"2026-10-0"+str(i)+"T17:00:00Z",
                   home="A",hid="1",away="Z",aid="8",city="Raleigh",state="NC",completed=True)))
        new=extract_game(evt("long","2026-10-24T16:00:00Z",home="A",away="B"))
        def geocode(city,state,country):
            return {"latitude":34.05 if city=="Los Angeles" else 35.78,
                    "longitude":-118.24 if city=="Los Angeles" else -78.64,
                    "timezone":"America/Los_Angeles" if city=="Los Angeles" else "America/New_York",
                    "precision":"CITY_CENTROID_NOT_STADIUM_COORDINATE"}
        def injury(g,when):
            return {"coverage_status":"UNKNOWN","confirmed_qb_starters":{},"injuries":[],"warnings":[]}
        rows,coverage=build_context([new],old,"2026-10-22T12:00:00Z",geocode,
                                     lambda geo,kickoff:None,injury)
        r=rows[0]
        self.assertEqual(r["away_timezone_shift_hours"],3)
        self.assertEqual(r["away_travel_direction"],"EAST")
        self.assertEqual(r["away_body_clock_kickoff_hour"],9)
        self.assertEqual(r["home_timezone_shift_hours"],0)
        self.assertGreater(r["away_approx_straight_line_miles"],2000)
        self.assertEqual(coverage["away_cross_zone_trips"],1)

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
        self.assertEqual(rows[0]["injury_coverage_by_team"],{"A":"UNKNOWN","B":"UNKNOWN"})
    def test_espn_tbd_championship_slots_never_enter_two_team_context(self):
        # Nov 18 live ESPN archive had eight TBD/TBD and four fixed/TBD games.
        # Do NOT map a placeholder to a real team's QB, injury or market line.
        future="2026-11-28T05:00:00Z"
        for gid in range(401934095,401934103):
            self.assertIsNone(extract_game(evt(str(gid),future,
                home="TBD",away="TBD",hid="-1",aid="-2")))
        for unknown in ("TBD","TBA","to be determined"," TO BE ANNOUNCED "):
            self.assertIsNone(extract_game(evt("401860926",future,
                home="Colorado State Rams",away=unknown,hid="36",aid="-2")))
            self.assertIsNone(extract_game(evt("other",future,
                home=unknown,away="Fresno State Bulldogs",hid="-1",aid="278")))
        # Negative IDs are synthetic even if a provider changes display names.
        self.assertIsNone(extract_game(evt("a",future,
            home="Unnamed Team",away="Real Team",hid="-1",aid="278")))
        self.assertIsNone(extract_game(evt("b",future,
            home="Real Team",away="Other Real Team",hid="20",aid="-2")))
        self.assertIsNone(extract_game(evt("c",future,
            home="Same",away="Same",hid="20",aid="21")))
        actual=extract_game(evt("real",future,
            home="Colorado State Rams",away="Fresno State Bulldogs",
            hid="36",aid="278"))
        self.assertEqual((actual["home"],actual["away"]),
            ("Colorado State Rams","Fresno State Bulldogs"))
        # A future valid school whose proper name includes TBD is not a
        # known ESPN generic placeholder.
        self.assertIsNotNone(extract_game(evt("named",future,
            home="TBD State College",away="Other School",
            hid="888",aid="889")))

    def test_review_queue_does_not_duplicate_unknown_teams_after_normalization(self):
        from scripts.qb_review_queue import build_queue
        future="2026-11-28T05:00:00Z"
        raw=[evt("real",future,home="A",away="B",hid="10",aid="11")]
        raw.extend(evt(str(i),future,home="TBD",away="TBD",
                       hid="-1",aid="-2") for i in range(8))
        real=[g for g in (extract_game(event) for event in raw) if g is not None]
        def personnel(g,when):
            return {"coverage_status":"UNKNOWN","confirmed_qb_starters":{},
                    "injuries":[],"warnings":[]}
        context,_=build_context(real,[],"2026-11-18T13:00:00Z",
            lambda *args:None,lambda *args:None,personnel)
        news={"manifest":{"status":"OFFICIAL_NEWS_REVIEW_ONLY",
                 "asof_utc":"2026-11-18T13:00:00Z","feed_status":{}},
              "candidates":[]}
        q=build_queue({"games":context},news,"2026-11-18T13:01:00Z")
        self.assertEqual(q["summary"]["team_game_slots"],2)
        self.assertEqual({r["team"] for r in q["rows"]},{"A","B"})
        self.assertEqual(len({(r["game_id"],r["team"]) for r in q["rows"]}),2)

if __name__=="__main__":unittest.main()

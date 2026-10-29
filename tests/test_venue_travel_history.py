import datetime as dt
import unittest
from scripts.venue_travel_history import reconstruct,STATUS

def event(i,date,home,away,home_id,away_id,city,state):
    return {"game_id":str(i),"date_et":date,"kickoff_utc":date+"T16:00:00Z",
       "home":home,"away":away,"home_id":home_id,"away_id":away_id,
       "neutral":False,"completed":True,"city":city,"state":state,"country":"USA"}
def game(e):
    return {"game_id":e["game_id"],"date":e["date_et"],
       "kickoff_utc":e["kickoff_utc"],"home":e["home"],"away":e["away"],"neutral":"False"}
def geo():
    return {("Raleigh","NC","USA"):{"latitude":35.78,"longitude":-78.64,"timezone":"America/New_York"},
       ("Los Angeles","CA","USA"):{"latitude":34.05,"longitude":-118.24,"timezone":"America/Los_Angeles"}}

class HistoricalTravelTests(unittest.TestCase):
    def make(self):
        events=[]
        for d in (1,8,15):
            day=(dt.date(2026,9,1)+dt.timedelta(days=d-1)).isoformat()
            events.append(event(d,day,"A","X","1","3","Raleigh","NC"))
            events.append(event(d+100,day,"B","Y","2","4","Los Angeles","CA"))
        events.append(event(400,"2026-09-22","A","B","1","2","Raleigh","NC"))
        return events
    def test_past_only_two_home_games_before_cross_country_trip(self):
        ev=self.make()
        out=reconstruct([game(e) for e in ev],ev,geo(),"2026-09-23T02:00:00Z")
        self.assertEqual(out["status"],STATUS)
        trip=next(x for x in out["rows"] if x["game_id"]=="400")
        self.assertEqual(trip["audited_travel_features"]["away_eastward_hours"],3.)
        self.assertGreater(trip["audited_travel_features"]["away_minus_home_travel_1000mi"],2.)
        self.assertFalse(trip["historical_snapshot_publication_authenticated"])
        # Earliest games have no prior two-game home-base evidence.
        self.assertFalse(any(x["game_id"]=="1" for x in out["rows"]))
    def test_missing_geo_cannot_silently_be_zero_miles(self):
        ev=self.make()
        out=reconstruct([game(e) for e in ev],ev,{},"2026-09-23T02:00:00Z")
        self.assertEqual(len(out["rows"]),0)
    def test_home_venue_id_swap_and_future_sources_fail_closed(self):
        ev=self.make()
        rows=[game(e) for e in ev]
        rows[0]["home"]="Swapped"
        with self.assertRaisesRegex(ValueError,"identity mismatch"):
            reconstruct(rows,ev,geo(),"2026-09-23T02:00:00Z")
        with self.assertRaisesRegex(ValueError,"Future"):
            reconstruct([game(e) for e in ev],ev,geo(),"2026-09-15T15:00:00Z")
if __name__=="__main__":unittest.main()

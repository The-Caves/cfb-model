import unittest
from scripts.context_delta import snapshot_changes
def record(gid="1",kickoff="2026-10-24T20:00:00Z",wind=12,qbs=None,injuries=None):
    return {"game_id":gid,"kickoff_utc":kickoff,"home":"H","away":"A",
      "wind_mph":wind,"weather_status":"LIVE_FORECAST",
      "verified_qb_starters":qbs or {},"injury_reports":injuries or [],
      "injury_report_status":"UNKNOWN"}
def snap(asof,games):return {"asof_utc":asof,"games":games}
class DeltaTests(unittest.TestCase):
    def test_first_snapshot_does_not_invent_changes(self):
        x,freeze,qa=snapshot_changes(None,snap("2026-10-23T15:00:00Z",[record()]),"2026-10-23T15:00:00Z")
        self.assertEqual((len(x),len(freeze)),(0,0))
    def test_weather_significance(self):
        t="2026-10-23T16:00:00Z"
        old=snap("2026-10-23T15:00:00Z",[record(wind=10)])
        new=snap(t,[record(wind=16)])
        changes,_,_=snapshot_changes(old,new,t)
        self.assertEqual([x["kind"] for x in changes],["SIGNIFICANT_NUMERIC_FORECAST_CHANGE"])
    def test_weather_source_outage_is_one_coverage_event(self):
        old=snap("2026-10-23T15:00:00Z",[dict(record(),gust_mph=20,temperature_f=70,precip_probability_pct=30)])
        new=snap("2026-10-23T16:00:00Z",[dict(record(),weather_status="UNAVAILABLE_FORECAST",wind_mph=None,gust_mph=None,temperature_f=None,precip_probability_pct=None)])
        changes,_,_=snapshot_changes(old,new,"2026-10-23T16:00:00Z")
        self.assertEqual(len(changes),1)
        self.assertEqual(changes[0]["kind"],"WEATHER_COVERAGE_CHANGED")
    def test_missing_report_not_player_recovered(self):
        old=snap("2026-10-23T15:00:00Z",[record(injuries=[{"team":"H","player":"One","status":"OUT","source_url":"https://example.com"}])])
        new=snap("2026-10-23T16:00:00Z",[record()])
        changes,_,_=snapshot_changes(old,new,"2026-10-23T16:00:00Z")
        self.assertEqual(changes[0]["kind"],"PLAYER_REPORT_NOT_PRESENT")
        self.assertFalse(any(x["kind"]=="VERIFIED_AVAILABILITY_STATUS_CHANGE" for x in changes))
    def test_qb_change_only_sourced(self):
        qb1={"H":{"player":"Starter One","source_url":"https://school.edu/a"}}
        qb2={"H":{"player":"Starter Two","source_url":"https://school.edu/b"}}
        old=snap("2026-10-23T15:00:00Z",[record(qbs=qb1)])
        new=snap("2026-10-23T16:00:00Z",[record(qbs=qb2)])
        changes,_,_=snapshot_changes(old,new,"2026-10-23T16:00:00Z")
        self.assertEqual(changes[0]["kind"],"CONFIRMED_QB_CHANGE")
    def test_freeze_is_previous_snapshot(self):
        kickoff="2026-10-24T20:00:00Z"
        old=snap("2026-10-24T19:30:00Z",[record(kickoff=kickoff,wind=10)])
        new=snap("2026-10-24T20:30:00Z",[])
        changes,frozen,_=snapshot_changes(old,new,"2026-10-24T20:30:00Z")
        self.assertEqual(changes,[])
        self.assertEqual(len(frozen),1)
        self.assertEqual(frozen[0]["snapshot"]["wind_mph"],10)
        self.assertEqual(frozen[0]["final_pregame_snapshot_asof_utc"],old["asof_utc"])
    def test_missing_from_short_horizon_not_cancelled(self):
        old=snap("2026-10-23T15:00:00Z",[record()])
        new=snap("2026-10-23T16:00:00Z",[])
        changes,frozen,_=snapshot_changes(old,new,"2026-10-23T16:00:00Z")
        self.assertEqual((changes,frozen),([],[]))
    def test_available_roster_entry_disappearing_does_not_alert(self):
        old=snap("2026-10-23T15:00:00Z",[record(injuries=[
            {"team":"H","player":"Routine Listed Player","status":"AVAILABLE","source_url":"https://school.edu/report"}])])
        new=snap("2026-10-23T16:00:00Z",[record()])
        changes,_,qa=snapshot_changes(old,new,"2026-10-23T16:00:00Z")
        self.assertEqual(changes,[])
        self.assertEqual(qa["personnel_changes"],0)
    def test_available_player_becoming_out_is_a_status_change(self):
        old=snap("2026-10-23T15:00:00Z",[record(injuries=[
            {"team":"H","player":"Player One","status":"AVAILABLE","source_url":"https://school.edu/report"}])])
        new=snap("2026-10-23T16:00:00Z",[record(injuries=[
            {"team":"H","player":"Player One","status":"OUT","source_url":"https://school.edu/report"}])])
        changes,_,qa=snapshot_changes(old,new,"2026-10-23T16:00:00Z")
        self.assertEqual([x["kind"] for x in changes],["VERIFIED_AVAILABILITY_STATUS_CHANGE"])
        self.assertEqual(qa["personnel_changes"],1)
    def test_unavailable_player_disappearing_keeps_source_gap(self):
        old=snap("2026-10-23T15:00:00Z",[record(injuries=[
            {"team":"H","player":"Player One","status":"OUT","source_url":"https://school.edu/report"}])])
        new=snap("2026-10-23T16:00:00Z",[record()])
        changes,_,_=snapshot_changes(old,new,"2026-10-23T16:00:00Z")
        self.assertEqual([x["kind"] for x in changes],["PLAYER_REPORT_NOT_PRESENT"])

if __name__=="__main__":unittest.main()

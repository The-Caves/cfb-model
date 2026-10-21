import datetime as dt,unittest
from scripts.context_refresh_plan import decide
UTC=dt.timezone.utc
def game(hours,t):
    return {"kickoff_utc":(t+dt.timedelta(hours=hours)).isoformat(),"completed":False}
class SchedulerTests(unittest.TestCase):
    def test_baseline(self):
        t=dt.datetime(2026,10,21,10,tzinfo=UTC)
        self.assertTrue(decide(t,[])["run"])
    def test_hourly_close_game(self):
        t=dt.datetime(2026,10,21,7,tzinfo=UTC)
        self.assertEqual(decide(t,[game(5,t)])["reason"],"within_12_hours_hourly")
    def test_three_hour_tier(self):
        t=dt.datetime(2026,10,21,9,tzinfo=UTC)
        self.assertTrue(decide(t,[game(25,t)])["run"])
        t=dt.datetime(2026,10,21,8,tzinfo=UTC)
        self.assertFalse(decide(t,[game(25,t)])["run"])
    def test_probe_failure_fail_open(self):
        t=dt.datetime(2026,10,21,5,tzinfo=UTC)
        self.assertEqual(decide(t,[],False,False)["reason"],"schedule_check_failed_fails_open")
if __name__=="__main__":unittest.main()

"""V12 PIT evidence gates: do not launder retrospective observations."""
import unittest
from scripts.v12_availability_gate import snapshot, STATUS


def record(category,team,observed="2026-09-25T18:10:00Z",
           published="2026-09-25T18:00:00Z"):
    result={"game_id":"999","category":category,"team":team,
            "verification":"OFFICIAL_PRIMARY",
            "source_url":"https://example.edu/news/football-injuries",
            "first_observed_at_utc":observed,
            "source_published_at_utc":published,
            "value":{"status":"AVAILABLE"}}
    if category=="weather":result["weather_type"]="FORECAST"
    return result


class PITTests(unittest.TestCase):
    def snap(self,rows):
        return snapshot(rows,game_id="999",home="Home",away="Away",
                        asof_utc="2026-09-26T00:00:00Z")

    def test_verified_earlier_observation_kept(self):
        result=self.snap([record("qb","Home"),record("injury","Away"),
                          record("weather","GAME")])
        self.assertEqual(result["status"],STATUS)
        self.assertEqual(result["accepted_record_keys"],3)
        self.assertIsNotNone(result["evidence"]["qb"]["home"])
        self.assertIsNone(result["evidence"]["qb"]["away"])
        self.assertIsNotNone(result["evidence"]["weather"]["GAME"])
        self.assertFalse(result["score_effects_applied"])

    def test_late_sources_and_actual_weather_are_rejected(self):
        rows=[record("qb","Home",observed="2026-10-01T12:00:00Z"),
              record("injury","Away",published="2026-09-27T18:00:00Z"),
              dict(record("weather","GAME"),weather_type="ACTUAL"),
              dict(record("qb","Home"),verification="UNVERIFIED"),
              dict(record("qb","Away"),source_published_at_utc=""),
              dict(record("qb","Away"),game_id="888")]
        result=self.snap(rows)
        self.assertEqual(result["accepted_record_keys"],0)
        self.assertEqual(result["rejected_records"]["AFTER_FORECAST_CUTOFF"],2)
        self.assertEqual(result["rejected_records"]["ACTUAL_WEATHER_IS_LEAKAGE"],1)
        self.assertTrue(all(x is None for x in result["evidence"]["qb"].values()))

    def test_no_timestamp_inference_and_contradictory_sources(self):
        with self.assertRaisesRegex(ValueError,"timestamp"):
            snapshot([],game_id="999",home="Home",away="Away",
                     asof_utc="2026-09-26")
        x=record("qb","Home")
        y=dict(x,value={"status":"OUT"})
        with self.assertRaisesRegex(ValueError,"Contradictory"):
            self.snap([x,y])

if __name__=="__main__":
    unittest.main()

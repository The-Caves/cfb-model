"""No backdated weather, unverified matchup join, or simulated points on the site."""
import copy
import unittest
from scripts.site_weather import attach

NOW = "2026-11-12T15:00:00Z"
KICK = "2026-11-13T01:00:00Z"


def board():
    return {"schema_version": 2, "betting_status": "PASS_UNVALIDATED",
            "games": [{"game_id": "401", "home_team": "Home", "away_team": "Away",
                       "kickoff_utc": KICK, "v04_direct_scores": {"home_points": 24}}]}


def context():
    return {"asof_utc": "2026-11-12T14:30:00Z", "games": [
        {"game_id": "401", "home": "Home", "away": "Away", "kickoff_utc": KICK,
         "weather_status": "LIVE_FORECAST", "venue_indoor": False,
         "weather_source": "OPEN_METEO_LIVE_FORECAST",
         "forecast_issue_utc": "2026-11-12T14:25:00Z",
         "forecast_retrieved_utc": "2026-11-12T14:27:00Z",
         "weather_location_precision": "CITY_CENTROID",
         "temperature_f": 31, "wind_mph": 23, "gust_mph": 32,
         "precip_probability_pct": 75}]}


class WeatherSiteTests(unittest.TestCase):
    def test_high_impact_forecast_visible_and_scores_unchanged(self):
        b = board()
        old = copy.deepcopy(b["games"][0]["v04_direct_scores"])
        new = attach(b, context(), NOW)
        x = new["games"][0]["weather"]
        self.assertEqual(x["status"], "FORECAST")
        self.assertEqual(x["flags"], ["WIND", "PRECIPITATION", "COLD"])
        self.assertTrue(x["risk"])
        self.assertEqual(new["weather_display"]["flagged_games"], 1)
        self.assertEqual(new["games"][0]["v04_direct_scores"], old)
        self.assertFalse(new["weather_display"]["frozen_model_scores_changed"])

    def test_missing_and_wrong_game_do_not_infer_weather(self):
        for c in (None, dict(context(), games=[]),
                  dict(context(), games=[dict(context()["games"][0], home="Wrong")])):
            b = attach(board(), c, NOW)
            self.assertEqual(b["games"][0]["weather"]["status"], "UNKNOWN")

    def test_late_or_future_forecast_cannot_apply_to_game(self):
        for changes in ({"forecast_issue_utc": "2026-11-13T01:01:00Z"},
                        {"forecast_retrieved_utc": "2026-11-12T14:31:00Z"},
                        {"kickoff_utc": "2026-11-13T03:00:00Z"}):
            c = context()
            c["games"][0].update(changes)
            self.assertEqual(attach(board(), c, NOW)["games"][0]["weather"]["status"], "UNKNOWN")
        c = context()
        c["asof_utc"] = "2026-11-13T03:00:00Z"
        with self.assertRaises(ValueError):
            attach(board(), c, NOW)

    def test_indoor_requires_authentic_venue_status(self):
        c = context()
        c["games"][0].update(venue_indoor=True, weather_status="INDOOR_NOT_APPLICABLE")
        self.assertEqual(attach(board(), c, NOW)["games"][0]["weather"]["status"], "INDOOR")
        c["games"][0]["weather_status"] = "LIVE_FORECAST"
        self.assertEqual(attach(board(), c, NOW)["games"][0]["weather"]["status"], "UNKNOWN")

    def test_no_weather_source_or_unreported_rain_stays_unknown(self):
        c = context()
        c["games"][0]["weather_source"] = "UNVERIFIED"
        self.assertEqual(attach(board(), c, NOW)["games"][0]["weather"]["status"], "UNKNOWN")
        c = context()
        c["games"][0].update(temperature_f=None, wind_mph=None, gust_mph=None,
                             precip_probability_pct=None)
        self.assertEqual(attach(board(), c, NOW)["games"][0]["weather"]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

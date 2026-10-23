import copy
import unittest
from unittest.mock import patch
from scripts.weather_matchups import _interaction, build

HOME = {"recent_form": {"pass_rate": .6, "explosive_pass": .12}}
AWAY = {"recent_form": {"pass_rate": .4, "explosive_pass": .08}}
JOINED_GAME = {"team_profiles": {"home": HOME, "away": AWAY}}
WEATHER = {"weather_status": "LIVE_FORECAST", "venue_indoor": False,
           "wind_mph": 22, "precip_probability_pct": 70, "temperature_f": 32}

class WeatherMatchupTests(unittest.TestCase):
    def test_interaction_math_and_no_fixed_points(self):
        result = _interaction(WEATHER, JOINED_GAME)
        self.assertAlmostEqual(result["features"]["wind_pass_exposure"], 5.0)
        self.assertAlmostEqual(result["features"]["wind_explosive_pass_exposure"], 1.0)
        self.assertAlmostEqual(result["features"]["precip_rush_exposure"], .35)
        self.assertAlmostEqual(result["features"]["cold_pass_exposure"], 4.0)
        self.assertNotIn("point_adjustment", result)

    def test_missing_weather_is_not_zero(self):
        wx = dict(WEATHER, weather_status="UNAVAILABLE_FORECAST")
        result = _interaction(wx, JOINED_GAME)
        self.assertTrue(result["weather_missing"])
        self.assertIsNone(result["features"]["wind_pass_exposure"])

    def test_indoor_zero_requires_indoor_status(self):
        wx = dict(WEATHER, venue_indoor=True, weather_status="INDOOR_NOT_APPLICABLE")
        result = _interaction(wx, JOINED_GAME)
        self.assertEqual(result["features"]["wind_pass_exposure"], 0)
        with self.assertRaises(ValueError):
            _interaction(dict(wx, weather_status="LIVE_FORECAST"), JOINED_GAME)

    def test_actual_context_writer_omits_optional_status(self):
        joined = {"run_id": "1", "captured_at_utc": "2026-10-23T10:00:00Z",
                  "games": [dict(JOINED_GAME, game_id="1", home="Home", away="Away",
                                 kickoff_utc="2026-10-24T16:00:00Z")]}
        ctx = {"asof_utc": "2026-10-23T09:00:00Z",
               "captured_at_utc": "2026-10-23T09:01:00Z",
               "games": [dict(WEATHER, game_id="1", home="Home", away="Away",
                              kickoff_utc="2026-10-24T16:00:00Z",
                              forecast_issue_utc="2026-10-23T09:00:00Z")]}
        with patch("scripts.weather_matchups.verify_joined", return_value=None):
            report = build(joined, ctx)
        self.assertEqual(report["summary"]["games"], 1)
        self.assertFalse(report["safe_for_betting"])

    def test_rejects_future_forecast_and_wrong_game(self):
        joined = {"run_id": "1", "captured_at_utc": "2026-10-23T10:00:00Z",
                  "games": [dict(JOINED_GAME, game_id="1", home="Home", away="Away",
                                 kickoff_utc="2026-10-24T16:00:00Z")]}
        game = dict(WEATHER, game_id="1", home="Home", away="Away",
                    kickoff_utc="2026-10-24T16:00:00Z",
                    forecast_issue_utc="2026-10-23T10:02:00Z")
        ctx = {"asof_utc": "2026-10-23T09:00:00Z",
               "captured_at_utc": "2026-10-23T09:01:00Z",
               "betting_status": "PASS_UNVALIDATED", "games": [game]}
        with patch("scripts.weather_matchups.verify_joined", return_value=None):
            with self.assertRaises(ValueError):
                build(joined, ctx)
            ctx["games"][0]["forecast_issue_utc"] = "2026-10-23T09:00:00Z"
            ctx["games"][0]["away"] = "Wrong"
            with self.assertRaises(ValueError):
                build(joined, ctx)

if __name__ == "__main__":
    unittest.main()

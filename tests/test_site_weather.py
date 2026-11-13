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



    def test_fallback_restores_source_observed_conditions_after_timeout(self):
        from scripts.site_weather import restore_previous_weather
        current=context()
        current["asof_utc"]="2026-11-12T15:00:00Z"
        current["games"][0].update(weather_status="UNAVAILABLE_FORECAST",
            forecast_retrieved_utc=None, weather_source=None,
            temperature_f=None, wind_mph=None,gust_mph=None,precip_probability_pct=None)
        saved=context()
        changed=restore_previous_weather(current["games"],saved,"2026-11-12T15:10:00Z")
        self.assertEqual(changed,1)
        self.assertEqual(current["games"][0]["wind_mph"],23)
        self.assertEqual(current["games"][0]["forecast_retrieved_utc"],
                         saved["games"][0]["forecast_retrieved_utc"])
        self.assertEqual(current["games"][0]["weather_cached_from_asof_utc"],
                         saved["asof_utc"])
        result=attach(board(),current,"2026-11-12T15:12:00Z")
        self.assertEqual(result["games"][0]["weather"]["status"],"FORECAST")
        self.assertTrue(result["games"][0]["weather"]["cached"])
        self.assertEqual(result["weather_display"]["cached_forecast_games"],1)

    def test_recover_from_recent_immutable_history_if_current_missing(self):
        latest=context()
        latest["games"][0]["weather_status"]="UNAVAILABLE_FORECAST"
        latest["asof_utc"]="2026-11-12T14:56:00Z"
        result=attach(board(),latest,"2026-11-12T15:00:00Z",history=[context()])
        weather=result["games"][0]["weather"]
        self.assertEqual(weather["status"],"FORECAST")
        self.assertTrue(weather["cached"])
        self.assertEqual(weather["flags"],["WIND","PRECIPITATION","COLD"])
        self.assertEqual(result["weather_display"]["unknown_games"],0)
        self.assertEqual(result["weather_display"]["cached_forecast_games"],1)

    def test_newest_authentic_forecast_wins_over_older_saved_weather(self):
        current=context()
        current["asof_utc"]="2026-11-12T14:58:00Z"
        current["games"][0]["forecast_retrieved_utc"]="2026-11-12T14:57:00Z"
        current["games"][0]["forecast_issue_utc"]="2026-11-12T14:55:00Z"
        current["games"][0]["wind_mph"]=4
        result=attach(board(),current,"2026-11-12T15:00:00Z",history=[context()])
        self.assertEqual(result["games"][0]["weather"]["wind_mph"],4)
        self.assertFalse(result["games"][0]["weather"]["cached"])

    def test_expired_mismatched_or_postkickoff_history_never_used(self):
        from scripts.site_weather import restore_previous_weather
        latest=context()
        latest["games"]=[]
        for old in (
            dict(context(),asof_utc="2026-11-10T14:30:00Z"),
            dict(context(),games=[dict(context()["games"][0],home="Wrong")]),
            dict(context(),games=[dict(context()["games"][0],
                                      forecast_retrieved_utc="2026-11-13T01:01:00Z")]),
        ):
            self.assertEqual(
                attach(board(),latest,"2026-11-12T15:00:00Z",history=[old])
                    ["games"][0]["weather"]["status"],"UNKNOWN")
        wrong=dict(context(),games=[dict(context()["games"][0],away="Wrong")])
        missing=[dict(context()["games"][0],weather_status="UNAVAILABLE_FORECAST")]
        self.assertEqual(restore_previous_weather(missing,wrong,"2026-11-12T15:00:00Z"),0)

    def test_read_historical_gzip_snapshots_from_state_branch(self):
        import gzip,json,tempfile
        from pathlib import Path
        from scripts.site_weather import load_history
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"2026/11/12/20261112T143000Z.json.gz"
            file.parent.mkdir(parents=True)
            file.write_bytes(gzip.compress(json.dumps(context()).encode()))
            archived=load_history(tmp,"2026-11-12T15:00:00Z")
            self.assertEqual(len(archived),1)
            self.assertEqual(archived[0]["games"][0]["weather_status"],"LIVE_FORECAST")
            self.assertEqual(load_history(tmp,"2026-11-15T15:00:00Z"),[])

if __name__ == "__main__":
    unittest.main()

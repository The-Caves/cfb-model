"""Offline contract tests for the static research forecast exporter."""
import unittest
from unittest.mock import patch
from scripts.site_forecast_export import export

def fixture():
    return {
        "status":"STEP3G_PROSPECTIVE_RESEARCH_PROJECTIONS",
        "season":2026,"forecast_observed_utc":"2026-10-23T14:00:00Z",
        "model_training":{"model":"RESEARCH_TEST"},
        "games":[{
            "game_id":"test-1","away":"Fictional Away","home":"Fictional Home",
            "kickoff_utc":"2026-10-24T20:00:00Z",
            "forecast_observed_utc":"2026-10-23T14:00:00Z",
            "reported_qb_coverage":0,"verified_team_report_coverage":0,
            "projection":{"predicted_home_margin":3.5,
                          "predicted_total_points":48.0,
                          "prediction_status":"UNVALIDATED_RESEARCH_PROJECTION"}
        }]
    }

class SiteForecastExportTests(unittest.TestCase):
    @patch("scripts.site_forecast_export.verify")
    def test_exports_no_market_quote(self, verifier):
        result=export(fixture(),"2026-10-23T15:00:00Z")
        self.assertEqual(result["games"][0]["model_home_margin"],3.5)
        self.assertIsNone(result["games"][0]["market_home_spread"])
        self.assertTrue(result["research_only"])
        self.assertEqual(result["prospective_records"],{})

    @patch("scripts.site_forecast_export.verify")
    def test_rejects_after_kickoff(self, verifier):
        record=fixture()
        record["games"][0]["forecast_observed_utc"]="2026-10-25T00:00:00Z"
        with self.assertRaises(ValueError):
            export(record,"2026-10-25T01:00:00Z")

    @patch("scripts.site_forecast_export.verify")
    def test_rejects_partial_projection(self, verifier):
        record=fixture()
        record["games"][0]["projection"]["predicted_total_points"]=None
        with self.assertRaises(ValueError):
            export(record,"2026-10-23T15:00:00Z")

if __name__=="__main__":
    unittest.main()

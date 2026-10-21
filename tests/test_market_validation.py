"""End-to-end fixture validation runs without provider connections or network."""
import json
import os
import unittest
from unittest.mock import patch
from scripts.market_validation import verify

class MarketPipelineSmokeTests(unittest.TestCase):
    def test_fanduel_fixture_to_crosswalk_to_private_vault(self):
        # No ODDS_API_KEY is present and network use cannot enter this smoke.
        with patch.dict(os.environ,{"ODDS_API_KEY":"","GITHUB_ACTIONS":"true"}):
            result=verify()
        self.assertEqual(result["validation"],"SYNTHETIC_END_TO_END_PASS")
        self.assertEqual(result["provider_events_matched"],3)
        self.assertEqual(result["snapshots"],3)
        self.assertEqual(result["quote_rows"],18)
        self.assertTrue(result["retrospective_market_leakage_blocked"])
        self.assertTrue(result["same_book_line_movement_verified"])
        self.assertTrue(result["after_kickoff_prices_suppressed"])
        self.assertTrue(result["reversed_matchups_quarantined"])
        self.assertEqual(result["api_calls"],0)
        self.assertEqual(result["market_credits_used"],0)
        self.assertFalse(result["safe_for_betting"])
        self.assertNotIn("-110",json.dumps(result))
        self.assertEqual(result["betting_status"],"PASS_UNVALIDATED")
if __name__=="__main__":unittest.main()

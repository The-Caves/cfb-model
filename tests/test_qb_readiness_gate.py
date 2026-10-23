import unittest
from unittest.mock import patch
from scripts.qb_readiness_gate import assess

def sample(counts):
    return {"forecast_observed_utc":"2026-10-22T17:00:00+00:00",
            "games":[{"game_id":str(i),"home":"Home","away":"Away",
                      "kickoff_utc":"2026-10-24T17:00:00+00:00",
                      "reported_qb_coverage":n} for i,n in enumerate(counts)]}

class QBReadinessTests(unittest.TestCase):
    @patch("scripts.qb_readiness_gate.verify")
    def test_partial_coverage_never_passes(self,verify):
        result=assess(sample([0,1,2]))
        self.assertEqual(result["summary"]["both_qbs_confirmed_games"],1)
        self.assertEqual(result["summary"]["qb_slot_coverage_fraction"],0.5)
        self.assertEqual([x["personnel_ready"] for x in result["games"]],[False,False,True])
        self.assertEqual(result["games"][0]["prediction_status"],"PASS_QB_UNVERIFIED")
        self.assertFalse(result["safe_for_betting"])
    @patch("scripts.qb_readiness_gate.verify")
    def test_invalid_counts_rejected(self,verify):
        for count in (-1,3,1.5,None,True):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    assess(sample([count]))
    @patch("scripts.qb_readiness_gate.verify")
    def test_empty_slate_not_false_success(self,verify):
        result=assess(sample([]))
        self.assertIsNone(result["summary"]["fully_confirmed_fraction"])
        self.assertEqual(result["summary"]["games"],0)

if __name__=="__main__":
    unittest.main()

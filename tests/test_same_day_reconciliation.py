import unittest
from scripts.same_day_reconciliation import reconcile

def indices(captured="2026-10-22T14:03:46Z",kickoff="2026-10-22T23:00:00Z"):
    return ({"season":2026,"games":{"1":[{"home":"Home","away":"Away","kickoff_utc":kickoff,
                                         "captured_at_utc":captured}]}},
            {"season":2026,"games":{}})

class ReconciliationTests(unittest.TestCase):
    def test_same_day_capture_does_not_change_official_policy(self):
        index,outcomes=indices()
        report=reconcile(index,outcomes,"2026-10-22")
        self.assertEqual(report["summary"]["same_day_exploratory"],1)
        self.assertEqual(report["summary"]["official_backtest_eligible"],0)
        self.assertFalse(report["policy_changed"])

    def test_linked_final_does_not_promote_same_day_capture(self):
        index,outcomes=indices()
        outcomes["games"]["1"]={"home_score":20}
        report=reconcile(index,outcomes,"2026-10-22")
        self.assertEqual(report["summary"]["linked_finals"],1)
        self.assertEqual(report["summary"]["official_backtest_eligible"],0)

    def test_valid_prior_day_capture_is_separately_eligible(self):
        index,outcomes=indices("2026-10-21T17:00:00Z")
        outcomes["games"]["1"]={}
        report=reconcile(index,outcomes,"2026-10-22")
        self.assertEqual(report["summary"]["official_backtest_eligible"],1)

    def test_after_kickoff_is_never_pregame(self):
        index,outcomes=indices("2026-10-23T01:00:00Z")
        report=reconcile(index,outcomes,"2026-10-22")
        self.assertEqual(report["games"][0]["classification"],"NO_PREGAME_CAPTURE")

    def test_conflicting_identity_fails(self):
        index,outcomes=indices()
        index["games"]["1"].append(dict(index["games"]["1"][0],away="Other"))
        with self.assertRaises(ValueError):
            reconcile(index,outcomes,"2026-10-22")

if __name__=="__main__":
    unittest.main()

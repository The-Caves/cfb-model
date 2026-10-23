import unittest
from scripts.free_market_settlement_diagnostic import diagnose

class SettlementDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.row={"game_id":"123","home":"Home","away":"Away","kickoff_utc":"2026-10-24T20:00:00Z","status":"AWAITING_VERIFIED_FINAL"}
        self.matches={"rows":[self.row,dict(self.row)]}
    def test_deduplicates_forecasts(self):
        r=diagnose(self.matches,[],"2026-10-23T20:00:00Z")
        self.assertEqual(r["unique_games"],1)
        self.assertEqual(r["comparison_rows"],2)
        self.assertEqual(r["counts"]["NOT_KICKED_OFF"],1)
    def test_completed_unarchived(self):
        game=dict(self.row,home_score="20",away_score="17")
        r=diagnose(self.matches,[game],"2026-10-25T20:00:00Z")
        self.assertEqual(r["counts"]["COMPLETED_NOT_ARCHIVED"],1)
    def test_postkickoff_unreported(self):
        r=diagnose(self.matches,[],"2026-10-25T20:00:00Z")
        self.assertEqual(r["counts"]["KICKED_OFF_NO_COMPLETED_LEDGER_RESULT"],1)
    def test_completed_identity_mismatch(self):
        game=dict(self.row,home="Other",home_score="20",away_score="17")
        r=diagnose(self.matches,[game],"2026-10-25T20:00:00Z")
        self.assertEqual(r["counts"]["COMPLETED_LEDGER_IDENTITY_MISMATCH"],1)
    def test_matched(self):
        self.row["status"]="MATCHED_VERIFIED_FINAL"
        self.matches["rows"]=[self.row]
        r=diagnose(self.matches,[],"2026-10-25T20:00:00Z")
        self.assertEqual(r["counts"]["MATCHED_VERIFIED_FINAL"],1)

if __name__=="__main__":unittest.main()

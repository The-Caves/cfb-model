"""Regression checks for on-demand prediction personnel evidence labels."""
import unittest
from pathlib import Path

class TestOnDemandPersonnel(unittest.TestCase):
    def test_exposes_unverified_personnel(self):
        source=Path("scripts/on_demand_picks.py").read_text()
        self.assertIn('"qb_status":"VERIFIED_BOTH_TEAMS" if g["reported_qb_coverage"]==2',source)
        self.assertIn('"injury_status":"VERIFIED_BOTH_TEAMS" if g["verified_team_report_coverage"]==2',source)
        self.assertIn('"personnel_risk":"HIGH"',source)
        self.assertIn('"both_qbs_verified"',source)
        self.assertIn('"both_reports_verified"',source)

if __name__=="__main__":
    unittest.main()

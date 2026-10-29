import unittest
from scripts.site_matchup import overlay,STATUS
from scripts.team_matchup_intelligence import STATUS as STYLE
def board():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED",
        "games":[{"game_id":"1","away_team":"B","home_team":"A",
                  "kickoff_utc":"2026-10-31T18:00:00Z","model_home_margin":3.,
                  "model_total":44.}]}
def profile():
    return {"status":STYLE,"betting_status":"PASS_UNVALIDATED",
        "cutoff_date_exclusive":"2026-10-29",
        "profiles":{"A":{"run_off":.1},"B":{"run_off":-.2}},
        "games":[{"game_id":"1","home":"A","away":"B",
          "kickoff_utc":"2026-10-31T18:00:00Z",
          "two_way_run_pass_coverage":True,"both_turnover_records":False,
          "matchup":{"home_run_edge":.2}}]}
class SiteTeamMatchupTests(unittest.TestCase):
    def test_overlay_keeps_v03_and_pass_total_unchanged(self):
        x=overlay(board(),profile(),"2026-10-29T20:00:00Z")
        self.assertEqual(x["matchup_display"]["status"],STATUS)
        self.assertEqual(x["games"][0]["matchup_intelligence"]["matchup"]["home_run_edge"],.2)
        self.assertEqual(x["games"][0]["model_home_margin"],3.)
        self.assertEqual(x["games"][0]["model_total"],44.)
    def test_mismatched_fixture_not_plotted(self):
        p=profile();p["games"][0]["away"]="C"
        self.assertIsNone(overlay(board(),p,"2026-10-29T20:00:00Z")["games"][0]["matchup_intelligence"])
if __name__=="__main__":unittest.main()

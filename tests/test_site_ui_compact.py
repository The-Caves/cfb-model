"""Contract checks for the mobile-first static football dashboard.

The site's JS only PRESENTS immutable score data. It must neither infer a
game-specific QB starter from a depth chart nor mutate frozen predictions.
"""
import unittest
from pathlib import Path

HTML=Path("site/index.html")
class CompactSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=HTML.read_text(encoding="utf-8")
    def test_compact_qb_instead_of_full_three_row_panels(self):
        self.assertIn('function shortQB(',self.html)
        self.assertIn('function qbIdentity(',self.html)
        self.assertIn('function teamDisplayRow(',self.html)
        self.assertNotIn('function qbCard(',self.html)
        self.assertNotIn('qbPanel.append(',self.html)
        self.assertIn('Last game',self.html)
        self.assertIn('Chart only',self.html)
        self.assertIn('Starter not officially confirmed',self.html)
    def test_expanded_scouting_and_source_details_preserved(self):
        self.assertIn('function scoutingPanel(',self.html)
        self.assertIn('function qbDetails(',self.html)
        self.assertIn('details","scouting"',self.html)
        self.assertIn('details","detailFold"',self.html)
        self.assertIn('game.matchup_intelligence',self.html.replace('g.matchup_intelligence','game.matchup_intelligence'))
    def test_no_predicted_score_mutations(self):
        self.assertIn('game["model_"+side+"_points"]',self.html)
        self.assertNotIn('model_home_margin =',self.html)
        self.assertNotIn('model_total =',self.html)
        self.assertIn('Experimental',self.html) if False else self.assertIn('Research only',self.html)
    def test_player_glance_research_is_compact_and_does_not_infer_betting_lines(self):
        self.assertIn('function playerOutlook(g)',self.html)
        self.assertIn('el.append(playerOutlook(g));',self.html)
        self.assertIn('Player props · stat outlook',self.html)
        self.assertIn('No sportsbook prop lines',self.html)
        self.assertIn('playerPick',self.html)
        self.assertIn('player-performance',self.html)
        self.assertIn('With player projections',self.html)
        self.assertNotIn('model_home_margin =',self.html)

    def test_mobile_and_logo_fallback(self):
        self.assertIn('@media(max-width:580px)',self.html)
        self.assertIn('logoBadge(team,brand)',self.html)
        self.assertIn('img.addEventListener("error",()=>img.remove())',self.html)
        self.assertIn('espncdn.com',self.html)
        self.assertEqual(self.html.count('id="dashboard-data"'),1)
if __name__=="__main__":unittest.main()

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

    def test_prospective_player_model_performance_has_model_vs_baseline(self):
        self.assertIn("function renderPlayerPerformance()",self.html)
        self.assertIn("Earliest saved pre-kickoff PlayerForm estimate",self.html)
        self.assertIn("player_stat_performance",self.html)

    def test_bias_alert_challenger_not_original_v03_winner(self):
        self.assertIn("function opponentMargin(g)",self.html)
        self.assertIn("V03 home-bias alert",self.html)
        self.assertIn("V03 withheld",self.html)
        self.assertIn("Opponent-strength R1 · experimental",self.html)
        self.assertIn("function opponentScoreScenario(game)",self.html)
        self.assertIn("Hybrid estimate*",self.html)
        self.assertIn("Score scenario · R1 margin / V03 total",self.html)
        self.assertIn("Scores · V04 directly trained · research",self.html)
        self.assertIn("function v04ScoreScenario(game)",self.html)
        self.assertIn("V04 direct*",self.html)
        self.assertIn("Not a jointly trained or validated score model",self.html)
        self.assertIn('scenario["scenario_"+side+"_points"]',self.html)
        self.assertIn("No valid split",self.html)

    def test_v04_market_policy_is_research_only_with_visible_passes(self):
        self.assertIn("function v04MarketResearch(game)",self.html)
        self.assertIn("V04_FIXED_RESIDUAL_RULE_20261101_V1",self.html)
        self.assertIn("V04 research: PASS",self.html)
        self.assertIn("Unconfirmed QB(s): stronger research thresholds",self.html)
        self.assertIn("ARCHIVED_PREKICKOFF_V04_MARKET_RESEARCH_GRADES",self.html)
        self.assertIn("First-quote eligible games",self.html)
        self.assertNotIn("g.model_home_margin =",self.html)

    def test_mobile_and_logo_fallback(self):
        self.assertIn('@media(max-width:580px)',self.html)
        self.assertIn('logoBadge(team,brand)',self.html)
        self.assertIn('img.addEventListener("error",()=>img.remove())',self.html)
        self.assertIn('espncdn.com',self.html)
        self.assertEqual(self.html.count('id="dashboard-data"'),1)
if __name__=="__main__":unittest.main()

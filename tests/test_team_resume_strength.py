"""As-of SOS/SOV/SOR research features: source dates and record-quality gates."""
import copy
import unittest
from scripts.team_resume_strength import calculate,record_probability_at_least,STATUS,MIN_RATING_GAMES

def season():
    teams=["Alpha","Bravo","Charlie","Delta","Echo","Foxtrot","Golf","Hotel","India","Juliet"]
    games=[]
    for idx in range(40):
        home=teams[idx%10]
        away=teams[(idx*3+1)%10]
        if home==away:away=teams[(idx*3+2)%10]
        games.append({"game_id":str(idx),"date":f"2026-09-{1+idx//2:02d}",
                      "home":home,"away":away,
                      "home_score":str(31+idx%8),
                      "away_score":str(13+idx%7),
                      "neutral":"False"})
    return games

class AsOfResumeStrengthTests(unittest.TestCase):
    def test_tail_measures_strength_of_record_conditional_on_schedule(self):
        easy=record_probability_at_least(2,[.90,.90])
        hard=record_probability_at_least(2,[.10,.10])
        self.assertAlmostEqual(easy,.81)
        self.assertAlmostEqual(hard,.01)
        self.assertGreater(-__import__("math").log10(hard),-__import__("math").log10(easy))
        self.assertEqual(record_probability_at_least(0,[.05,.02]),1.)
        with self.assertRaises(ValueError):
            record_probability_at_least(2,[1.5,0.5])

    def test_earlier_games_only_and_future_scores_do_not_leak(self):
        games=season()
        original=calculate(games,"2026-09-20")
        modified=copy.deepcopy(games)
        for g in modified:
            if g["date"]>="2026-09-20":
                g["home_score"]="154"
                g["away_score"]="0"
        self.assertEqual(original,calculate(modified,"2026-09-20"))
        self.assertEqual(original["status"],STATUS)
        self.assertTrue(original["ready"])
        self.assertEqual(original["source_games"],38)
        self.assertFalse(original["historical_publication_verified"])
        self.assertIn("Alpha",original["teams"])

    def test_strength_fields_have_source_and_definitions(self):
        profiles=calculate(season(),"2026-09-23")
        self.assertEqual(profiles["source_games"],40)
        for team,p in profiles["teams"].items():
            self.assertEqual(p["games_before_cutoff"],len(p["historical_game_ids"]))
            self.assertEqual(p["wins_before_cutoff"]+p["losses_before_cutoff"],
                             p["games_before_cutoff"])
            self.assertGreaterEqual(p["sor_probability_avg_team_at_least_record"],0)
            self.assertLessEqual(p["sor_probability_avg_team_at_least_record"],1)
            self.assertIsInstance(p["sos_opponent_power_points"],float)
            if not p["wins_before_cutoff"]:
                self.assertIsNone(p["sov_defeated_opponent_power_points"])
            for gid in p["historical_game_ids"]:
                self.assertLess(season()[int(gid)]["date"],"2026-09-23")
        self.assertTrue(profiles["sor_definition"].startswith("-log10("))

    def test_early_schedule_and_duplicate_source_fail_safely(self):
        early=calculate(season(),"2026-09-09")
        self.assertFalse(early["ready"])
        self.assertEqual(early["teams"],{})
        dup=season()
        dup[3]["game_id"]=dup[0]["game_id"]
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            calculate(dup,"2026-09-23")

    def test_identity_wrong_season_or_invalid_result_rejected(self):
        for edit in ({"home":"Bravo","away":"Bravo"},
                     {"date":"2025-10-01"},
                     {"home_score":"900"},
                     {"neutral":"unknown"}):
            rows=season()
            rows[0].update(edit)
            with self.assertRaises(ValueError):
                calculate(rows,"2026-09-23")

if __name__=="__main__":
    unittest.main()

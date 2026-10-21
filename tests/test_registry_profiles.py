import unittest
from scripts.build_profiles import build_profiles
class RegistryProfileTests(unittest.TestCase):
    def test_registry_excludes_non_fbs_team_profile_but_keeps_opponent(self):
        game={"game_id":"1","date":"2026-09-05","away":"FCS Team","home":"FBS Team",
              "away_score":7,"home_score":35,"neutral":False}
        result=build_profiles([game],"2026-10-20",{"FBS Team"})
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["team"],"FBS Team")
        self.assertEqual(result[0]["games"],1)
        self.assertEqual(result[0]["points_for_per_game"],35)
if __name__=="__main__": unittest.main()

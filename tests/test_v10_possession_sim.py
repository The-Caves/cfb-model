"""Observed-drive V10 simulation tests. No invented possession records."""
import unittest
from scripts.v10_possession_sim import fit,simulate,outcome_distribution

def fixtures():
    games=[];advanced={}
    for i in range(44):
        day="2026-09-"+str(1+i//2).zfill(2)
        drives=[]
        for n in range(22):
            home=n%2==0
            turnover=(not home and n%7==1)
            td=(home and n%4==0)
            fg=(not home and not turnover and n%5==0)
            drives.append({"team":"Home" if home else "Away",
              "side":"home" if home else "away",
              "start_yards_to_goal":75 if n%3 else 38,
              "field_zone":"own_half" if n%3 else "opponent_half",
              "result":"INTERCEPTION" if turnover else "TD" if td else "FG" if fg else "PUNT",
              "turnover":turnover,"offense_points":7 if td else 3 if fg else 0,
              "defense_points":7 if turnover and n%19==1 else 0,
              "red_zone_visited":bool(td or fg)})
        game={"game_id":str(i),"home":"Home","away":"Away",
              "date":day,"kickoff_utc":day+"T19:00:00Z","drives":drives}
        games.append(game)
        for team in ("Home","Away"):
            advanced[(str(i),team)]={
                "off_epa_sum":"30" if team=="Home" else "-10",
                "epa_plays":"90","pass_epa_sum":"14",
                "pass_epa_plays":"45","rush_epa_sum":"-3",
                "rush_epa_plays":"45","pressure_count":"9",
                "pressure_observed":"45","redzone_success":"16",
                "redzone_plays":"30","pass_plays":"50",
                "scrimmage_plays":"90"}
    return games,advanced

class PossessionModelTests(unittest.TestCase):
    def test_prior_date_profiles_only(self):
        games,advanced=fixtures()
        target={"game_id":"999","home":"Home","away":"Away","date":"2026-10-01"}
        m=fit(games,advanced,target,min_games=35)
        self.assertTrue(m["ready"])
        self.assertEqual(m["source_prior_games"],44)
        self.assertEqual(m["prior_drives"],968)
        self.assertFalse(m["source_data_first_published_by_historical_cutoff_verified"])
        self.assertGreater(m["profiles"]["away"]["turnover_probability"],0)
        early=fit(games,advanced,dict(target,date="2026-09-03"),min_games=35)
        self.assertFalse(early["ready"])
    def test_matchup_conditions_and_normalized_risks(self):
        games,advanced=fixtures()
        m=fit(games,advanced,{"game_id":"999","home":"Home","away":"Away","date":"2026-10-01"})
        b=outcome_distribution(m,"home",45,False)
        a=outcome_distribution(m,"home",45,True)
        self.assertAlmostEqual(sum(b.values()),1,places=7)
        self.assertAlmostEqual(sum(a.values()),1,places=7)
        self.assertNotEqual(round(b["TD"],6),round(a["TD"],6))
        self.assertLess(a["TURNOVER"],1)
    def test_reproducibility_and_zero_takeaway_scenarios(self):
        games,advanced=fixtures()
        m=fit(games,advanced,{"game_id":"999","home":"Home","away":"Away","date":"2026-10-01"})
        a=simulate(m,True,trials=150,seed=991,trace=True)
        self.assertEqual(a,simulate(m,True,trials=150,seed=991,trace=True))
        self.assertEqual(a["model_variant"],"OPPONENT_EPA_PRESSURE_RZ_TURNOVER_MATCHUP")
        self.assertGreaterEqual(len(a["sample_possessions"]),14)
        self.assertLessEqual(len(a["sample_possessions"]),28)
        self.assertGreaterEqual(a["expected_home_takeaways"],0)
        self.assertLessEqual(a["prob_home_zero_takeaways"],1)
        self.assertFalse(a["model_promoted"])
    def test_not_ready_cannot_publish_probability(self):
        with self.assertRaises(ValueError):
            simulate({"ready":False},True,trials=120)

if __name__=="__main__":unittest.main()

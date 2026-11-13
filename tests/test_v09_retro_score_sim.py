import unittest
from scripts.v09_retro_score_sim import evaluate,simulate,correction
def game(n,day):
    return {"game_id":str(n),"home":"Home","away":"Away",
        "date":day,"cutoff":day,"kickoff_utc":day+"T20:00:00Z",
        "home_points":27.,"away_points":24.,"final_home":31,"final_away":19,
        "market":{"home_spread":-3.5,"total":51.5,"provider":"Book"}}
class RetroTests(unittest.TestCase):
    def test_paired_folds_and_determinism(self):
        a,b,c=game(1,"2026-10-24"),game(2,"2026-10-31"),game(3,"2026-11-07")
        out=evaluate([a,b,c],min_train=2,trials=150)
        self.assertEqual(out["eligible_games"],1)
        self.assertFalse(out["promotion_eligible"])
        self.assertEqual(out["models"]["v04"]["games"],1)
        self.assertEqual(out["models"]["v04"]["hypothetical_ats"]["losses"],1)
        self.assertEqual(simulate(c,[a,b],"team_form",150),
                         simulate(c,[a,b],"team_form",150))
    def test_same_or_later_week_blocked(self):
        a,b=game(1,"2026-10-24"),game(2,"2026-11-07")
        self.assertEqual(simulate(b,[a],"bootstrap",120)["prior_fold_errors"],1)
        for bad in (b,game(3,"2026-11-07"),game(4,"2026-11-14")):
            with self.assertRaisesRegex(ValueError,"leaked"):
                simulate(b,[bad],"global",120)
    def test_missing_lines_are_not_fabricated(self):
        a,b=game(1,"2026-10-24"),game(2,"2026-11-07")
        b["market"]={"home_spread":None,"total":None,"provider":None}
        out=simulate(b,[a],"bootstrap",130)
        self.assertIsNone(out["home_cover_probability"])
        self.assertIsNone(out["over_probability"])
    def test_bias_variant_shape_and_abstention(self):
        a,b=game(1,"2026-10-24"),game(2,"2026-10-31")
        self.assertEqual(correction([a,b],game(3,"2026-11-07"),"bootstrap"),(0.,0.))
        self.assertEqual(len(correction([a,b],game(3,"2026-11-07"),"team_form")),2)
        self.assertEqual(evaluate([a,b],min_train=2,trials=100)["eligible_games"],0)
if __name__=="__main__":unittest.main()

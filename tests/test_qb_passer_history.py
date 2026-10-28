import unittest
from scripts.qb_passer_history import collect,prior_qb_form,STATUS

def play(name,epa=.25,pass_=True):
    return {"_pass":pass_,"passer_player_name":name,"EPA":epa}
class QBPasserHistoryTests(unittest.TestCase):
    def game(self):
        return {"game_id":"202","date":"2026-10-20"}
    def test_mixed_qbs_and_unknown_passers_not_labeled_starters(self):
        passes=[play("Nick Minicucci") for _ in range(17)]
        passes+= [play("E.J. Archield Jr.",-.4) for _ in range(5)]
        passes+= [play(None) for _ in range(3)]
        r,qa=collect(self.game(),"Delaware","Missouri State",passes,"2026-10-21T04:00:00Z")
        self.assertEqual(len(r),2)
        self.assertEqual(r[0]["pass_tagged_plays"],17)
        self.assertEqual(r[1]["pass_tagged_plays"],5)
        self.assertEqual(qa["unnamed_pass_tagged_plays"],3)
        self.assertFalse(qa["starter_verified"])
        self.assertEqual(r[0]["passer_identity_status"],"POSTGAME_PASSER_NOT_STARTER_VERIFIED")
        self.assertFalse(r[0]["historical_source_time_verified"])
    def test_bad_game_date_rejected(self):
        with self.assertRaisesRegex(ValueError,"future"):
            collect({"game_id":"1","date":"2026-10-22"},"A","B",
                    [play("A B")],"2026-10-22T02:00:00Z")
    def test_predecision_conditioning_excludes_future_and_late_retrieval(self):
        old,_=collect(self.game(),"Delaware","Missouri State",
                      [play("Nick Minicucci",.5)]*20+[play("Backup QB",-.2)]*20,
                      "2026-10-21T04:00:00Z")
        later,_=collect({"game_id":"203","date":"2026-10-27"},"Delaware","WKU",
                        [play("Nick Minicucci",2.)]*20,"2026-10-28T06:00:00Z")
        total=prior_qb_form(old+later,"Delaware","Nick Minicucci",
                            "2026-10-27","2026-10-26T23:00:00Z")
        self.assertEqual(total["prior_player_games"],1)
        self.assertEqual(total["player_epa_per_pass_tagged_play"],.5)
        self.assertEqual(total["other_qb_epa_per_pass_tagged_play"],-.2)
        self.assertIsNone(total["qb_point_adjustment"])
    def test_insufficient_comparison_stays_missing(self):
        old,_=collect(self.game(),"Delaware","Missouri State",
                      [play("Nick Minicucci")]*4,"2026-10-21T04:00:00Z")
        p=prior_qb_form(old,"Delaware","Nick Minicucci",
                        "2026-10-27","2026-10-26T23:00:00Z")
        self.assertIsNone(p["within_team_player_minus_other_epa"])
        self.assertIsNone(p["player_epa_per_pass_tagged_play"])
    def test_duplicate_source_fails_closed(self):
        old,_=collect(self.game(),"Delaware","Missouri State",
                      [play("Nick Minicucci")]*20,"2026-10-21T04:00:00Z")
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            prior_qb_form(old+old,"Delaware","Nick Minicucci",
                          "2026-10-27","2026-10-26T23:00:00Z")
    def test_observation_must_not_postdate_target_day(self):
        with self.assertRaisesRegex(ValueError,"later"):
            prior_qb_form([],"Delaware","Nick Minicucci",
                          "2026-10-27","2026-10-28T00:00:00Z")
if __name__=="__main__":unittest.main()

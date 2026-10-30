import copy
import unittest
from scripts.player_prop_prospective_grade import evaluate,digest,FORECAST_STATUS,FINAL_STATUS

KICK="2026-10-24T20:00:00Z";ISSUE="2026-10-23T17:00:00Z"
RECEIPT="2026-10-23T17:05:00Z";FINAL="2026-10-25T10:00:00Z"
NOW="2026-10-30T20:00:00Z"
def forecast(v="MODEL",p=.7,line=50.5):
    r={"status":FORECAST_STATUS,"model_version":v,"game_id":"123",
       "player_id":"9001","metric":"receiving_yards","bookmaker":"fanduel",
       "line":line,"quote_sha256":"a"*64,
       "kickoff_utc":KICK,"issued_at_utc":ISSUE,
       "archive_observed_at_utc":RECEIPT,"quote_observed_at_utc":ISSUE,
       "over_probability":p,"bookmaker_over_no_vig":.52,
       "probabilities_conditional_on_playing":True,
       "betting_status":"PASS_UNVALIDATED"}
    r["record_sha256"]=digest(r)
    return r
def final(value=60):
    return {"status":FINAL_STATUS,"game_id":"123","player_id":"9001",
       "metric":"receiving_yards","actual":value,"kickoff_utc":KICK,
       "observed_at_utc":FINAL,"source_url":"https://example.edu/official",
       "stat_category_recorded":True,"participation_verified":True}
class PlayerGradeTests(unittest.TestCase):
    def test_same_settled_line_market_and_two_models(self):
        r=evaluate([forecast("A",.7),forecast("B",.6)],[final()],NOW,min_pairs=2)
        self.assertAlmostEqual(r["versions"]["A"]["model_brier"],.09)
        self.assertAlmostEqual(r["versions"]["A"]["market_no_vig_brier"],.2304)
        self.assertLess(r["versions"]["A"]["paired_brier_delta"],0)
        self.assertEqual(r["versions"]["A"]["graded_nonpush_props"],1)
        self.assertFalse(r["model_promoted"])
        self.assertFalse(r["versions"]["B"]["promotion_eligible"])

    def test_postkickoff_or_tampered_forecast_rejected(self):
        f=forecast();f["over_probability"]=.99
        with self.assertRaises(ValueError):evaluate([f],[final()],NOW,min_pairs=2)
        f=forecast();f["archive_observed_at_utc"]="2026-10-25T10:00:00Z"
        f["record_sha256"]=digest(f)
        with self.assertRaises(ValueError):evaluate([f],[final()],NOW,min_pairs=2)

    def test_missing_label_and_push_are_not_fake_loss(self):
        r=evaluate([forecast()],[final(50.5)],NOW,min_pairs=2)
        self.assertEqual(r["versions"]["MODEL"]["graded_nonpush_props"],0)
        self.assertEqual(r["unsettled_or_push"]["PUSH_EXCLUDED_FROM_BINARY_GRADE"],1)
        r=evaluate([forecast()],[],NOW,min_pairs=2)
        self.assertEqual(r["unsettled_or_push"]["NO_OFFICIAL_RECORDED_STAT_FINAL"],1)

    def test_unobserved_category_is_not_zero_and_wrong_final_time_is_rejected(self):
        f=final();f["stat_category_recorded"]=False
        with self.assertRaises(ValueError):evaluate([forecast()],[f],NOW,min_pairs=2)
        f=final();f["observed_at_utc"]=KICK
        with self.assertRaises(ValueError):evaluate([forecast()],[f],NOW,min_pairs=2)

    def test_inconsistent_book_quotes_and_duplicate_forecast_rejected(self):
        a=forecast("A");b=forecast("B");b["bookmaker_over_no_vig"]=.40
        b["record_sha256"]=digest(b)
        with self.assertRaises(ValueError):evaluate([a,b],[final()],NOW,min_pairs=2)
        with self.assertRaises(ValueError):evaluate([a,a],[final()],NOW,min_pairs=2)

if __name__=="__main__":
    unittest.main()

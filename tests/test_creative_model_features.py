import datetime as dt
import unittest
from scripts.creative_model_features import (
    _features, _record, _weighted, build, GROUPS, verified_injury_pressure_interaction)

def hist(day,margin=7,epa=.12,drives=11):
    return {"date":day,"game_id":day,"margin":margin,"epa_off":epa,
        "epa_coverage":1,"drives":drives,"attack_ppd":2.3,"defense_ppd":1.8,
        "drive_plays":6.0,"score_epa_gap":.20,"play_weighted_field_position":52.,
        "pass_rate":.55,"pressure_allowed":.2,"sack_generated":.11,
        "third_down_success":.44,"fourth_down_success":.6,
        "explosive_dependence":.08}

class FeatureTests(unittest.TestCase):
    def test_no_prior_games_cannot_invent_scoring_rates(self):
        f=_features([],[],"2026-10-27")
        self.assertIsNone(f["possession_score_estimate"])
        self.assertIsNone(f["recency_margin_shift_diff"])
        self.assertTrue(all(f[k] is None for k in GROUPS["possession_context"]))

    def test_two_prior_games_give_possession_and_stressor_proxies(self):
        before=[hist("2026-10-10"),hist("2026-10-20",9)]
        f=_features(before,before,"2026-10-27")
        margin,total=f["possession_score_estimate"]
        self.assertAlmostEqual(margin,0.)
        self.assertAlmostEqual(total,11.*(2.3+1.8))
        self.assertAlmostEqual(f["pressure_pass_exposure_diff"],0.)
        self.assertIsNotNone(f["volatility_proxy"])
        self.assertIsNone(f["recency_margin_shift_diff"])

    def test_future_or_same_day_history_rejected(self):
        with self.assertRaises(ValueError):
            _features([hist("2026-10-27"),hist("2026-10-12")],
                      [hist("2026-10-12"),hist("2026-10-10")],"2026-10-27")

    def test_recent_weighting_reacts_without_future(self):
        h=[hist("2026-09-20",0),hist("2026-10-20",20)]
        self.assertGreater(_weighted(h,"margin","2026-10-27"),10)

    def test_advanced_row_provenance_no_drive_data(self):
        game={"game_id":"1","date":"2026-10-10","kickoff_utc":"2026-10-10T16:00:00Z",
              "home":"Home","away":"Away","home_score":"21","away_score":"17","neutral":"false"}
        p=_record(game,"Home",{})
        self.assertIsNone(p["attack_ppd"])
        self.assertIsNone(p["score_epa_gap"])

    def test_model_row_created_before_current_outcome_enters_history(self):
        games=[]
        for i in range(5):
            date=dt.date(2026,10,1)+dt.timedelta(days=i)
            games.append({"game_id":str(i),"date":date.isoformat(),
                          "kickoff_utc":date.isoformat()+"T16:00:00Z",
                          "home":"Home","away":"Away","home_score":str(17+10*i),
                          "away_score":"7","neutral":"false"})
        rows=build(games,{})
        self.assertIsNone(rows[0]["recency_margin_shift_diff"])
        self.assertIsNone(rows[2]["recency_margin_shift_diff"])
        self.assertIsNotNone(rows[3]["recency_margin_shift_diff"])
        self.assertEqual(rows[2]["home_games_prior"],2)

    def test_verified_player_stressor_preserves_partial_unknown(self):
        verified={"coverage":"VERIFIED_REPORT_REVIEWED","absences":{"OL":2}}
        unknown={"coverage":"UNKNOWN","absences":None}
        result=verified_injury_pressure_interaction(verified,unknown,.25,.1)
        self.assertAlmostEqual(result["home_ol_stressor"],.5)
        self.assertIsNone(result["stressor_difference"])
        self.assertIsNone(result["away_ol_stressor"])
        self.assertFalse(result["model_points_adjusted"])

if __name__=="__main__":
    unittest.main()

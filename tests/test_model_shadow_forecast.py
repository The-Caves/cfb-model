"""No live deployment, no same-date leakage, and four distinct shadow versions."""
import copy
import datetime as dt
import unittest
from unittest.mock import patch

from scripts.model_v03 import build_weekly_games
from scripts.personnel_features import BASE_FIELDS
from scripts.model_shadow_forecast import (
    MODELS, VERSIONS, STATUS, build_shadow, verify_shadow, _training_hash,
    _clip_margin, checksum)


def fixture():
    games=[]
    # Four independent matchups per date: no team plays twice on a date.
    schools=list("ABCDEFGH")
    for day in range(40):
        date=dt.date(2026,8,1)+dt.timedelta(days=day)
        for match in range(4):
            i=day*4+match
            games.append({
                "game_id":str(1000+i),"date":date.isoformat(),
                "kickoff_utc":date.isoformat()+"T16:00:00Z",
                "home":schools[match*2],
                "away":schools[match*2+1],
                "neutral":"false","home_score":str(20+(i%17)),
                "away_score":str(13+(i%11))
            })
    training=build_weekly_games(games,{})
    future=[{"game_id":"90001","home":"A","away":"B",
             "kickoff_utc":"2026-10-29T23:30:00Z"},
            {"game_id":"90002","home":"Unseen Team","away":"D",
             "kickoff_utc":"2026-10-30T23:30:00Z"}]
    forecast={"status":"STEP3G_PROSPECTIVE_RESEARCH_PROJECTIONS",
        "run_id":"12345","forecast_observed_utc":"2026-10-28T12:00:00Z",
        "model_training":{
            "training_game_ids_sha256":checksum(sorted(r["game_id"] for r in training)),
            "training_features_sha256":_training_hash(training)},
        "games":[]}
    for row in future:
        forecast["games"].append({**row,"row_sha256":"a"*64,
            "features":{field:training[-1].get(field) for field in BASE_FIELDS},
            "projection":{"predicted_home_margin":5.,"predicted_total_points":54.}})
    return forecast,games,training


class ShadowModelsTests(unittest.TestCase):
    def make(self):
        frozen,games,training=fixture()
        with patch("scripts.model_shadow_forecast.verify_baseline"):
            result=build_shadow(frozen,games,{},training,"2026-10-28T12:05:00Z")
        return result,frozen,games,training

    def test_four_models_frozen_and_never_promote(self):
        shadow,*_=self.make()
        self.assertTrue(verify_shadow(shadow))
        self.assertEqual(shadow["status"],STATUS)
        self.assertFalse(shadow["model_promoted"])
        self.assertEqual(shadow["summary"]["games"],2)
        self.assertEqual(shadow["summary"]["fully_comparable_games"],1)
        row=shadow["games"][0]
        self.assertEqual(set(row["models"]),set(MODELS))
        self.assertTrue(all(row["models"][n]["version"]==VERSIONS[n] for n in MODELS))
        self.assertTrue(all(row["models"][n]["predicted_total"]==54. for n in MODELS))
        self.assertTrue(all(row["models"][n]["status"]=="SHADOW_FROZEN_RESEARCH" for n in MODELS))
        missing=shadow["games"][1]
        self.assertEqual(missing["models"]["latent_only"]["status"],"PASS")
        self.assertEqual(missing["models"]["recency_plus_latent"]["status"],"PASS")
        self.assertFalse(missing["latent_evidence_present"])

    def test_no_same_game_outcome_or_future_feature_used(self):
        original,frozen,games,training=self.make()
        # The shadow relies on completed historical game rows, never the
        # eventual future game's result (not present in these input tables).
        altered=copy.deepcopy(frozen)
        altered["games"][0]["future_game_result_must_not_be_used"]={"home_score":120}
        with patch("scripts.model_shadow_forecast.verify_baseline"):
            new=build_shadow(altered,games,{},training,"2026-10-28T12:05:00Z")
        self.assertEqual(
            [(r["game_id"],r["models"]) for r in original["games"]],
            [(r["game_id"],r["models"]) for r in new["games"]])

    def test_training_drift_rejected(self):
        frozen,games,training=fixture()
        altered=[dict(r) for r in training]
        altered[-1]["home_score"]+=1
        with patch("scripts.model_shadow_forecast.verify_baseline"):
            with self.assertRaisesRegex(ValueError,"training differs"):
                build_shadow(frozen,games,{},altered,"2026-10-28T12:05:00Z")

    def test_delayed_and_started_forecasts_rejected(self):
        frozen,games,training=fixture()
        with patch("scripts.model_shadow_forecast.verify_baseline"):
            with self.assertRaisesRegex(ValueError,"promptly"):
                build_shadow(frozen,games,{},training,"2026-10-28T13:00:00Z")
            frozen_late=copy.deepcopy(frozen)
            frozen_late["forecast_observed_utc"]="2026-11-01T00:00:00Z"
            with self.assertRaisesRegex(ValueError,"after all kickoffs"):
                build_shadow(frozen_late,games,{},training,"2026-11-01T00:05:00Z")

    def test_tampering_and_future_start_rejected(self):
        result,*_=self.make()
        result["games"][0]["models"]["recency_14d"]["predicted_total"]=70.
        with self.assertRaisesRegex(ValueError,"changed totals"):
            verify_shadow(result)
        result,*_=self.make()
        result["games"][0]["kickoff_utc"]="2026-10-28T12:01:00Z"
        with self.assertRaisesRegex(ValueError,"postkickoff"):
            verify_shadow(result)

    def test_research_model_score_sign_and_bounds(self):
        self.assertEqual(_clip_margin(100,42),42.)
        self.assertEqual(_clip_margin(-100,42),-42.)
        with self.assertRaisesRegex(ValueError,"Nonfinite"):
            _clip_margin(float("nan"),50)


if __name__=="__main__":
    unittest.main()

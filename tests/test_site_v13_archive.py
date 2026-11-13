"""Verify immutable source-gated V13 shadow captures and anti-forgery checks."""
import copy
import datetime as dt
import unittest

from scripts.site_decision_archive import freeze
from scripts.v13_v04_probabilities import fit_uncertainty, predict
from tests.test_site_decision_archive import board,NOW


class V13ArchiveAcceptance(unittest.TestCase):
    def valid(self):
        b=board();g=b["games"][0]
        g["home_bias_quarantined"]=True
        g["model_ats_side"]="PASS"
        model={"status":"SOURCE_OBSERVED_DIRECT_TEAM_SCORE_MODEL_RESEARCH_ONLY",
               "model":"V04_INDEPENDENT_OPPONENT_ADJUSTED_SCORES_RESEARCH_ONLY",
               "home_points":17.4,"away_points":25.1,
               "home_margin":-7.7,"total_points":42.5,
               "direct_scoring_fit_uses_v03_total":False,
               "no_market_lines_in_training":True,"model_promoted":False}
        g["v04_direct_scores"]=model
        history=[]
        for i in range(40):
            week="2026-10-10" if i%2 else "2026-10-17"
            history.append({"game_id":str(i),"date":week,"cutoff":week,
                            "v04":{"home_points":28.,"away_points":21.,
                                   "margin":7.,"total":49.},
                            "final_home":30,"final_away":27})
        at="2026-10-24"
        c=fit_uncertainty(history,at)
        p=predict(model,c,at,site=True,
                  market={"home_spread":-7.5,"total":49.})
        p.update({"site_status":"V13_SOURCE_TIMED_V04_PROBABILITY_SHADOW",
                  "game_id":g["game_id"],"home":"Home","away":"Away",
                  "kickoff_utc":g["kickoff_utc"],
                  "original_forecast_observed_utc":b["forecast_observed_utc"],
                  "generated_at_utc":NOW.isoformat(),
                  "source_run_id":b["forecast_run_id"],
                  "original_v04_score_checksum_unchanged":True,
                  "source_provenance":"IMMUTABLE_CAPTURED_PREKICKOFF_SETTLED_V04",
                  "previous_frozen_grades_unchanged":True,
                  "market_quote_eligible":True,
                  "research_probability_not_certified_betting_edge":True})
        g["v13_probability_shadow"]=p
        return b

    def test_v13_is_frozen_as_separate_prospective_receipt(self):
        b=self.valid()
        receipt=freeze(b,NOW,"888")
        row=receipt["rows"][0]
        shadow=row["v13_frozen_probability_shadow"]
        self.assertEqual(shadow["margin_mean"],-7.7)
        self.assertEqual(shadow["total_mean"],42.5)
        self.assertTrue(shadow["v04_mean_scores_unchanged"])
        self.assertFalse(shadow["model_promoted"])
        self.assertEqual(row["v04_direct_home_margin"],-7.7)
        self.assertEqual(row["frozen_forecast_home_margin"],10.)
        self.assertEqual(row["displayed_ats_side"],"PASS")

    def test_forged_model_or_probability_refused(self):
        original=self.valid()
        for field,value in [
            ("home_win_probability",1.),
            ("total_p90",60.),
            ("home_points_mean",99.),
            ("model_promoted",True),
            ("calibration_earlier_games",1),
            ("generated_at_utc","2026-10-24T18:00:00+00:00")]:
            b=copy.deepcopy(original)
            b["games"][0]["v13_probability_shadow"][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                freeze(b,NOW,"888")

    def test_unsourced_line_forgery_refused(self):
        b=self.valid()
        b["games"][0]["v13_probability_shadow"]["over_probability"]=.99
        with self.assertRaisesRegex(ValueError,"market-conditioned"):
            freeze(b,NOW,"888")

if __name__=="__main__":
    unittest.main()

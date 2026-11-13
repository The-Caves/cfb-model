"""V14 site research overlay preserves V04/V13 and original market decisions."""
import copy
import unittest

from scripts.site_v14_shadow import attach,STATUS
from scripts.v14_matchup_features import load_inputs,profile,matchup
from scripts.v14_residual_challenger import fit as fit_score
from scripts.v14_market_calibration import fit as fit_market
from scripts.v13_v04_probabilities import fit_uncertainty,predict
from tests.test_site_v13_shadow import board,NOW
from tests.test_v14_challenger import source,old


def contexts():
    rows,turnover=source()
    data=load_inputs(rows,turnover)
    previous=matchup(profile(data,"2026-09-26"),"Home","Away")
    history=[old(i,match=previous) for i in range(80)]
    cutoff="2026-11-13"
    return fit_score(history,cutoff),fit_market(history,cutoff),profile(data,cutoff)


def v13(board_obj):
    history=[{"game_id":str(i),"date":"2026-10-10",
        "cutoff":"2026-10-10",
        "v04":{"home_points":28.,"away_points":21.,
               "margin":7.,"total":49.},
        "final_home":31,"final_away":20} for i in range(40)]
    v=board_obj["games"][0]["v04_direct_scores"]
    # Only previous V04 outcomes affect uncertainty, not target-game finals.
    p=predict(v,fit_uncertainty(history,"2026-11-13"),
              "2026-11-13",site=True)
    board_obj["games"][0]["v13_probability_shadow"]=p


class V14SiteShadowTests(unittest.TestCase):
    def test_v14_is_new_score_shadow_without_rewriting_published_v04(self):
        b=board()
        v13(b)
        before=copy.deepcopy(b)
        scored,market,dated=contexts()
        result=attach(b,scored,market,dated,NOW)
        self.assertEqual(result["v14_matchup_display"]["status"],STATUS)
        self.assertEqual(result["v14_matchup_display"]["ready"],1)
        p=result["games"][0]["v14_matchup_shadow"]
        self.assertEqual(p["site_status"],STATUS)
        self.assertEqual(p["source_cutoff_exclusive"],"2026-11-13")
        self.assertEqual(p["variant"],"joint_close")
        self.assertIsNotNone(p["probabilities"])
        self.assertIsNotNone(p["probabilities"]["home_cover_calibrated"])
        self.assertFalse(p["model_promoted"])
        self.assertFalse(p["safe_for_betting"])
        self.assertFalse(p["historical_research_not_prospective_backtest"] is False)
        for k in ("v04_direct_scores","v13_probability_shadow",
                  "model_home_margin","model_total","model_ats_side","model_ou_side"):
            self.assertEqual(result["games"][0].get(k),before["games"][0].get(k))

    def test_no_matchup_source_or_no_v13_uncertainty_does_not_fabricate_quotes(self):
        b=board()
        score,market,dated=contexts()
        result=attach(b,score,market,dated,NOW)
        self.assertEqual(result["v14_matchup_display"]["ready"],1)
        self.assertIsNone(result["games"][0]["v14_matchup_shadow"]["probabilities"])
        fresh=copy.deepcopy(dated)
        fresh["teams"].pop("Away")
        result=attach(board(),score,market,fresh,NOW)
        self.assertEqual(result["v14_matchup_display"]["missing_source"],1)
        self.assertIsNone(result["games"][0]["v14_matchup_shadow"])

    def test_cutoff_mismatch_and_started_game_excluded(self):
        score,market,dated=contexts()
        altered=copy.deepcopy(dated);altered["cutoff"]="2026-11-12"
        with self.assertRaisesRegex(ValueError,"cutoff"):
            attach(board(),score,market,altered,NOW)
        b=board()
        b["games"][0]["kickoff_utc"]="2026-11-13T14:00:00Z"
        result=attach(b,score,market,dated,NOW)
        self.assertEqual(result["v14_matchup_display"]["already_kicked_off"],1)
        self.assertIsNone(result["games"][0]["v14_matchup_shadow"])

if __name__=="__main__":
    unittest.main()

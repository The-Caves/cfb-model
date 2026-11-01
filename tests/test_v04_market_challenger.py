"""Prospective research-policy rules, source clocks and PASS invariants."""
import copy
import datetime as dt
import unittest

from scripts.v04_market_challenger import decide, apply, POLICY, STATUS
from scripts.v04_direct_scores import MODEL, STATUS as SCORE_STATUS

KICK = "2026-11-07T20:00:00Z"
NOW = "2026-11-07T17:00:00Z"
QUOTE = "2026-11-07T16:58:00Z"


def score(margin=7., total=55.):
    return {"model": MODEL, "status": SCORE_STATUS,
            "home_margin": margin, "total_points": total,
            "home_points": (total+margin)/2.,
            "away_points": (total-margin)/2.,
            "direct_scoring_fit_uses_v03_total": False,
            "no_market_lines_in_training": True,
            "model_promoted": False}


def decision(spread=2., total=40., qb=2, score_override=None):
    return decide(score_override or score(), spread, total, "ESPN/Source",
                  QUOTE, KICK, NOW, qb)


class V04MarketChallengerTests(unittest.TestCase):
    def test_market_anchored_home_and_over_are_research_not_bets(self):
        d=decision()
        self.assertEqual((d["ats_side"],d["ou_side"]),("HOME","OVER"))
        self.assertEqual(d["policy"], POLICY)
        self.assertEqual(d["status"], STATUS)
        self.assertEqual(d["market_implied_home_margin"], -2.)
        self.assertAlmostEqual(d["market_anchored_home_margin"], .7)
        self.assertAlmostEqual(d["market_anchored_total"], 43.75)
        self.assertTrue(d["predefined_not_fitted_on_results"])
        self.assertFalse(d["validated_betting_edge"])
        self.assertFalse(d["score_model_promoted"])
        self.assertFalse(d["research_policy_promoted"])

    def test_away_and_under_direction_are_not_home_biased(self):
        d=decision(spread=-15.,total=65.)
        self.assertEqual((d["ats_side"],d["ou_side"]),("AWAY","UNDER"))

    def test_uncertain_qb_requires_more_disagreement_and_does_not_guess(self):
        d=decision(spread=0.,total=46.,qb=0)
        self.assertEqual((d["ats_side"],d["ou_side"]),("PASS","PASS"))
        self.assertTrue(d["missing_verified_qb_warning"])
        self.assertEqual(d["ats_min_gap"],8.)
        self.assertEqual(d["ou_min_gap"],10.)
        d=decision(spread=2.,total=40.,qb=0)
        self.assertEqual((d["ats_side"],d["ou_side"]),("HOME","OVER"))

    def test_large_conflict_passes_instead_of_chasing_apparent_edge(self):
        d=decision(spread=14.,total=20.)
        self.assertEqual((d["ats_side"],d["ou_side"]),("PASS","PASS"))
        self.assertIn("EXTREME",d["ats_reason"])
        self.assertIn("EXTREME",d["ou_reason"])

    def test_no_quote_does_not_produce_wager_or_market_projection(self):
        d=decide(score(),None,None,None,None,KICK,NOW,0)
        self.assertEqual((d["ats_side"],d["ou_side"]),("PASS","PASS"))
        self.assertIsNone(d["market_anchored_home_margin"])
        self.assertIsNone(d["market_anchored_total"])

    def test_after_kickoff_or_late_market_cannot_be_graded(self):
        with self.assertRaisesRegex(ValueError,"after kickoff"):
            decide(score(),2.,40.,"ESPN",QUOTE,KICK,KICK,2)
        with self.assertRaisesRegex(ValueError,"late"):
            decide(score(),2.,40.,"ESPN",KICK,KICK,NOW,2)
        with self.assertRaisesRegex(ValueError,"late"):
            decide(score(),2.,40.,"ESPN","2026-11-07T19:00:00Z",KICK,NOW,2)

    def test_forged_source_or_invalid_venue_score_fails_closed(self):
        bad=score()
        bad["no_market_lines_in_training"]=False
        with self.assertRaisesRegex(ValueError,"provenance"):
            decision(score_override=bad)
        bad=score()
        bad["home_points"]=100.
        with self.assertRaisesRegex(ValueError,"incoherent"):
            decision(score_override=bad)

    def test_board_apply_never_changes_original_v03_or_v04_scores(self):
        b={"schema_version":2,"betting_status":"PASS_UNVALIDATED",
            "games":[{"game_id":"123","kickoff_utc":KICK,
            "home_bias_quarantined":True,"model_home_margin":25.,
            "model_total":51.,"v04_direct_scores":score(),
            "market_home_spread":2.,"market_total":40.,
            "market_provider":"ESPN/Source","market_observed_utc":QUOTE,
            "qb_starters_verified":2}]}
        original=copy.deepcopy(b["games"][0])
        got=apply(b,dt.datetime.fromisoformat(NOW.replace("Z","+00:00")))
        row=got["games"][0]
        for k,v in original.items():
            self.assertEqual(row[k],v)
        self.assertEqual(row["v04_market_research"]["ats_side"],"HOME")
        self.assertEqual(got["v04_market_research_audit"]["ats_research_sides"],1)

    def test_absent_v04_and_started_game_do_not_forge_picks(self):
        b={"schema_version":2,"betting_status":"PASS_UNVALIDATED","games":[
            {"kickoff_utc":KICK,"v04_direct_scores":None},
            {"kickoff_utc":"2026-11-07T15:00:00Z",
             "v04_direct_scores":score(),"home_bias_quarantined":True}]}
        apply(b,dt.datetime.fromisoformat(NOW.replace("Z","+00:00")))
        self.assertTrue(all(g["v04_market_research"] is None for g in b["games"]))

if __name__ == "__main__":
    unittest.main()

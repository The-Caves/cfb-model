"""V08 vs V04 chronological, identical-cohort research contract.

Synthetic games are unit-test fixtures ONLY, never promoted or written as
2026 historical performance. All true source timing limitations remain visible.
"""
import copy
import datetime as dt
import unittest

from scripts.v08_matchup_v04_comparison import (
    evaluate,FAMILIES,CORE,STATUS)


def fixture(n=135):
    start=dt.date(2026,7,1)
    names=["A Lions","B Bears","C Tigers","D Owls","E Wolves","F Hawks"]
    games=[]
    rows=[]
    fields=set(CORE)
    for subset in FAMILIES.values():fields.update(subset)
    for i in range(n):
        date=start+dt.timedelta(days=i)
        home=names[i%len(names)]
        away=names[(i+2)%len(names)]
        if home==away:raise ValueError("bad fixture")
        game={"game_id":str(60000+i),"date":date.isoformat(),
            "kickoff_utc":date.isoformat()+"T18:00:00Z",
            "home":home,"away":away,
            "home_score":str(18+(i*7)%29),
            "away_score":str(7+(i*11)%40),
            "neutral":"False"}
        games.append(game)
        row={k:(i%11-5)*(j+1)*.003 for j,k in enumerate(sorted(fields))}
        row.update({**game,
            "home_score":int(game["home_score"]),"away_score":int(game["away_score"]),
            "home_games_prior":3,"away_games_prior":3,
            "feature_evidence_status":"RETROSPECTIVE_NOT_PUBLICATION_VERIFIED",
            "betting_status":"PASS_UNVALIDATED"})
        rows.append(row)
    return games,rows


class V08MatchupTests(unittest.TestCase):
    def test_same_source_game_and_holdout_cohort_for_each_valid_comparison(self):
        games,rows=fixture()
        original=copy.deepcopy((games,rows))
        report=evaluate(games,rows,start="2026-10-07",min_train=85,min_test=3)
        self.assertEqual((games,rows),original)
        self.assertEqual(report["status"],STATUS)
        self.assertFalse(report["model_promoted"])
        self.assertFalse(report["changes_frozen_v04_predictions"])
        self.assertTrue(report["no_source_timing_proof_for_historical_pbp"])
        self.assertTrue(report["summary"]["run_pass_defense"]["paired_games"]>0)
        for name,s in report["summary"].items():
            if s["paired_games"]:
                self.assertEqual(len(report["paired_predictions"][name]),s["paired_games"])
                for paired in report["paired_predictions"][name]:
                    self.assertEqual(paired["v04"]["game_id"],paired["candidate"]["game_id"])
                    self.assertEqual(paired["v04"]["actual_margin"],paired["candidate"]["actual_margin"])
                self.assertIsNotNone(s["delta_margin_mae"])
                self.assertIsNotNone(s["delta_total_mae"])
        self.assertIn("home_redzone_play_vs_defense",FAMILIES["redzone_play_success"])
        self.assertIn("home_turnover_risk_proxy",FAMILIES["giveaways_vs_takeaways"])

    def test_missing_turnover_evidence_passes_and_never_imputes_zero(self):
        games,rows=fixture()
        for row in rows:
            row["home_turnover_risk_proxy"]=None
            row["away_turnover_risk_proxy"]=None
        report=evaluate(games,rows,start="2026-10-07",min_train=85,min_test=3)
        self.assertEqual(report["summary"]["giveaways_vs_takeaways"]["paired_games"],0)
        self.assertEqual(report["summary"]["giveaways_vs_takeaways"]["status"],
                         "PASS_NO_MATCHED_GAMES")
        self.assertGreater(report["summary"]["run_pass_defense"]["paired_games"],0)
        self.assertFalse(report["model_promoted"])

    def test_swapped_teams_or_final_scores_are_not_silently_fitted(self):
        games,rows=fixture()
        rows[10]["away"]="Substituted opponent"
        with self.assertRaisesRegex(ValueError,"source identity mismatch"):
            evaluate(games,rows,start="2026-10-07",min_train=85,min_test=3)
        games,rows=fixture()
        rows[10]["home_score"]+=17
        with self.assertRaisesRegex(ValueError,"source identity mismatch"):
            evaluate(games,rows,start="2026-10-07",min_train=85,min_test=3)

    def test_same_date_unknown_feature_is_not_backfilled_from_future(self):
        games,rows=fixture()
        for row in rows:
            if row["date"]>="2026-10-07":
                row["home_redzone_play_vs_defense"]=None
        report=evaluate(games,rows,start="2026-10-07",min_train=85,min_test=3)
        self.assertEqual(report["summary"]["redzone_play_success"]["paired_games"],0)
        self.assertGreater(report["summary"]["run_pass_defense"]["paired_games"],0)


if __name__=="__main__":
    unittest.main()

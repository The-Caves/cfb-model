
import copy
import datetime as dt
import unittest

from scripts.nextgen_walkforward import evaluate,add_temporal_features,CORE,GROUPS,NONLINEAR

def record(n,day,complete=True):
    row={"game_id":str(n),"date":day.isoformat(),"home_score":30+n%8,
         "away_score":20+n%3,"home_games_prior":2,"away_games_prior":2,
         "feature_evidence_status":"RETROSPECTIVE_NOT_PUBLICATION_VERIFIED",
         "betting_status":"PASS_UNVALIDATED"}
    for j,f in enumerate(CORE):row[f]=(n%13)*(j+1)*.001
    for j,extras in enumerate(GROUPS.values()):
        for k,f in enumerate(extras):row[f]=(n%11)*(k+1)*.003 + (j+1)*.002
    if not complete: row[NONLINEAR[0]]=None
    return row

def fixture():
    begin=dt.date(2026,7,1)
    return [record(i,begin+dt.timedelta(days=i),i%17!=0) for i in range(115)]

class NextgenResearchTests(unittest.TestCase):
    def test_same_training_and_heldout_game_cohorts(self):
        r=evaluate(fixture(),start="2026-10-07",min_train=30)
        for fold in r["folds"]:
            for k,c in fold["model_cohorts"].items():
                if c["status"]=="RESEARCH_MATCHED_HELDOUT":
                    self.assertEqual(c["v03"]["games"],c["candidate"]["games"])
                    self.assertEqual(c["matched_test_games"],c["candidate"]["games"])
        self.assertFalse(r["model_promoted"])
        self.assertEqual(r["source_timing"],"RETROSPECTIVE_PBP_REVISED_NOT_ORIGINAL_POINT_IN_TIME")

    def test_missing_candidate_cov_does_not_turn_into_easier_baseline(self):
        r=evaluate(fixture(),start="2026-10-07",min_train=30)
        folded=[f for f in r["folds"] if f["model_cohorts"]["nonlinear_matchup"]["status"]=="RESEARCH_MATCHED_HELDOUT"]
        self.assertTrue(folded)
        self.assertTrue(any(f["model_cohorts"]["nonlinear_matchup"]["missing_train"]>0 for f in folded))
        self.assertEqual(r["summary"]["nonlinear_matchup"]["paired_games"],
            len(r["paired_game_predictions"]["nonlinear_matchup"]))

    def test_not_enough_eligible_games_passes_without_zero_imputation(self):
        r=evaluate(fixture()[:40],start="2026-08-01",min_train=70)
        self.assertEqual(r["summary"]["combined"]["paired_games"],0)
        self.assertEqual(r["summary"]["combined"]["status"],"NO_MATCHED_GAMES_TO_TEST")

    def test_duplicate_and_untrusted_history_refused(self):
        rows=fixture()
        with self.assertRaises(ValueError):evaluate(rows+[copy.deepcopy(rows[0])],min_train=30)
        rows[0]["feature_evidence_status"]="POINT_IN_TIME_VERIFIED"
        with self.assertRaises(ValueError):evaluate(rows,min_train=30)

    def test_nonzero_home_winner_and_total_training_are_separate(self):
        r=evaluate(fixture(),start="2026-10-07",min_train=30)
        for models in r["summary"].values():
            if models["paired_games"]:
                self.assertIsNotNone(models["candidate"]["total_mae"])
                self.assertIsNotNone(models["candidate"]["su_brier"])
                self.assertIsNotNone(models["candidate"]["signed_home_bias"])

if __name__=="__main__":
    unittest.main()

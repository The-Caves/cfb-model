"""Chronological research-only home-margin candidate acceptance checks."""
import copy,csv,datetime as dt,json,tempfile,unittest
from pathlib import Path
from scripts.home_bias_candidate import (
    BASE_FIELDS,fit_candidate,predict_candidate,load_combined,validate,eligible,
)

def row(gid,date,prior=2,home_score=23,away_score=16,form=0):
    return {"game_id":str(gid),"date":date,
       "kickoff_utc":date+"T18:00:00Z",
       "home":"H","away":"A",
       "home_games_prior":str(prior),"away_games_prior":str(prior),
       "home_score":home_score,"away_score":away_score,
       "betting_status":"PASS_UNVALIDATED",
       "feature_evidence_status":"RETROSPECTIVE_NOT_PUBLICATION_VERIFIED",
       **{f:form if f=="score_margin_form" else None for f in BASE_FIELDS}}

class CandidateTests(unittest.TestCase):
    def sample(self):
        rows=[]
        for week in range(9):
            date=(dt.date(2026,8,29)+dt.timedelta(days=7*week)).isoformat()
            for k in range(26):
                rows.append(row(str(100*week+k),date,prior=week,
                                home_score=24+(k%5)+week%2,
                                away_score=19+(k%7),form=k%7-3))
        return rows
    def test_prior_profile_gate(self):
        self.assertFalse(eligible(row(1,"2026-10-01",0)))
        self.assertTrue(eligible(row(2,"2026-10-01",1)))
    def test_model_rejects_same_day_or_future_label(self):
        train=self.sample()
        cutoff=dt.date(2026,10,10)
        training=[r for r in train if r["date"]<str(cutoff)]
        fit_candidate(training,BASE_FIELDS,cutoff)
        training.append(row("later","2026-10-10"))
        with self.assertRaises(ValueError):fit_candidate(training,BASE_FIELDS,cutoff)
    def test_labels_in_test_period_cannot_change_fit(self):
        cutoff=dt.date(2026,10,10)
        train=[r for r in self.sample() if r["date"]<str(cutoff)]
        params=fit_candidate(train,BASE_FIELDS,cutoff)
        test=[row("later","2026-10-10",prior=6)]
        old=predict_candidate(test,BASE_FIELDS,params)[0]
        test[0]["home_score"]=990
        test[0]["away_score"]=-900
        self.assertAlmostEqual(predict_candidate(test,BASE_FIELDS,params)[0],old)
    def test_no_margin_score_fabrication_from_malformed_labels(self):
        train=[r for r in self.sample() if r["date"]<"2026-10-10"]
        # Select an established-profile game; week-zero rows are intentionally excluded.
        train[27]["home_score"]=float("nan")
        with self.assertRaises(ValueError):fit_candidate(train,BASE_FIELDS,"2026-10-10")
    def test_chronological_ablation_consistent_test_counts(self):
        report=validate(self.sample(),start="2026-09-26",weeks=4)
        self.assertTrue(report["folds"])
        self.assertFalse(report["forecast_promotion"])
        self.assertFalse(report["historical_feature_publication_verified"])
        for fold in report["folds"]:
            self.assertEqual(len(fold["test_game_ids_sorted"]),fold["test_games"])
            self.assertTrue(all(str(fold["train_before"]) > r["date"] for r in self.sample()
                     if str(r["game_id"]) in fold["train_game_ids_sorted"]))
            for cohort in fold["model_comparison"].values():
                self.assertEqual(cohort["games"],fold["test_games"])
    def test_merged_feature_labels_must_have_exact_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            features=[row("1","2026-09-26")]
            features[0].pop("home_score");features[0].pop("away_score")
            labels=[{"game_id":"2","date":"2026-09-26",
                     "kickoff_utc":"2026-09-26T18:00:00Z",
                     "home_score":23,"away_score":16}]
            for name,rows in (("features.csv",features),("labels.csv",labels)):
                with (p/name).open("w",newline="") as f:
                    writer=csv.DictWriter(f,fieldnames=list(rows[0]))
                    writer.writeheader();writer.writerows(rows)
            with self.assertRaises(ValueError):load_combined(p/"features.csv",p/"labels.csv")
    def test_empty_csv_feature_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            feature={"game_id":"1","date":"2026-09-26",
                     "kickoff_utc":"2026-09-26T18:00:00Z",
                     "home_games_prior":"2","away_games_prior":"1",
                     "betting_status":"PASS_UNVALIDATED",
                     "feature_evidence_status":"RETROSPECTIVE_NOT_PUBLICATION_VERIFIED",
                     **{name:"" for name in BASE_FIELDS}}
            labels={"game_id":"1","date":"2026-09-26",
                    "kickoff_utc":"2026-09-26T18:00:00Z",
                    "home_score":"23","away_score":"12"}
            for name,record in (("features.csv",feature),("labels.csv",labels)):
                with (p/name).open("w",newline="") as output:
                    writer=csv.DictWriter(output,fieldnames=list(record))
                    writer.writeheader()
                    writer.writerow(record)
            rows=load_combined(p/"features.csv",p/"labels.csv")
            self.assertEqual(len(rows),1)
            self.assertIsNone(rows[0]["score_margin_form"])
            self.assertIsNone(rows[0]["off_epa_matchup"])
            self.assertNotEqual(rows[0]["score_margin_form"],0)
    def test_dual_prior_training_does_not_promote_candidate(self):
        report=validate(self.sample())
        self.assertEqual(report["candidate_version"],"HOME_MARGIN_PRIOR_GAMES_RECENCY14D_CANDIDATE_V1")
        self.assertEqual(report["betting_status"],"PASS_UNVALIDATED")
        self.assertEqual(report["settings"]["recency_half_life_days"],14)
if __name__=="__main__":unittest.main()

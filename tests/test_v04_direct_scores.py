import copy,datetime as dt,math,unittest
from scripts.v04_direct_scores import fit,predict,walkforward,STATUS,MODEL
from scripts.v04_score_benchmark import evaluate

OBS="2026-10-31T00:00:00Z"
def observed():
    rows=[]
    for week in range(9):
        day=(dt.date(2026,8,29)+dt.timedelta(days=7*week)).isoformat()
        for j in range(13):
            h=f"Team {j}" if week%2==0 else f"Team {j+13}"
            a=f"Team {j+13}" if week%2==0 else f"Team {j}"
            rows.append({"game_id":str(week*13+j+1),"date":day,
              "kickoff_utc":day+"T19:00:00Z","home":h,"away":a,
              "home_score":24+j%4+int(h=="Team 0")*8,
              "away_score":17+j%5,
              "neutral":"True" if j%6==0 else "False"})
    return rows

class V04Tests(unittest.TestCase):
    def test_direct_scores_conserve_margin_total_and_nonnegative(self):
        model=fit(observed()[:104],OBS)
        x=predict(model,"Team 0","Team 13",False)
        self.assertEqual(x["model"],MODEL)
        self.assertTrue(x["opponent_attack_defense_total_model"])
        self.assertFalse(x["direct_scoring_fit_uses_v03_total"])
        self.assertFalse(x["model_promoted"])
        self.assertAlmostEqual(x["home_points"]+x["away_points"],x["total_points"],places=2)
        self.assertAlmostEqual(x["home_points"]-x["away_points"],x["home_margin"],places=2)
        self.assertGreaterEqual(x["home_points"],0)
        self.assertGreaterEqual(x["away_points"],0)
        self.assertGreaterEqual(x["total_points"],20)
    def test_neutral_has_no_home_bonus_and_swapping_sides_changes_sign(self):
        model=fit(observed()[:104],OBS)
        a=predict(model,"Team 0","Team 13",True)
        b=predict(model,"Team 13","Team 0",True)
        self.assertAlmostEqual(a["home_margin"],-b["home_margin"],places=3)
        self.assertAlmostEqual(a["total_points"],b["total_points"],places=3)
        self.assertEqual(a["home_field_points"],0)
        normal=predict(model,"Team 0","Team 13",False)
        self.assertAlmostEqual(normal["home_margin"]-a["home_margin"],
            model["home_field_points"],places=3)
    def test_known_team_requirement_and_source_checks(self):
        model=fit(observed()[:104],OBS)
        self.assertIsNone(predict(model,"No team","Team 0",False))
        self.assertIsNone(predict(model,"Team 0","Team 0",False))
        self.assertIsNone(predict(model,"Team 0","Team 13","False"))
        a=observed()[:104]
        a[0]["date"]="2026-10-31"
        with self.assertRaisesRegex(ValueError,"strictly before"):
            fit(a,OBS)
        a=observed()[:104];a.append(a[0].copy())
        with self.assertRaisesRegex(ValueError,"Duplicated"):
            fit(a,OBS)
    def test_own_game_result_cannot_enter_train(self):
        a=observed()
        c=walkforward(a,["2026-10-24"])
        self.assertEqual(c["status"],"V04_CHRONOLOGICAL_RESEARCH_ONLY")
        self.assertTrue(c["folds"])
        self.assertGreater(c["folds"][0]["matched_games"],0)
        b=copy.deepcopy(a)
        for row in b:
            if row["date"]>="2026-10-24":
                row["home_score"]=200
                row["away_score"]=0
        d=walkforward(b,["2026-10-24"])
        self.assertEqual(
            [(p["margin"],p["total"]) for f in c["folds"] for p in f["predictions"]],
            [(p["margin"],p["total"]) for f in d["folds"] for p in f["predictions"]])
    def test_score_source_cannot_be_postdate_or_ambiguous_neutral(self):
        a=observed()[:104]
        a[1]["neutral"]="unknown"
        with self.assertRaisesRegex(ValueError,"Neutral"):
            fit(a,OBS)
    def test_no_automatic_promotion(self):
        m=fit(observed()[:104],OBS)
        self.assertFalse(m["model_promoted"])
        self.assertEqual(m["betting_status"],"PASS_UNVALIDATED")

if __name__=="__main__":unittest.main()

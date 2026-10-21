import csv,datetime as dt,json,tempfile,unittest
from pathlib import Path
from scripts.model_v03 import build_weekly_games,validate,rate,run

def game(gid,date,home,away,hs,as_):
    return {"game_id":str(gid),"date":date,"kickoff_utc":date+"T20:00:00Z",
            "home":home,"away":away,"home_score":str(hs),"away_score":str(as_),
            "neutral":"False"}
def advanced(g,team,opp,epa):
    return {"game_id":g["game_id"],"date":g["date"],"team":team,"opponent":opp,
            "off_epa_sum":str(epa*50),"epa_plays":"50",
            "def_epa_sum":str(0.1*50),"def_epa_plays":"50",
            "pass_epa_sum":"3","pass_epa_plays":"25",
            "rush_epa_sum":"1","rush_epa_plays":"25",
            "success_count":"25","success_plays":"50",
            "explosive_pass":"2","pass_plays":"25",
            "explosive_rush":"2","rush_plays":"25",
            "pressure_count":"1","pressure_observed":"25",
            "drive_yards_sum":"330","drives":"10",
            "scrimmage_plays":"50"}
class ModelV03Tests(unittest.TestCase):
    def fixtures(self):
        g=[game("1","2026-09-05","A","B",28,14),
           game("2","2026-09-05","C","D",21,17),
           game("3","2026-09-12","B","A",24,27),
           game("4","2026-09-19","A","C",38,10),
           game("5","2026-09-26","A","B",31,28)]
        adv={}
        for x in g:adv[x["game_id"]]={t:advanced(x,t,o,.2 if t=="A" else -.1)
              for t,o in ((x["home"],x["away"]),(x["away"],x["home"]))}
        return g,adv
    def test_strict_previous_date_only(self):
        g,adv=self.fixtures()
        rows=build_weekly_games(g,adv)
        self.assertEqual(rows[0]["home_games_prior"],0)
        self.assertEqual(rows[1]["away_games_prior"],0)
        self.assertEqual(rows[2]["home_games_prior"],1)
        self.assertEqual(rows[2]["away_games_prior"],1)
        self.assertEqual(rows[-1]["home_games_prior"],3)
        self.assertEqual(rows[-1]["away_games_prior"],2)
        self.assertEqual(rows[-1]["betting_status"],"PASS_UNVALIDATED")
        self.assertEqual(rows[-1]["feature_evidence_status"],"RETROSPECTIVE_NOT_PUBLICATION_VERIFIED")
    def test_current_game_score_cannot_enter_current_features(self):
        g,adv=self.fixtures()
        original=build_weekly_games(g,adv)
        g[-1]["home_score"]="140";g[-1]["away_score"]="0"
        after=build_weekly_games(g,adv)
        for f in ("score_margin_form","off_epa_matchup","pass_epa_form","rest_days_diff"):
            self.assertEqual(original[-1][f],after[-1][f])
    def test_retrospective_pbp_current_game_cannot_enter_current_features(self):
        g,adv=self.fixtures()
        a=build_weekly_games(g,adv)
        adv[g[-1]["game_id"]]["A"]["off_epa_sum"]="50000"
        b=build_weekly_games(g,adv)
        self.assertEqual(a[-1]["off_epa_matchup"],b[-1]["off_epa_matchup"])
        self.assertEqual(a[-1]["pass_epa_form"],b[-1]["pass_epa_form"])
    def test_no_zero_imputation_for_missing_provider_games(self):
        g,adv=self.fixtures()
        adv.pop("1")
        rows=build_weekly_games(g,adv)
        self.assertIsNone(rows[2]["off_epa_matchup"])
        self.assertEqual(rows[2]["home_games_prior"],1)
    def test_cannot_use_unzoned_time(self):
        from scripts.model_v03 import timestamp
        with self.assertRaises(ValueError):timestamp("2026-10-01T20:00:00")
    def test_weekly_walkforward_does_not_train_on_test_results(self):
        import numpy as np
        g,adv=self.fixtures()
        # Build more histories so week 2 has enough training games.
        teams=["A","B","C","D","E","F","G","H"]
        all_games=[]
        arows={}
        for week in range(7):
            day=(dt.date(2026,9,5)+dt.timedelta(days=week*7)).isoformat()
            for i in range(4):
                h=teams[2*i];away=teams[2*i+1]
                if week%2: h,away=away,h
                match=game(str(week*4+i+1),day,h,away,20+week+i,16+week)
                all_games.append(match)
                arows[match["game_id"]]={team:advanced(match,team,opp,.1+week/100)
                     for team,opp in ((h,away),(away,h))}
        features=build_weekly_games(all_games,arows)
        folds,details=validate(features,start_date="2026-09-26",min_training=5)
        self.assertTrue(folds)
        self.assertEqual(folds[0]["train_before"],"2026-09-26")
        self.assertFalse(any("2026-09-26"<=r["date"] for r in features if
                             r["date"]<folds[0]["train_before"]))
        self.assertTrue(details)
        self.assertTrue(all(r["result_labels_only"] for r in details))
    def test_output_feature_artifact_has_no_final_scores(self):
        g,adv=self.fixtures()
        import scripts.model_v03 as model
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            for name,rs in (("games.csv",g),
                            ("adv.csv",[v for pairs in adv.values() for v in pairs.values()])):
                with (p/name).open("w",newline="") as h:
                    writer=csv.DictWriter(h,fieldnames=list(rs[0]))
                    writer.writeheader();writer.writerows(rs)
            manifest={"season":2026,"betting_status":"PASS_UNVALIDATED",
                "historical_pregame_availability_verified":False,
                "retrieved_at_utc":"2026-10-21T20:10:00Z","sources":{}}
            (p/"manifest.json").write_text(json.dumps(manifest))
            summary=model.run(p/"games.csv",p/"adv.csv",p/"manifest.json",p/"out")
            with (p/"out"/"weekly_pregame_features.csv").open() as h:
                pregames=list(csv.DictReader(h))
            with (p/"out"/"weekly_postgame_labels.csv").open() as h:
                labels=list(csv.DictReader(h))
            self.assertEqual(len(pregames),5)
            self.assertEqual(len(labels),5)
            self.assertNotIn("home_score",pregames[0])
            self.assertNotIn("away_score",pregames[0])
            self.assertEqual(labels[-1]["home_score"],"31")
            self.assertEqual(labels[-1]["away_score"],"28")
            self.assertEqual(summary["betting_status"],"PASS_UNVALIDATED")
    def test_same_day_second_game_does_not_use_first_result(self):
        g,adv=self.fixtures()
        later=game("6","2026-09-26","A","C",14,35)
        g.append(later)
        adv["6"]={"A":advanced(later,"A","C",.7),
                  "C":advanced(later,"C","A",-.8)}
        before=build_weekly_games(g,adv)
        g[-2]["home_score"]="150"
        g[-2]["away_score"]="0"
        after=build_weekly_games(g,adv)
        for name in ("score_margin_form","off_epa_matchup","win_rate_form"):
            self.assertEqual(before[-1][name],after[-1][name])
    def test_real_data_manifest_lacks_historical_provenance(self):
        import scripts.model_v03 as model
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            for name,rows in (("games.csv",[self.fixtures()[0][0]]),
                ("adv.csv",list(self.fixtures()[1]["1"].values()))):
                with (p/name).open("w",newline="") as h:
                    writer=csv.DictWriter(h,fieldnames=list(rows[0]))
                    writer.writeheader();writer.writerows(rows)
            manifest={"season":2026,"betting_status":"PASS_UNVALIDATED",
                "historical_pregame_availability_verified":False,
                "retrieved_at_utc":"2026-10-21T20:10:00Z","sources":{}}
            (p/"manifest.json").write_text(json.dumps(manifest))
            _,_,m=model.load_inputs(p/"games.csv",p/"adv.csv",p/"manifest.json")
            self.assertFalse(m["historical_pregame_availability_verified"])
if __name__=="__main__":unittest.main()

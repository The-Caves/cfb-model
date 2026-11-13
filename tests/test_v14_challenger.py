"""V14 opponent-style, score residual, ATS/total reliability acceptance tests."""
import copy
import unittest

from scripts.v14_matchup_features import (
    STATUS as FEATURE_STATUS,load_inputs,profile,matchup,FEATURES)
from scripts.v14_residual_challenger import (
    STATUS as SCORE_STATUS,fit as fit_score,project,VARIANTS)
from scripts.v14_market_calibration import (
    STATUS as MARKET_STATUS,fit as fit_market,project as probabilities)


def source():
    adv=[];to=[]
    for i in range(1,7):
        day=f"2026-09-{i+6:02d}"
        for side,op in (("Home","Away"),("Away","Home")):
            adv.append({"game_id":str(i),"date":day,
                "team":side,"opponent":op,
                "pass_epa_sum":8 if side=="Home" else 1,
                "pass_epa_plays":40,
                "rush_epa_sum":2 if side=="Home" else 4,
                "rush_epa_plays":30,
                "pressure_count":3 if side=="Home" else 8,
                "pressure_observed":25,
                "explosive_pass":5 if side=="Home" else 2,
                "pass_plays":40,
                "redzone_success":2 if side=="Home" else 1,
                "redzone_plays":4,
                "scrimmage_plays":70})
            to.append({"game_id":str(i),"date":day,
                "team":side,"opponent":op,
                "turnovers_committed":1 if side=="Home" else 2,
                "takeaways_observed":2 if side=="Home" else 1,
                "historical_pregame_publication_verified":False})
    report={"status":"ESPN_COMPLETED_BOXSCORE_TURNOVERS_RESEARCH_ONLY",
        "rows":to,"historical_publication_times_verified":False,
        "model_promoted":False,"safe_for_betting":False}
    return adv,report


def old(i,cutoff="2026-09-26",date="2026-09-25",match=None):
    m=10.;t=50.
    return {"game_id":str(i),"cutoff":cutoff,"date":date,
        "home":"Home","away":"Away",
        "v04":{"home_points":30.,"away_points":20.,"margin":m,"total":t},
        "final_home":32+(i%4),"final_away":20,
        "matchup":match,"market":{"home_spread":-7.5,"total":48.5,
                                  "provider":"SourceBook"},
        "predictions":{"prior_variance":{
            "margin_mean":m,"total_mean":t,
            "margin_sd":16.5,"total_sd":17.}}}


class V14FeatureTests(unittest.TestCase):
    def test_prior_date_matchup_does_not_see_future_or_current_week(self):
        rows,t=source()
        store=load_inputs(rows,t)
        ctx=profile(store,"2026-09-26")
        m=matchup(ctx,"Home","Away")
        self.assertTrue(m["ready"])
        self.assertEqual(m["status"],FEATURE_STATUS)
        self.assertEqual(set(m["features"]),set(FEATURES))
        self.assertEqual(m["home_prior_games"],6)
        self.assertGreater(m["features"]["pass_matchup"],0)
        self.assertTrue(all(abs(x)<=2.5 for x in m["features"].values()))
        duplicate_later=copy.deepcopy(rows[0])
        duplicate_later.update({"game_id":"late","date":"2026-09-26",
                                "pass_epa_sum":9999})
        updated=load_inputs(rows+[duplicate_later],t)
        self.assertEqual(matchup(profile(updated,"2026-09-26"),"Home","Away"),m)
        ctx_first=profile(store,"2026-09-07")
        self.assertFalse(matchup(ctx_first,"Home","Away")["ready"])
        duplicate=copy.deepcopy(rows[0])
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            load_inputs(rows+[duplicate],t)

    def test_missing_statistics_do_not_become_zero(self):
        a,t=source()
        for row in a:
            if row["team"]=="Home":row["pressure_observed"]=0
        ctx=profile(load_inputs(a,t),"2026-09-26")
        self.assertFalse(matchup(ctx,"Home","Away")["ready"])


class V14RegressionTests(unittest.TestCase):
    def setUp(self):
        a,t=source()
        source=load_inputs(a,t)
        earlier_match=matchup(profile(source,"2026-09-26"),"Home","Away")
        self.match=matchup(profile(source,"2026-10-03"),"Home","Away")
        self.history=[old(i,match=earlier_match) for i in range(80)]

    def test_ridge_fits_only_past_and_falls_back_without_source(self):
        f=fit_score(self.history,"2026-10-03")
        self.assertEqual(f["status"],SCORE_STATUS)
        self.assertTrue(f["models"]["margin"]["ready"])
        self.assertTrue(f["models"]["total"]["ready"])
        scores=self.history[0]["v04"]
        for version in VARIANTS:
            p=project(scores,self.match,f,"2026-10-03",variant=version)
            self.assertFalse(p["model_promoted"])
            self.assertGreater(p["total"],0)
            self.assertAlmostEqual(p["home_points"]-p["away_points"],p["margin"],5)
            self.assertAlmostEqual(p["home_points"]+p["away_points"],p["total"],5)
            self.assertLessEqual(abs(p["margin_adjustment"]),6.)
            self.assertLessEqual(abs(p["total_adjustment"]),6.)
        with self.assertRaises(ValueError):
            fit_score(self.history+[old(100,"2026-10-03","2026-10-03",
                                        self.match)],"2026-10-03")
        empty=project(scores,None,f,"2026-10-03")
        self.assertEqual(empty["margin"],10.)
        self.assertEqual(empty["total"],50.)

    def test_low_sample_fallback_and_target_cutoff_mismatch(self):
        f=fit_score(self.history[:10],"2026-10-03")
        self.assertFalse(f["models"]["margin"]["ready"])
        p=project(self.history[0]["v04"],self.match,f,"2026-10-03")
        self.assertEqual(p["margin"],10.)
        mismatch=copy.deepcopy(self.match);mismatch["cutoff"]="2026-10-05"
        with self.assertRaisesRegex(ValueError,"weekly cutoff"):
            project(self.history[0]["v04"],mismatch,f,"2026-10-03")


class V14MarketTests(unittest.TestCase):
    def setUp(self):
        self.history=[old(i) for i in range(75)]

    def test_sportsbook_calibration_only_uses_prior_finalized_weeks(self):
        f=fit_market(self.history,"2026-10-03")
        self.assertEqual(f["status"],MARKET_STATUS)
        self.assertTrue(f["ats"]["ready"])
        self.assertTrue(f["total"]["ready"])
        pred=probabilities(10.,50.,16.5,17.,self.history[0]["market"],
                           f,"2026-10-03")
        self.assertTrue(0<=pred["home_win"]<=1)
        self.assertTrue(0<=pred["home_cover_raw"]<=1)
        self.assertTrue(0<=pred["home_cover_calibrated"]<=1)
        self.assertFalse(pred["safe_for_betting"])
        none=probabilities(10.,50.,16.5,17.,None,f,"2026-10-03")
        self.assertIsNone(none["home_cover_raw"])
        self.assertEqual(none["home_cover_choice"],"PASS")
        bad=old(777,cutoff="2026-10-03",date="2026-10-03")
        with self.assertRaisesRegex(ValueError,"Future"):
            fit_market(self.history+[bad],"2026-10-03")
        fake=dict(self.history[0]["market"],provider=None)
        with self.assertRaisesRegex(ValueError,"attribution"):
            probabilities(10.,50.,16.5,17.,fake,f,"2026-10-03")
        with self.assertRaisesRegex(ValueError,"incorrect week"):
            probabilities(10.,50.,16.5,17.,None,f,"2026-10-10")

if __name__=="__main__":
    unittest.main()

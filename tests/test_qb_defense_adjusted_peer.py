"""Opponent defense adjustment needs earlier games, reliable attribution and peers."""
import unittest,datetime as dt
import numpy as np

from scripts.qb_defense_adjusted_peer import (
    build_context,peer_effect,STATUS)
from scripts.qb_conditional_forecast import scenario
from scripts.personnel_features import BASE_FIELDS

TARGET="2026-10-31"
DECISION="2026-10-29T18:00:00Z"

def passer(gid,date,team,opponent,player,epa,plays=30,total=30,observed="2026-10-28T12:00:00Z"):
    return {"game_id":str(gid),"date":date,"team":team,"opponent":opponent,
        "player":player,"pass_tagged_plays":str(plays),"pass_epa_plays":str(plays),
        "pass_epa_sum":str(epa*plays),"team_pass_tagged_plays":str(total),
        "source_retrieved_at_utc":observed,
        "historical_source_time_verified":"False",
        "betting_status":"PASS_UNVALIDATED"}

def history():
    # SoftDef had previously ALLOWED +0.3 EPA/pass. HardDef had allowed
    # -0.3 against two prior different opponents. Both accepted pregame.
    return [
        passer("101","2026-10-01","C","SoftDef","C QB",.3),
        passer("102","2026-10-08","D","SoftDef","D QB",.3),
        passer("103","2026-10-01","E","HardDef","E QB",-.3),
        passer("104","2026-10-08","F","HardDef","F QB",-.3),
        # QB One appears better raw +0.4 than QB Two raw -0.1, but had
        # the weaker defense. After adjustments .1 < .2.
        passer("201","2026-10-20","A","SoftDef","QB One",.4),
        passer("202","2026-10-21","A","HardDef","QB Two",-.1)]

class DefenseAdjustedQBTests(unittest.TestCase):
    def test_stronger_defense_reverses_raw_qb_ranking(self):
        rows=history()
        ctx=build_context(rows,TARGET,DECISION)
        self.assertEqual(ctx["status"],STATUS)
        x=peer_effect(ctx,"A","QB One",8.)
        y=peer_effect(ctx,"A","QB Two",8.)
        self.assertEqual(x["status"],"QB_OPPONENT_ADJUSTED_PEER_SHADOW")
        self.assertAlmostEqual(x["player_adjusted_epa_per_pass"],.1)
        self.assertAlmostEqual(x["other_qb_adjusted_epa_per_pass"],.2)
        self.assertLess(x["margin_impact"],0)
        self.assertGreater(y["margin_impact"],0)
        self.assertEqual(x["player_adjusted_plays"],30)
        self.assertEqual(x["peer_adjusted_plays"],30)
        self.assertTrue(x["no_depth_chart_rank_penalty"])
        self.assertFalse(ctx["source_historical_publication_verified"])

    def test_current_game_does_not_set_its_own_opponent_baseline(self):
        baseline=build_context(history(),TARGET,DECISION)
        inserted=passer("205","2026-10-21","G","HardDef","G QB",10.)
        trial=build_context(history()+[inserted],TARGET,DECISION)
        self.assertEqual(peer_effect(baseline,"A","QB One",8.)["margin_impact"],
                         peer_effect(trial,"A","QB One",8.)["margin_impact"])

    def test_without_prior_opponent_defenses_never_invents_a_peer(self):
        rows=history()[-2:]
        ctx=build_context(rows,TARGET,DECISION)
        x=peer_effect(ctx,"A","QB One",8.)
        self.assertIn("PASS",x["status"])
        self.assertEqual(x["margin_impact"],0)
        self.assertEqual(x["player_adjusted_plays"],0)

    def test_unavailable_defensive_data_ignored_and_sample_insufficient(self):
        rows=history()
        rows[-1]["team_pass_tagged_plays"]="100"
        ctx=build_context(rows,TARGET,DECISION)
        x=peer_effect(ctx,"A","QB One",8.)
        self.assertEqual(x["margin_impact"],0)
        self.assertEqual(x["peer_adjusted_plays"],0)
        self.assertGreaterEqual(ctx["rejected_game_coverage"],1)

    def test_source_first_seen_after_decision_cannot_enter(self):
        late=history()
        for item in late[:4]:
            item["source_retrieved_at_utc"]="2026-11-01T12:00:00Z"
        ctx=build_context(late,TARGET,DECISION)
        self.assertEqual(peer_effect(ctx,"A","QB One",8.)["margin_impact"],0)

    def test_future_and_same_day_results_excluded(self):
        ctx=build_context(history()+[
           passer("300",TARGET,"A","HardDef","QB One",20.)],TARGET,DECISION)
        self.assertEqual(peer_effect(ctx,"A","QB One",8.)["player_adjusted_plays"],30)

    def test_duplicate_and_inconsistent_source_rejected(self):
        first=history()
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            build_context(first+[first[-1]],TARGET,DECISION)
        inconsistent=history()
        inconsistent.append(passer("201","2026-10-20","A","SoftDef",
                                   "QB Three",0.,10,total=50))
        with self.assertRaisesRegex(ValueError,"Conflicting"):
            build_context(inconsistent,TARGET,DECISION)
        mismatch=history();mismatch[-1]["team_pass_tagged_plays"]="10"
        with self.assertRaisesRegex(ValueError,"exceeds observed"):
            build_context(mismatch,TARGET,DECISION)

    def test_research_clearance_and_fitted_coefficient_required(self):
        rows=history();rows[-1]["historical_source_time_verified"]="True"
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            build_context(rows,TARGET,DECISION)
        ctx=build_context(history(),TARGET,DECISION)
        with self.assertRaisesRegex(ValueError,"coefficient"):
            peer_effect(ctx,"A","QB One",float("nan"))
        with self.assertRaisesRegex(ValueError,"after game day"):
            build_context(history(),TARGET,"2026-11-01T03:00:00Z")

    def test_no_other_qb_requires_zero_effect_even_if_star_is_amazing(self):
        rows=history()[:-1]
        rows[-1]["pass_epa_sum"]="300"
        ctx=build_context(rows,TARGET,DECISION)
        self.assertEqual(peer_effect(ctx,"A","QB One",8.)["margin_impact"],0)

    def test_existing_frozen_forecast_gets_separate_peer_only_shadow(self):
        rows=history()
        forecast={"home":"A","away":"B","kickoff_utc":"2026-10-31T20:00:00Z",
          "projection":{"predicted_home_margin":3.,"predicted_total_points":48.}}
        profiles={"team_profiles":{"home":{"recent_form":{"epa_pass":.1}},
            "away":{"recent_form":{"epa_pass":None}}}}
        home={"starter":"QB One","starter_status":"PROJECTED_DEPTH_CHART_ONLY",
              "confidence":"LOW_UNCONFIRMED","depth_rank":1,
              "is_confirmed_starter":False,"betting_status":"PASS_UNVALIDATED",
              "availability_by_player":{},
              "scenarios":[{"player":"QB One","depth_rank":1},
                           {"player":"QB Two","depth_rank":2}]}
        away={"starter":None,"starter_status":"UNKNOWN","confidence":"UNKNOWN",
              "depth_rank":None,"is_confirmed_starter":False,
              "betting_status":"PASS_UNVALIDATED","availability_by_player":{},
              "scenarios":[]}
        n=len(BASE_FIELDS)
        coefs=np.zeros((n+1,1));coefs[BASE_FIELDS.index("pass_epa_form")+1,0]=8.
        params=(coefs,np.zeros(n),np.ones(n),None)
        result=scenario(forecast,profiles,{"home":home,"away":away},
                        rows,params,dt.datetime.fromisoformat("2026-10-29T18:00:00+00:00"))
        self.assertEqual(result["baseline_margin"],3.)
        self.assertEqual(result["opponent_peer_status"],"QB_OPPONENT_PEER_EPA_SHADOW")
        self.assertLess(result["opponent_peer_home_margin"],result["baseline_margin"])
        self.assertEqual(result["opponent_peer_qualified_sides"],1)
        self.assertGreater(result["opponent_peer_exposure_home_margin"],
                           result["opponent_peer_home_margin"])
        self.assertTrue(result["opponent_peer_player_scenarios_by_side"]["home"]
                        ["QB Two"]["no_depth_chart_rank_penalty"])
        self.assertFalse(result["opponent_peer_historical_publication_authenticated"])
        self.assertFalse(result["model_promoted"])

if __name__=="__main__":unittest.main()

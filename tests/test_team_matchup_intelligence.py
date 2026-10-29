import unittest,datetime as dt
from scripts.team_matchup_intelligence import (_team_game,_profile,matchup,augment,
  validated_turnovers,build_profile_board,STATUS)
def game(n,day,home="A",away="B"):
    return {"game_id":str(n),"date":day,"kickoff_utc":day+"T16:00:00Z",
        "home":home,"away":away,"home_score":"24","away_score":"10","neutral":"false"}
def adv(g,home_run=.2,away_run=-.5,home_pass=.4,away_pass=-.1):
    d={}
    for team,run,pa in ((g["home"],home_run,home_pass),(g["away"],away_run,away_pass)):
        d[team]={"rush_epa_sum":str(run*30),"rush_epa_plays":"30",
           "pass_epa_sum":str(pa*30),"pass_epa_plays":"30",
           "rush_success_count":"18","rush_success_plays":"30",
           "pass_success_count":"15","pass_success_plays":"30",
           "pass_plays":"30","rush_plays":"30","scrimmage_plays":"60",
           "explosive_pass":"2","pressure_count":"3","pressure_observed":"30",
           "redzone_success":"4","redzone_plays":"8",
           "drive_plays_sum":"60","drives":"10"}
    return {g["game_id"]:d}
def turnovers(g):
    return {"status":"ESPN_COMPLETED_BOXSCORE_TURNOVERS_RESEARCH_ONLY",
      "season":2026,"historical_publication_times_verified":False,
      "betting_status":"PASS_UNVALIDATED","rows":[
      {"game_id":g["game_id"],"date":g["date"],"team":g["home"],
       "opponent":g["away"],"turnovers_committed":2,"takeaways_observed":0,
       "betting_status":"PASS_UNVALIDATED"},
      {"game_id":g["game_id"],"date":g["date"],"team":g["away"],
       "opponent":g["home"],"turnovers_committed":0,"takeaways_observed":2,
       "betting_status":"PASS_UNVALIDATED"}]}
class MatchupTests(unittest.TestCase):
    def test_offensive_run_good_opposing_run_defense_bad_not_reversed(self):
        g=game(1,"2026-09-01");x=adv(g)
        a=_team_game(g,"A",x);b=_team_game(g,"B",x)
        self.assertEqual(a["run_off"],.2)
        self.assertEqual(b["run_def_allowed"],.2)
        self.assertEqual(a["run_def_allowed"],-.5)
        self.assertEqual(matchup(_profile([a]),_profile([b]))["home_run_edge"],.2)
        self.assertEqual(matchup(_profile([a]),_profile([b]))["away_run_edge"],-.5)
    def test_strong_run_offense_plus_weak_run_defense_is_favorable(self):
        # This guard explicitly catches the earlier incorrect subtraction.
        home={"run_off":0.30,"run_def_allowed":-.25,
              "pass_off":0.10,"pass_def_allowed":-.20,
              "run_success_off":.58,"pass_success_off":.55,
              "pass_explosive_off":.13,"pressure_allowed":.1,
              "turnovers_committed":1.7,"takeaways":1.5}
        away={"run_off":-.25,"run_def_allowed":.40,
              "pass_off":.05,"pass_def_allowed":-.15,
              "run_success_allowed":.60,"pass_success_allowed":.35,
              "pass_explosive_allowed":.14,"pressure_generated":.08,
              "turnovers_committed":.8,"takeaways":2.0}
        x=matchup(home,away)
        self.assertAlmostEqual(x["home_run_edge"],.35)
        self.assertAlmostEqual(x["home_pass_edge"],-.025)
        self.assertAlmostEqual(x["home_run_success_edge"],.09)
        self.assertAlmostEqual(x["home_turnover_risk_proxy"],1.85)
        self.assertIsNone(x["away_turnover_risk_proxy"])
    def test_missing_run_defense_is_unknown_not_inferred_from_offense(self):
        self.assertIsNone(matchup({"run_off":.2},{"run_def_allowed":None})["home_run_edge"])

    def test_team_can_struggle_when_run_stopped_without_assuming_cause(self):
        xs=[]
        for i,v in enumerate((-.2,-.3,.2,.3)):
            g=game(i+1,(dt.date(2026,9,1)+dt.timedelta(days=7*i)).isoformat())
            x=_team_game(g,"A",adv(g,home_run=v))
            x["points"]=10 if v<=0 else 30
            xs.append(x)
        p=_profile(xs)
        self.assertEqual(p["run_disruption_dependency"],20.)
        self.assertEqual(p["run_stopped_games"],2)
        self.assertEqual(_profile(xs[:2])["run_disruption_dependency"],None)
    def test_opponent_adjusted_run_pass_uses_only_previous_opponent_strength(self):
        games=[]
        records={}
        for k in range(1,5):
            g=game(k,(dt.date(2026,9,1)+dt.timedelta(days=7*k)).isoformat())
            games.append(g);records.update(adv(g,home_run=.4,away_run=-.1))
        rows=augment(games,records)
        self.assertIsNone(rows[0]["home_run_adj_edge"])
        # The first two opponent matchups don't yet meet the prior-history gate.
        self.assertIsNone(rows[1]["home_run_adj_edge"])
        self.assertIsNotNone(rows[3]["home_run_adj_edge"])
        future=[game(22,"2026-10-29")]
        board=build_profile_board(games,records,None,future,"2026-10-29")
        self.assertIsNotNone(board["games"][0]["matchup"]["home_run_adj_edge"])
        self.assertFalse(board["games"][0]["total_projection_generated_from_profile"])

    def test_future_game_does_not_enter_its_own_matchup(self):
        g1=game(1,"2026-09-01");g2=game(2,"2026-09-08")
        all_={**adv(g1),**adv(g2,home_run=10,home_pass=10)}
        x=augment([g1,g2],all_)
        self.assertIsNone(x[0]["home_run_edge"])
        self.assertAlmostEqual(x[1]["home_run_edge"],.2,places=5)
    def test_same_date_results_do_not_modify_other_matchups(self):
        g1=game(1,"2026-09-01",home="A",away="B")
        g2=game(2,"2026-09-01",home="B",away="C")
        advanced={**adv(g1),**adv(g2,home_run=3,away_run=-1)}
        rows=augment([g1,g2],advanced)
        self.assertIsNone(rows[1]["home_run_edge"])
        self.assertIsNone(rows[1]["home_run_adj_edge"])

    def test_turnover_missing_not_zero_or_healthy(self):
        g=game(1,"2026-09-01")
        no=_team_game(g,"A",adv(g))
        self.assertIsNone(no["turnovers_committed"])
        by=validated_turnovers(turnovers(g),[g])
        self.assertEqual(_team_game(g,"A",adv(g),by)["turnovers_committed"],2)
        cut=turnovers(g);cut["rows"]=cut["rows"][:1]
        with self.assertRaisesRegex(ValueError,"One-sided"):
            validated_turnovers(cut,[g])
    def test_team_board_future_rejects_missing_context_no_fake_under(self):
        g=game(1,"2026-09-01")
        upcoming=[game(2,"2026-10-30")]
        board=build_profile_board([g],adv(g),None,upcoming,"2026-10-29")
        self.assertEqual(board["summary"]["games"],1)
        self.assertIsNone(board["games"][0]["matchup"]["home_turnover_risk_proxy"])
        self.assertFalse(board["games"][0]["total_projection_generated_from_profile"])
        self.assertEqual(board["status"],STATUS)
if __name__=="__main__":unittest.main()

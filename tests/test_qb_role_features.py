import unittest
from scripts.qb_role_features import build,STATUS

def passer(gid,day,name,plays,received="2026-10-26T14:00:00Z"):
    return {"game_id":gid,"date":day,"team":"Delaware Blue Hens",
        "opponent":"Some Opponent","player":name,"pass_tagged_plays":plays,
        "pass_epa_sum":plays*.2,"pass_epa_plays":plays,
        "source_retrieved_at_utc":received,
        "historical_source_time_verified":False,
        "betting_status":"PASS_UNVALIDATED"}
def game():
    return {"game_id":"401871071","home":"Western Kentucky Hilltoppers",
            "away":"Delaware Blue Hens","kickoff_utc":"2026-10-27T23:00:00Z"}
def config():
    return {"status":"REVIEWED_OFFICIAL_GAMEWEEK_LINKS_NOT_QB_STARTERS",
        "first_review_date":"2026-10-26","entries":[{
            "game_id":"401871071","team":"Delaware Blue Hens",
            "opponent":"Western Kentucky Hilltoppers",
            "kickoff_utc":"2026-10-27T23:00:00Z",
            "published_date":"2026-10-26",
            "starter_confirmed":False,
            "qb_context":{"player":"Nick Minicucci","mention_type":"RETURNED_FROM_INJURY_IN_PREVIOUS_GAME",
                          "source_url":"https://bluehens.com/news/2026/10/26/football-wraps-weekday-cusa-play-at-wku"}
        }]}
def data():
    return [passer("1","2026-09-06","Nick Minicucci",40),
            passer("2","2026-09-13","Nick Minicucci",45),
            passer("3","2026-10-10","E.J. Archield Jr.",35),
            passer("4","2026-10-20","Nick Minicucci",44)]
class RoleTests(unittest.TestCase):
    def test_primary_usage_proxy_and_recent_return_not_upcoming_starter(self):
        result=build([game()],data(),config(),"2026-10-26T20:00:00Z")
        self.assertEqual(result["status"],STATUS)
        d=next(r for r in result["rows"] if r["team"]=="Delaware Blue Hens")
        self.assertEqual(d["season_leading_passer_proxy"],"Nick Minicucci")
        self.assertEqual(d["last_game_leading_passer_proxy"],"Nick Minicucci")
        self.assertFalse(d["observed_recent_qb_switch"])
        self.assertEqual(d["official_recent_return_context"]["signal"],
                         "RETURNED_IN_PRIOR_GAME_NOT_CONFIRMED_THIS_GAME")
        self.assertEqual(d["current_qb_status"],"UNKNOWN")
        self.assertIsNone(d["current_qb_conditional_history"])
        self.assertIsNone(d["confirmed_starter_matches_season_passer_leader_proxy"])
        self.assertIsNone(d["confirmed_starter_matches_recent_return_context"])
        self.assertIsNone(d["model_qb_points_adjustment"])
    def test_future_pbp_observation_not_used_to_reconstruct_pregame(self):
        late=[passer("5","2026-10-20","New Guy",100,
                     "2026-10-28T02:00:00Z")]
        r=build([game()],data()+late,config(),"2026-10-26T20:00:00Z")
        d=next(x for x in r["rows"] if x["team"]=="Delaware Blue Hens")
        self.assertEqual(d["season_leading_passer_proxy"],"Nick Minicucci")
    def test_real_verified_starter_can_have_conditional_history(self):
        starters={("401871071","Delaware Blue Hens"):{
            "status":"CONFIRMED_REVIEWED_PREKICKOFF","player":"Nick Minicucci",
            "observed_at_utc":"2026-10-26T18:00:00Z"}}
        r=build([game()],data(),config(),"2026-10-26T20:00:00Z",starters)
        d=next(x for x in r["rows"] if x["team"]=="Delaware Blue Hens")
        self.assertEqual(d["current_qb_status"],"CONFIRMED_REVIEWED_PREKICKOFF")
        self.assertTrue(d["confirmed_starter_matches_season_passer_leader_proxy"])
        self.assertTrue(d["confirmed_starter_matches_recent_return_context"])
        self.assertIsNotNone(d["current_qb_conditional_history"])
        self.assertIsNotNone(d["current_qb_conditional_history"]["within_team_player_minus_other_epa"])
    def test_unverified_qb_or_future_review_rejected(self):
        starters={("401871071","Delaware Blue Hens"):{
            "status":"EXPECTED","player":"Nick Minicucci",
            "observed_at_utc":"2026-10-26T18:00:00Z"}}
        with self.assertRaisesRegex(ValueError,"Unreviewed"):
            build([game()],data(),config(),"2026-10-26T20:00:00Z",starters)
    def test_current_game_excluded(self):
        self.assertEqual(build([game()],[],config(),"2026-10-28T12:00:00Z")["team_game_slots"],0)
if __name__=="__main__":unittest.main()

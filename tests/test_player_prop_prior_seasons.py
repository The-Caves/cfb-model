import unittest
from scripts.player_prop_prior_seasons import assemble,make_schedule,STATUS

AT="2026-10-30T21:00:00Z"
def schedule(y):
    kickoff=f"{y}-10-12T19:00:00Z" if y==2024 else "2026-01-02T19:00:00Z"
    return [{"game_id":100+y,"season":y,"start_date":kickoff,
      "completed":True,"start_time_tbd":False,"fbs_participant":True,
      "home_id":10+y,"away_id":25+y,"home_team":"A","away_team":"B"}]
def box(y):
    return [{"game_id":100+y,"season":y,"team_id":10+y,"athlete_id":55,
        "athlete_name":"Same ESPN Player","category":"passing",
        "passingYards":"280","passingTouchdowns":"3",
        "interceptions":"0","completions/passingAttempts":"22/33"}]
def fixture():
    return {2024:box(2024),2025:box(2025)},{2024:schedule(2024),2025:schedule(2025)}
class PriorSeasonsTests(unittest.TestCase):
    def test_bowl_in_january_stays_previous_football_season(self):
        b,s=fixture()
        r=assemble(b,s,AT)
        self.assertEqual(r["status"],STATUS)
        self.assertEqual(r["summary"]["2025_player_games"],1)
        self.assertEqual(r["by_season"]["2025"]["player_game_ledger"][0]["date"],"2026-01-02")
        self.assertEqual(r["summary"]["athletes_observed_both_seasons"],1)
        self.assertEqual(r["summary"]["athletes_with_changed_team_ids"],1)
        self.assertFalse(r["changed_team_association_examples"][0]["transfer_eligibility_verified"])
        self.assertTrue(r["no_prop_bookmaker_lines_implied"])

    def test_player_team_does_not_match_game_then_excluded(self):
        b,s=fixture();b[2025][0]["team_id"]=900
        r=assemble(b,s,AT)
        self.assertEqual(r["by_season"]["2025"]["player_game_rows"],0)
        self.assertEqual(r["summary"]["athletes_observed_both_seasons"],0)
        self.assertEqual(r["by_season"]["2025"]["skipped_player_stat_rows"]["NO_MATCHED_ESPN_GAME_TEAM_ID"],1)

    def test_invalid_fixture_and_unfinished_game_not_injected(self):
        b,s=fixture();s[2024][0]["completed"]=False
        r=assemble(b,s,AT)
        self.assertEqual(r["summary"]["2024_player_games"],0)
        self.assertEqual(r["by_season"]["2024"]["skipped_schedule_rows"]["UNCOMPLETED_GAME"],1)

    def test_current_football_game_does_not_become_2025_prior(self):
        b,s=fixture();s[2025][0]["start_date"]="2026-11-02T19:00:00Z"
        r=assemble(b,s,AT)
        self.assertEqual(r["summary"]["2025_player_games"],0)

    def test_duplicate_game_and_team_member_rejected(self):
        b,s=fixture();s[2024].append(s[2024][0].copy())
        with self.assertRaises(ValueError):
            assemble(b,s,AT)
        b,s=fixture();b[2024].append(b[2024][0].copy())
        with self.assertRaises(ValueError):
            assemble(b,s,AT)

if __name__=="__main__":
    unittest.main()

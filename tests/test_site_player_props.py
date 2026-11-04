"""Site player projections are conditional, and score-model provenance immutable."""
import copy
import unittest

from scripts.site_player_props import overlay,STATUS

OBS="2026-10-30T19:00:00Z"
KICK="2026-10-31T20:00:00Z"

def schedule(year):
    games=[]
    for i in (1,2,3):
        games.append({"game_id":year*100+i,"season":year,
            "completed":True,"fbs_participant":True,"start_time_tbd":False,
            "start_date":f"{year}-09-{i:02d}T19:00:00Z",
            "home_id":10,"away_id":20,"home_team":"A","away_team":"B"})
    if year==2026:
        games.append({"game_id":999,"season":2026,
            "completed":False,"fbs_participant":True,"start_time_tbd":False,
            "start_date":KICK,"home_id":10,"away_id":20,
            "home_team":"A","away_team":"B"})
    return games

def boxes(year):
    output=[]
    for i in (1,2,3):
        gid=year*100+i
        for team,pid,name in ((10,111,"QB One"),(20,222,"QB Two")):
            output.append({"game_id":gid,"season":year,"team_id":team,
                "athlete_id":pid,"athlete_name":name,"category":"passing",
                "passingYards":str(200+i*10),"passingTouchdowns":"2",
                "interceptions":"0","completions/passingAttempts":"20/30"})
        for team,pid,name in ((10,333,"RB One"),(20,444,"RB Two")):
            output.append({"game_id":gid,"season":year,"team_id":team,
                "athlete_id":pid,"athlete_name":name,"category":"rushing",
                "rushingYards":str(90+i*3),"rushingAttempts":"15",
                "rushingTouchdowns":"1"})
        for team,pid,name in ((10,555,"WR One"),(20,666,"WR Two")):
            output.append({"game_id":gid,"season":year,"team_id":team,
                "athlete_id":pid,"athlete_name":name,"category":"receiving",
                "receivingYards":str(70+i*2),"receptions":"5",
                "receivingTouchdowns":"1"})
    return output

def board():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED",
        "model":"V03","games":[{"game_id":"999","home_team":"A","away_team":"B",
         "kickoff_utc":KICK,"model_home_margin":4.3,"model_total":48.5,
         "model_home_points":26.4,"model_away_points":22.1,
         "qb_availability_home":[],"qb_availability_away":[],
         "qb_depth_home":[{"player":"QB One","rank":1},{"player":"Replacement QB","rank":2}],
         "qb_depth_away":[{"player":"QB Two","rank":1}]}]}

class SitePlayerFormTests(unittest.TestCase):
    def test_sourced_upcoming_player_stat_outlook_not_betting_prop(self):
        original=board()
        out=overlay(original,boxes(2026),boxes(2025),schedule(2026),schedule(2025),OBS)
        self.assertEqual(out["player_prop_display"]["status"],STATUS)
        self.assertEqual(out["player_prop_display"]["covered_games"],1)
        row=out["games"][0]
        self.assertEqual(len(row["player_props"]["entries"]),6)
        self.assertEqual(row["model_home_margin"],4.3)
        self.assertIsInstance(row["player_props"]["entries"][0]["recent_four_baseline_yards"],float)
        self.assertEqual(row["model_total"],48.5)
        self.assertEqual(row["player_props"]["real_bookmaker_prop_lines"],0)
        self.assertFalse(out["player_prop_display"]["model_scores_updated"])
        self.assertTrue(all(p["real_bookmaker_line"] is None and p["over_probability"] is None
            for p in row["player_props"]["entries"]))
        self.assertTrue(all(p["player_participation_status"]!="CONFIRMED_ACTIVE"
            for p in row["player_props"]["entries"]))

    def test_no_current_qb_evidence_passes_passing_projection_even_with_stats(self):
        src=board()
        src["games"][0]["qb_depth_home"]=[]
        src["games"][0]["qb_depth_away"]=[]
        src["games"][0]["qb_home"]={"player":"QB One","status":"RECENT_GAME_PASSER"}
        out=overlay(src,boxes(2026),boxes(2025),schedule(2026),schedule(2025),OBS)
        entries=out["games"][0]["player_props"]["entries"]
        self.assertFalse(any(p["metric"]=="passing_yards" for p in entries))
        self.assertEqual(out["player_prop_display"]["unavailable_by_reason"][
            "NO_CURRENT_STARTER_OR_DEPTH_CHART_QB"],2)
        self.assertTrue(out["player_prop_display"][
            "history_only_passing_leaders_not_projections"])

    def test_depth_projected_qb_not_replaced_by_more_productive_previous_passer(self):
        src=board()
        src["games"][0]["qb_depth_home"]=[
            {"player":"Replacement QB","rank":1},{"player":"QB One","rank":2}]
        extra=[]
        for i in (1,2,3):
            extra.append({"game_id":202600+i,"season":2026,"team_id":10,
                 "athlete_id":777,"athlete_name":"Replacement QB",
                 "category":"passing","passingYards":"120",
                 "passingTouchdowns":"1","interceptions":"0",
                 "completions/passingAttempts":"9/20"})
        out=overlay(src,boxes(2026)+extra,boxes(2025),
                    schedule(2026),schedule(2025),OBS)
        home=[p for p in out["games"][0]["player_props"]["entries"]
              if p["metric"]=="passing_yards" and p["team_side"]=="home"]
        self.assertEqual(len(home),1)
        self.assertEqual(home[0]["player"],"Replacement QB")
        self.assertEqual(home[0]["qb_identity_evidence"],
                         "THIRD_PARTY_DEPTH_CHART_PROJECTION")
        self.assertTrue(home[0]["not_confirmed_starter"])

    def test_passing_projection_uses_exact_same_qb_decision_as_website(self):
        src=board()
        out=overlay(src,boxes(2026),boxes(2025),
                    schedule(2026),schedule(2025),OBS)
        g=out["games"][0]
        self.assertEqual(g["qb_pregame_home"]["player"],"QB One")
        self.assertEqual(g["qb_pregame_home"]["status"],"PROJECTED_DEPTH_CHART")
        self.assertEqual(next(p for p in g["player_props"]["entries"]
                              if p["metric"]=="passing_yards" and
                              p["team_side"]=="home")["player"],
                         g["qb_pregame_home"]["player"])
        self.assertFalse(g["qb_pregame_home"]["historical_passing_leader_used"])

    def test_stale_or_divergent_pregame_identity_fails_closed(self):
        src=board()
        src["games"][0]["qb_pregame_home"]={
            "player":"QB One","status":"CONFIRMED_THIS_GAME"}
        with self.assertRaisesRegex(ValueError,"Conflicting quarterback identity"):
            overlay(src,boxes(2026),boxes(2025),
                    schedule(2026),schedule(2025),OBS)

    def test_old_qb_rushing_volume_does_not_replace_current_qb(self):
        src=board()
        src["games"][0]["qb_depth_home"]=[
            {"player":"Replacement QB","rank":1},
            {"player":"QB One","rank":2}]
        current=boxes(2026)
        for i in (1,2,3):
            current.extend([
                {"game_id":202600+i,"season":2026,"team_id":10,
                 "athlete_id":111,"athlete_name":"QB One",
                 "category":"rushing","rushingYards":"180",
                 "rushingAttempts":"13","rushingTouchdowns":"1"},
                {"game_id":202600+i,"season":2026,"team_id":10,
                 "athlete_id":777,"athlete_name":"Replacement QB",
                 "category":"passing","passingYards":"110",
                 "passingTouchdowns":"1","interceptions":"0",
                 "completions/passingAttempts":"12/20"}])
        out=overlay(src,current,boxes(2025),schedule(2026),
                    schedule(2025),OBS)
        g=out["games"][0]
        self.assertFalse(any(p["player"]=="QB One" and p["metric"]=="rushing_yards"
                             for p in g["player_props"]["entries"]))
        self.assertEqual(g["qb_pregame_home"]["player"],"Replacement QB")
        self.assertGreaterEqual(out["player_prop_display"]["unavailable_by_reason"][
            "QB_RUSHER_NOT_CURRENT_EXPECTED_QB"],1)

    def test_official_out_qb_excluded_without_assuming_backup(self):
        src=board()
        src["games"][0]["qb_availability_home"]=[{"player":"QB One","status":"OUT"}]
        out=overlay(src,boxes(2026),boxes(2025),schedule(2026),schedule(2025),OBS)
        self.assertFalse(any(p["player"]=="QB One" for p in out["games"][0]["player_props"]["entries"]))
        self.assertFalse(out["player_prop_display"]["all_player_participation_verified"])

    def test_official_season_out_qb_is_not_selected_by_historical_yardage(self):
        src=board()
        src["games"][0]["official_longterm_qb_absences_home"]=[
            {"player":"QB One","position":"QB",
             "designation":"OUT_REMAINDER_2026",
             "status":"OFFICIAL_SEASON_OUT_VERIFIED_AFTER_SOURCE_REVIEW"},
            {"player":"QB Three","position":"QB",
             "designation":"OUT_REMAINDER_2026",
             "status":"OFFICIAL_SEASON_OUT_VERIFIED_AFTER_SOURCE_REVIEW"}]
        current=boxes(2026)
        for i in (1,2,3):
            current.extend([
                {"game_id":202600+i,"season":2026,"team_id":10,
                 "athlete_id":111,"athlete_name":"QB One",
                 "category":"rushing","rushingYards":"80",
                 "rushingAttempts":"10","rushingTouchdowns":"1"},
                {"game_id":202600+i,"season":2026,"team_id":10,
                 "athlete_id":777,"athlete_name":"Replacement QB",
                 "category":"passing","passingYards":"150",
                 "passingTouchdowns":"1","interceptions":"0",
                 "completions/passingAttempts":"12/20"}])
        before=src["games"][0]["model_home_margin"]
        out=overlay(src,current,boxes(2025),schedule(2026),schedule(2025),OBS)
        entries=out["games"][0]["player_props"]["entries"]
        self.assertFalse(any(p["player"]=="QB One" for p in entries))
        self.assertEqual(next(p for p in entries if p["metric"]=="passing_yards"
                              and p["team_side"]=="home")["player"],"Replacement QB")
        self.assertEqual(out["games"][0]["model_home_margin"],before)
        self.assertGreaterEqual(out["player_prop_display"]["unavailable_by_reason"][
            "OFFICIAL_UNIVERSITY_SEASON_OUT_QB"],2)

    def test_verified_game_starter_excludes_other_passer_without_changing_scores(self):
        src=board()
        src["games"][0]["qb_home"]={"status":"CONFIRMED_OFFICIAL","player":"Different QB"}
        out=overlay(src,boxes(2026),boxes(2025),schedule(2026),schedule(2025),OBS)
        entries=out["games"][0]["player_props"]["entries"]
        self.assertFalse(any(p["player"]=="QB One" and p["metric"]=="passing_yards"
                             for p in entries))
        self.assertEqual(out["games"][0]["model_total"],48.5)

    def test_all_position_injuries_suppress_out_and_flag_questionable(self):
        src=board()
        src["games"][0]["player_availability_home"]=[
            {"player":"RB One","position":"RB","status":"OUT"},
            {"player":"WR One","position":"WR","status":"QUESTIONABLE"}]
        out=overlay(src,boxes(2026),boxes(2025),schedule(2026),schedule(2025),OBS)
        entries=out["games"][0]["player_props"]["entries"]
        self.assertFalse(any(p["player"]=="RB One" for p in entries))
        receiver=next(p for p in entries if p["player"]=="WR One")
        self.assertEqual(receiver["official_reported_status"],"QUESTIONABLE")
        self.assertEqual(receiver["player_participation_status"],
                         "RECENT_GAME_PARTICIPANT_NOT_CONFIRMED")
        self.assertIsNone(receiver["real_bookmaker_line"])
        self.assertEqual(out["games"][0]["model_home_margin"],4.3)
        self.assertGreaterEqual(out["player_prop_display"]["official_status_flagged_entries"],1)
        self.assertFalse(out["player_prop_display"]["role_shares_changed_yard_projections"])

    def test_recent_recorded_workload_is_present_but_not_snap_share(self):
        r=overlay(board(),boxes(2026),boxes(2025),schedule(2026),schedule(2025),OBS)
        qb=next(p for p in r["games"][0]["player_props"]["entries"]
                if p["player"]=="QB One" and p["metric"]=="passing_yards")
        role=qb["workload_role_evidence"]
        self.assertEqual(role["role_basis"],"TEAM_RECORDED_PASS_ATTEMPT_SHARE")
        self.assertEqual(role["recorded_opportunity_share"],1.0)
        self.assertTrue(role["share_is_not_snap_or_target_percentage"])
        self.assertFalse(qb["workload_share_used_to_change_yard_projection"])
        self.assertFalse(r["player_prop_display"]["all_player_participation_verified"])

    def test_mismatch_is_unavailable_and_no_score_tampering(self):
        src=board()
        src["games"][0]["home_team"]="Wrong University"
        before=copy.deepcopy(src["games"][0])
        out=overlay(src,boxes(2026),boxes(2025),schedule(2026),schedule(2025),OBS)
        self.assertEqual(out["games"][0]["player_props"]["status"],"PLAYER_OUTLOOK_UNAVAILABLE")
        self.assertEqual(out["games"][0]["model_home_points"],before["model_home_points"])
        self.assertEqual(out["player_prop_display"]["covered_games"],0)

    def test_completed_or_future_box_cannot_make_fake_pregame_outlook(self):
        src=board()
        extra={"game_id":999,"season":2026,"team_id":10,"athlete_id":777,
            "athlete_name":"Unknown Future","category":"passing",
            "passingYards":"1000","passingTouchdowns":"6",
            "interceptions":"0","completions/passingAttempts":"60/70"}
        out=overlay(src,boxes(2026)+[extra],boxes(2025),
                    schedule(2026),schedule(2025),OBS)
        self.assertFalse(any(p["player"]=="Unknown Future"
            for p in out["games"][0]["player_props"]["entries"]))
        with self.assertRaises(ValueError):
            overlay(board(),boxes(2026),boxes(2025),
                    schedule(2026),schedule(2025),"2026-11-01T00:00:00Z")

if __name__=="__main__":
    unittest.main()

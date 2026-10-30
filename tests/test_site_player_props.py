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
         "qb_availability_home":[],"qb_availability_away":[]}]}

class SitePlayerFormTests(unittest.TestCase):
    def test_sourced_upcoming_player_stat_outlook_not_betting_prop(self):
        original=board()
        out=overlay(original,boxes(2026),boxes(2025),schedule(2026),schedule(2025),OBS)
        self.assertEqual(out["player_prop_display"]["status"],STATUS)
        self.assertEqual(out["player_prop_display"]["covered_games"],1)
        row=out["games"][0]
        self.assertEqual(len(row["player_props"]["entries"]),6)
        self.assertEqual(row["model_home_margin"],4.3)
        self.assertEqual(row["model_total"],48.5)
        self.assertEqual(row["player_props"]["real_bookmaker_prop_lines"],0)
        self.assertFalse(out["player_prop_display"]["model_scores_updated"])
        self.assertTrue(all(p["real_bookmaker_line"] is None and p["over_probability"] is None
            for p in row["player_props"]["entries"]))
        self.assertTrue(all(p["player_participation_status"]!="CONFIRMED_ACTIVE"
            for p in row["player_props"]["entries"]))

    def test_official_out_qb_excluded_without_assuming_backup(self):
        src=board()
        src["games"][0]["qb_availability_home"]=[{"player":"QB One","status":"OUT"}]
        out=overlay(src,boxes(2026),boxes(2025),schedule(2026),schedule(2025),OBS)
        self.assertFalse(any(p["player"]=="QB One" for p in out["games"][0]["player_props"]["entries"]))
        self.assertFalse(out["player_prop_display"]["all_player_participation_verified"])

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

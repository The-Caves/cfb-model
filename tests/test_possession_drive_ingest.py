"""Verify genuine ESPN possession attribution rather than inferring from final scores."""
import copy
import unittest
from scripts.possession_drive_ingest import parse,_category,_field_position,STATUS

STAMP="2026-11-13T19:00:00Z"
def fixture(pick_six=False):
    home=7 if pick_six else 0
    away=0
    g={"game_id":"401111111","date":"2026-11-06",
       "kickoff_utc":"2026-11-06T23:00:00Z",
       "home":"Home Panthers","away":"Away Bears",
       "home_score":str(home),"away_score":str(away)}
    comp={"status":{"type":{"completed":True}},"competitors":[
       {"homeAway":"home","team":{"displayName":"Home Panthers","id":"111"},"score":str(home)},
       {"homeAway":"away","team":{"displayName":"Away Bears","id":"222"},"score":str(away)}]}
    box={"teams":[
       {"team":{"displayName":"Home Panthers"},"statistics":[{"name":"turnovers","displayValue":"0"}]},
       {"team":{"displayName":"Away Bears"},"statistics":[{"name":"turnovers","displayValue":"1" if pick_six else "0"}]}]}
    drives=[]
    for i in range(12):
        is_away=(i%2==0)
        team="222" if is_away else "111"
        turnover=pick_six and i==0
        after_home=home if pick_six else 0
        drive={"id":"d"+str(i),"team":{"id":team},"result":"INT TD" if turnover else "PUNT",
          "offensivePlays":5,"yards":20,
          "plays":[{"id":"p"+str(i),"type":{"text":"Rush"},"homeScore":after_home,
               "awayScore":0,"start":{"team":{"id":team},"yardsToEndzone":75},
               "end":{"team":{"id":team},"yardsToEndzone":65}}]}
        drives.append(drive)
    return g,{"header":{"competitions":[comp]},"boxscore":box,
              "drives":{"previous":drives}}

class DriveIngestTests(unittest.TestCase):
    def test_all_zero_drive_score_reconciles(self):
        game,data=fixture()
        report=parse(game,data,STAMP)
        self.assertEqual(report["scoreboard_and_boxscore_reconciled"],True)
        self.assertEqual(len(report["drives"]),12)
        self.assertEqual(report["drives"][0]["start_yards_to_goal"],75)
        self.assertEqual(report["drives"][0]["field_zone"],"own_half")
        self.assertEqual(sum(d["offense_points"] for d in report["drives"]),0)
    def test_defensive_pick_six_never_becomes_offensive_points(self):
        game,data=fixture(True)
        report=parse(game,data,STAMP)
        self.assertEqual(report["drives"][0]["result"],"INTERCEPTION")
        self.assertEqual(report["drives"][0]["offense_points"],0)
        self.assertEqual(report["drives"][0]["defense_points"],7)
        self.assertTrue(report["drives"][0]["turnover"])
        self.assertEqual(report["turnovers_verified"]["Away Bears"],1)
        self.assertEqual(sum(d["offense_points"] for d in report["drives"]),0)
        self.assertEqual(sum(d["defense_points"] for d in report["drives"]),7)
    def test_mismatch_sources_fail_closed(self):
        game,data=fixture(True)
        wrong=copy.deepcopy(data)
        wrong["drives"]["previous"][0]["plays"][0]["homeScore"]=0
        with self.assertRaisesRegex(ValueError,"reconcile"):
            parse(game,wrong,STAMP)
        wrong=copy.deepcopy(data)
        wrong["boxscore"]["teams"][1]["statistics"][0]["displayValue"]="0"
        with self.assertRaisesRegex(ValueError,"turnovers"):
            parse(game,wrong,STAMP)
        wrong=copy.deepcopy(data)
        wrong["drives"]["previous"][0]["plays"][0]["start"]["team"]["id"]="333"
        with self.assertRaisesRegex(ValueError,"field position"):
            parse(game,wrong,STAMP)
    def test_critical_result_categories(self):
        self.assertEqual(_category("INT TD"),"INTERCEPTION")
        self.assertEqual(_category("FUMBLE TD"),"FUMBLE")
        self.assertEqual(_category("TOUCHDOWN"),"TD")
        self.assertEqual(_category("MISSED FG"),"MISSED_FG")
        self.assertEqual(_category("FG"),"FG")
        self.assertIsNone(_category("MAGICAL RESULT"))
    def test_postkickoff_source_gate(self):
        game,data=fixture()
        with self.assertRaisesRegex(ValueError,"already completed"):
            parse(game,data,"2026-11-06T21:00:00Z")

if __name__=="__main__":
    unittest.main()

import unittest
from scripts.ingest_advanced import per_game_features,aggregate_team_profiles,truth,merge_drives
class AdvancedTests(unittest.TestCase):
    def ledger(self):
        return {"77":{"game_id":"77","date":"2026-09-01","home":"Home","away":"Away",
                      "home_score":"28","away_score":"14"}}
    def make(self,home=25,away=25,hs=28):
        rows=[]
        for i in range(home+away):
            is_home=i<home
            rows.append({"game_id":77,"season":2026,"pos_team_id":1 if is_home else 2,
                "homeTeamId":1,"awayTeamId":2,"homeFinalScore":hs,"awayFinalScore":14,
                "status_type_completed":True,"pass":i%2==0,"rush":i%2!=0,
                "EPA":.2 if is_home else -.3,"EPA_success":is_home,
                "statYardage":22 if i%2==0 else 5,"down":1,
                "start.yardsToEndzone":55,"qb_hurry":False,"sack":False})
        return rows
    def test_true_values(self):
        self.assertIsNone(truth(None));self.assertFalse(truth("false"));self.assertTrue(truth("true"))
    def test_two_sides_and_epa(self):
        rows,qa=per_game_features(self.make(),self.ledger(),"2026-10-20")
        self.assertEqual(qa["games_accepted"],1)
        self.assertEqual(len(rows),2)
        p=aggregate_team_profiles(rows,["Home","Away","Absent"],"2026-10-20","2026-10-21T00:00Z")
        self.assertEqual([x["games_covered"] for x in p],[0,1,1])
        h=next(x for x in p if x["team"]=="Home")
        self.assertEqual(h["off_epa_per_play"],.2)
        self.assertEqual(h["def_epa_allowed_per_play"],-.3)
        self.assertEqual(h["betting_status"],"PASS_UNVALIDATED")
        self.assertEqual(h["drives_observed"],"")

    def test_two_sided_drive_join(self):
        teamrows,qa=per_game_features(self.make(),self.ledger(),"2026-10-20")
        drive_rows=[
            {"season":2026,"game_id":77,"pos_team":1,"drives":10,
             "yards_per_drive":37,"plays_per_drive":6.1,"avg_field_position":62},
            {"season":2026,"game_id":77,"pos_team":2,"drives":8,
             "yards_per_drive":22,"plays_per_drive":5.4,"avg_field_position":70}]
        report=merge_drives(teamrows,drive_rows,self.ledger())
        self.assertEqual(report["drive_rows_applied"],2)
        self.assertEqual(report["complete_game_pairs"],1)
        p=aggregate_team_profiles(teamrows,["Home","Away"],"2026-10-20","now")
        home=next(x for x in p if x["team"]=="Home")
        self.assertEqual(home["drives_observed"],10)
        self.assertEqual(home["yards_per_drive"],37)
        self.assertEqual(home["provider_mean_yards_to_goal_per_play"],62)

    def test_drive_names_in_actual_2026_release(self):
        teamrows,_=per_game_features(self.make(),self.ledger(),"2026-10-20")
        drive_rows=[
            {"season":2026,"game_id":77,"pos_team":"Home","drives":10,
             "yards_per_drive":37,"plays_per_drive":6.1,"avg_field_position":62},
            {"season":2026,"game_id":77,"pos_team":"Away","drives":8,
             "yards_per_drive":22,"plays_per_drive":5.4,"avg_field_position":70}]
        qa=merge_drives(teamrows,drive_rows,self.ledger())
        self.assertEqual(qa["drive_rows_applied"],2)
        self.assertEqual(qa["match_kinds"]["matched_by_exact_game_team_name"],2)
    def test_unmatched_drive_team_and_incomplete_pair(self):
        teamrows,_=per_game_features(self.make(),self.ledger(),"2026-10-20")
        drive_rows=[{"season":2026,"game_id":77,"pos_team":1,"drives":10,
                     "yards_per_drive":37,"plays_per_drive":6,"avg_field_position":62}]
        qa=merge_drives(teamrows,drive_rows,self.ledger())
        self.assertEqual(qa["drive_rows_applied"],0)
        self.assertEqual(qa["complete_game_pairs"],0)
    def test_score_conflict_quarantines_entire_game(self):
        rows,qa=per_game_features(self.make(hs=30),self.ledger(),"2026-10-20")
        self.assertEqual(len(rows),0)
        self.assertEqual(qa["games_quarantined"],1)
    def test_incomplete_game_quarantined(self):
        rows,qa=per_game_features(self.make(home=25,away=3),self.ledger(),"2026-10-20")
        self.assertEqual(len(rows),0)
        self.assertEqual(qa["games_quarantined"],1)
    def test_future_cutoff(self):
        games=self.ledger()
        games["77"]["date"]="2026-10-21"
        rows,qa=per_game_features(self.make(),games,"2026-10-21")
        self.assertEqual(len(rows),0)
if __name__=="__main__":unittest.main()

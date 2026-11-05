"""Source-reconciled team attempts / drive counts from ESPN 2026 releases."""
import copy
import unittest

from scripts.player_prop_team_box_source import assemble, STATUS
from scripts.player_prop_team_budget import prepare
from scripts.player_prop_joint_simulation import simulate
from test_player_prop_joint_simulation import fitted,player_history,target,DEC,KICK


def inputs():
    schedule=[{"game_id":"200","season":2026,"completed":False,
        "start_time_tbd":False,"fbs_participant":True,
        "start_date":KICK,"home_id":10,"away_id":20,
        "home_team":"A","away_team":"B"}]
    box=[];drives=[]
    for i in range(1,5):
        schedule.append({"game_id":str(i),"season":2026,"completed":True,
           "start_time_tbd":False,"fbs_participant":True,
           "start_date":f"2026-09-{i+1:02d}T20:00:00Z",
           "home_id":10,"away_id":20,"home_team":"A","away_team":"B"})
        for team,side,pas,rush in ((10,"home",25,30),(20,"away",21,35)):
            box.append({"game_id":str(i),"season":2026,
                "team_id":team,"home_away":side,
                "completionAttempts":f"15/{pas}",
                "rushingAttempts":str(rush)})
            for d in range(1,11):
                drives.append({"game_id":str(i),"season":2026,
                    "team_id":team,"drive_id":f"{i}-{team}-{d}"})
    t=target();t["team_ids"]={"home":"10","away":"20"}
    return box,drives,schedule,t


class SourceAdapterTests(unittest.TestCase):
    def test_captured_paired_teams_with_real_espn_schema_and_drive_identity(self):
        box,drives,schedule,t=inputs()
        orig=copy.deepcopy((box,drives,schedule,t))
        b,p,summary=assemble(box,drives,schedule,t,DEC)
        self.assertEqual((box,drives,schedule,t),orig)
        self.assertEqual(summary["status"],STATUS)
        self.assertEqual(summary["matched_historical_games_for_target"],4)
        self.assertEqual(summary["historical_team_rows"],8)
        self.assertEqual(len(p["rows"]),8)
        self.assertEqual(b["rows"][0]["captured_at_utc"],b["observed_at_utc"])
        self.assertFalse(summary["historical_publication_time_authenticated"])
        self.assertFalse(b["source_revision_first_published_before_decision"])
        self.assertTrue(all(r["team_possessions"]==10 for r in p["rows"]))
        history,ready=prepare(b,t,p["rows"],DEC)
        self.assertEqual(ready,"READY_CONDITIONAL_BUDGET_SHADOW")
        self.assertEqual(len(history["home"]),4)
        z=simulate(fitted(),player_history(),p,t,DEC,trials=100,seed=1,
                   team_attempt_budgets=b)
        self.assertTrue(z["team_attempt_budget_applied"])
        self.assertEqual(z["player_scenarios"][0]["metrics"]["passing_attempts"]["mean"],25)
        self.assertFalse(z["model_promoted"])

    def test_missing_or_corrupt_team_stats_and_drives_cannot_be_claimed_complete(self):
        box,drives,schedule,t=inputs()
        box=box[:-1]
        b,p,r=assemble(box,drives,schedule,t,DEC)
        self.assertEqual(r["matched_historical_games_for_target"],3)
        self.assertEqual(r["skipped_by_reason"]["INVALID_OR_INCOMPLETE_TWO_SIDED_TEAM_BOX"],1)
        box,drives,schedule,t=inputs()
        box[0]["completionAttempts"]="31/20"
        b,p,r=assemble(box,drives,schedule,t,DEC)
        self.assertEqual(r["matched_historical_games_for_target"],3)
        box,drives,schedule,t=inputs()
        drives=[d for d in drives if not(d["game_id"]=="1" and d["team_id"]==20)]
        b,p,r=assemble(box,drives,schedule,t,DEC)
        self.assertEqual(r["skipped_by_reason"]["INCOMPLETE_OR_AMBIGUOUS_DRIVE_IDS"],1)
        box,drives,schedule,t=inputs()
        drives.append(dict(drives[0]))
        b,p,r=assemble(box,drives,schedule,t,DEC)
        self.assertEqual(r["matched_historical_games_for_target"],3)

    def test_no_leak_of_same_day_games_and_no_forged_kickoff(self):
        box,drives,schedule,t=inputs()
        schedule[1]["start_date"]="2026-10-30T19:00:00Z" # decision time
        b,p,r=assemble(box,drives,schedule,t,DEC)
        self.assertEqual(r["matched_historical_games_for_target"],3)
        box,drives,schedule,t=inputs()
        t["kickoff_utc"]="2026-11-01T20:00:00Z"
        with self.assertRaisesRegex(ValueError,"Target football date"):
            assemble(box,drives,schedule,t,DEC)
        box,drives,schedule,t=inputs()
        t["team_ids"]["home"]="999"
        with self.assertRaisesRegex(ValueError,"team-game identity"):
            assemble(box,drives,schedule,t,DEC)


if __name__=="__main__":
    unittest.main()

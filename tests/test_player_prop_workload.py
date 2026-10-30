import unittest
from scripts.player_prop_workload import evidence,player_role_index,role_summary,evaluate
from scripts.player_prop_history import from_box_rows

OBS="2026-10-30T19:00:00Z"
def sample():
    games={}
    records=[]
    for idx,(key,pa,ra,rec) in enumerate([(101,20,25,12),(102,30,30,18),
                                             (103,25,20,15),(104,40,35,25)],1):
        day=f"2026-09-{idx*7:02d}"
        games[str(key)]={"game_id":str(key),"date":day,
            "kickoff_utc":day+"T18:00:00Z","home":"A","away":"B"}
        def row(team,pid,name,category,**cols):
            records.append({"game_id":str(key),"season":2026,"team_id":team,
                "athlete_id":pid,"athlete_name":name,"category":category,**cols})
        row(10,1,"QB","passing",**{"passingYards":"150","completions/passingAttempts":f"{rec}/{pa}",
                                   "passingTouchdowns":"1","interceptions":"0"})
        row(10,2,"RB","rushing",rushingAttempts=str(ra//2),rushingYards="60",rushingTouchdowns="1")
        row(10,3,"Other RB","rushing",rushingAttempts=str(ra-ra//2),rushingYards="62",rushingTouchdowns="0")
        row(10,4,"WR","receiving",receptions=str(rec//2),receivingYards="70",receivingTouchdowns="1")
        row(10,5,"Other WR","receiving",receptions=str(rec-rec//2),receivingYards="80",receivingTouchdowns="0")
    return from_box_rows(records,games,OBS)

class RoleWorkloadTests(unittest.TestCase):
    def test_role_shares_use_recorded_stats_not_snap_or_target(self):
        s=sample();h,teams,excluded=player_role_index(s["rows"],OBS)
        p=role_summary(h,10,2,"rushing_yards")
        self.assertIsNotNone(p)
        self.assertLess(p["recorded_opportunity_share"],.6)
        self.assertTrue(p["share_is_not_snap_or_target_percentage"])
        receiver=role_summary(h,10,4,"receiving_yards")
        self.assertEqual(receiver["role_basis"],
                         "TEAM_RECORDED_COMPLETION_SHARE_NOT_TARGET_SHARE")
        self.assertTrue(receiver["participation_not_confirmed"])
    def test_no_completions_catches_mismatch_fabricates_receiver_share(self):
        s=sample()
        for r in s["rows"]:
            if r["player_id"]=="5":r["values"]["receptions"]=1
        rows,excluded=evidence(s["rows"])
        self.assertNotIn("receiving_yards",[r["metric"] for r in rows])
        self.assertGreater(excluded.get("RECEPTIONS_DO_NOT_RECONCILE_RECORDED_COMPLETIONS",0),0)
    def test_retrospective_paired_comparison_and_prior_date_embargo(self):
        s=sample();r=evaluate(s,start="2026-09-21")
        self.assertEqual(r["status"],"CFB_ROLE_OPPORTUNITY_WALKFORWARD_RESEARCH_ONLY")
        self.assertEqual(r["summary"]["rushing_yards"]["paired_recorded_stat_player_games"],2)
        self.assertIsNotNone(r["summary"]["passing_yards"]["role_candidate_mean_abs_error"])
        self.assertFalse(r["model_promoted"])
    def test_unknown_missing_player_category_not_zero_filled(self):
        s=sample();s["rows"]=[r for r in s["rows"] if r["player_id"]!="2"]
        r=evaluate(s,start="2026-09-21")
        self.assertTrue(r["missing_player_is_not_zero_filled"])
        self.assertFalse(any(x["player_id"]=="2" for
            x in r["sample_predictions"]["rushing_yards"]))
    def test_duplicate_or_bad_snapshot_rejected(self):
        s=sample();s["rows"].append(dict(s["rows"][0]))
        with self.assertRaises(ValueError):evidence(s["rows"])
        s=sample();s["status"]="unknown"
        with self.assertRaises(ValueError):evaluate(s)

if __name__=="__main__":unittest.main()

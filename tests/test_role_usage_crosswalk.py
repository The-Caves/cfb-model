import unittest
from scripts.role_usage_crosswalk import audit,STATUS
NOW="2026-10-30T21:00:00Z"
HASH={k:"a"*64 for k in ("roster_2025","roster_2026",
                         "offense_usage_2026","defense_usage_2026")}
def fixture():
    return {
      "roster_2025":[{"season":2025,"team_id":20,"athlete_id":999}],
      "roster_2026":[{"season":2026,"team_id":10,"athlete_id":999},
                     {"season":2026,"team_id":11,"athlete_id":888}],
      "offense_usage_2026":[
        {"player_id":"999","pos_team_id":10,"position_group":"RB",
         "touch_share":.32,"target_share":.12,"games":6},
        {"player_id":"888","pos_team_id":11,"position_group":"WR",
         "touch_share":.10,"target_share":.22,"games":4}],
      "defense_usage_2026":[]}
class CrosswalkTests(unittest.TestCase):
    def test_real_athlete_id_transfer_and_opportunity_not_snap_share(self):
        report=audit(fixture(),NOW,HASH)
        self.assertEqual(report["status"],STATUS)
        self.assertEqual(report["eligible_role_records"],2)
        a=next(x for x in report["role_records"] if x["player_id"]=="999")
        self.assertEqual(a["previous_2025_team_ids"],["20"])
        self.assertEqual(a["role_share_basis"],"TEAM_TOUCH_SHARE")
        self.assertEqual(a["role_share"],.32)
        self.assertFalse(a["is_snap_share"])
        self.assertFalse(a["starting_status_confirmed"])
        self.assertFalse(report["model_promoted"])

    def test_missing_role_and_unmatched_team_are_quarantined(self):
        f=fixture()
        f["offense_usage_2026"].append({
            "player_id":"999","pos_team_id":999,"position_group":"RB",
            "touch_share":.2,"target_share":.2,"games":4})
        f["offense_usage_2026"][0]["games"]=1
        result=audit(f,NOW,HASH)
        self.assertEqual(result["eligible_role_records"],1)
        self.assertIn("INSUFFICIENT_PLAYER_OPPORTUNITY_SAMPLE",
                      result["rejected_role_rows_by_reason"])
        self.assertIn("NO_UNAMBIGUOUS_CURRENT_SEASON_ROSTER_ID_MATCH",
                      result["rejected_role_rows_by_reason"])

    def test_ol_qb_no_fake_snap_opportunity_and_defense_tackles_allowed(self):
        f=fixture()
        f["roster_2026"].append({"season":2026,"team_id":10,"athlete_id":77})
        f["offense_usage_2026"].append({
            "player_id":"77","pos_team_id":10,"position_group":"OL",
            "touch_share":.9,"target_share":.8,"games":8})
        f["defense_usage_2026"].append({
            "player_id":"77","def_pos_team_id":10,"position_group":"DL",
            "tackle_share":.14,"games":8})
        result=audit(f,NOW,HASH)
        self.assertEqual(result["eligible_role_records"],3)
        self.assertEqual(result["eligible_role_types"]["SCRIMMAGE_TACKLE_SHARE"],1)
        self.assertNotIn("OL",set(x["position_group"] for x in result["role_records"]))

if __name__=="__main__":
    unittest.main()

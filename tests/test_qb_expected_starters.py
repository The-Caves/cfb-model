import unittest
from scripts.qb_expected_starters import build,STATUS
from scripts.site_depthchart import SOURCE
from scripts.qb_role_features import STATUS as ROLE

AT="2026-10-29T15:00:00Z"
KICK="2026-10-31T20:00:00Z"
def source(names):
    return {"source_type":SOURCE,
      "source_url":"https://www.ourlads.com/ncaa-football-depth-charts/depth-chart.aspx?id=1234&s=team-a",
      "observed_at_utc":"2026-10-29T14:00:00Z","players":names}
def fixtures(latest="A Backup",official=None,availability=None):
    game={"game_id":"100","home":"Team A","away":"Team B","kickoff_utc":KICK,
          "verified_qb_starters":{"Team A":{"player":official}} if official else {},
          "qb_availability_reports":availability or []}
    ctx={"asof_utc":"2026-10-29T13:00:00Z","games":[game]}
    records=[]
    for team,opp in (("Team A","Team B"),("Team B","Team A")):
        records.append({"game_id":"100","team":team,"opponent":opp,"kickoff_utc":KICK,
            "current_starting_qb":official if team=="Team A" else None,
            "last_game_leading_passer_proxy":latest if team=="Team A" else None,
            "season_leading_passer_proxy":"A First" if team=="Team A" else None,
            "official_recent_return_context":None})
    role={"status":ROLE,"asof_utc":"2026-10-29T14:00:00Z",
          "betting_status":"PASS_UNVALIDATED","rows":records}
    return ctx,role
class StarterSourceTests(unittest.TestCase):
    def a(self,result):return next(r for r in result["games"] if r["team"]=="Team A")
    def test_chart_disagrees_with_backup_last_game_starter_is_unknown(self):
        ctx,role=fixtures()
        r=build(ctx,role,{"Team A":source(["A First","A Backup","A Third"])},AT)
        x=self.a(r)
        self.assertIsNone(x["starter"])
        self.assertEqual(x["starter_status"],"CONFLICT_CHART_VS_RECENT_QB")
        self.assertEqual([y["role"] for y in x["scenarios"]],["QB1","QB2","QB3"])
        self.assertEqual(x["depth_label"],"UNKNOWN")
    def test_recent_backup_can_be_expected_if_qb1_explicitly_out(self):
        absence={"team":"Team A","player":"A First","position":"QB","status":"OUT",
         "published_at_utc":"2026-10-29T13:00:00Z","captured_at_utc":"2026-10-29T14:00:00Z"}
        ctx,role=fixtures(availability=[absence])
        r=build(ctx,role,{"Team A":source(["A First","A Backup","A Third"])},AT)
        x=self.a(r)
        self.assertEqual(x["starter"],"A Backup")
        self.assertEqual(x["depth_label"],"QB2")
        self.assertFalse(x["is_confirmed_starter"])
        self.assertEqual(len(x["scenarios"]),2)
    def test_qb2_officially_confirmed_is_not_assumed_worse_than_qb1(self):
        ctx,role=fixtures(official="A Backup")
        r=build(ctx,role,{"Team A":source(["A First","A Backup","A Third"])},AT)
        x=self.a(r)
        self.assertEqual(x["confidence"],"HIGH_OFFICIAL")
        self.assertTrue(x["is_confirmed_starter"])
        self.assertEqual(x["depth_rank"],2)
    def test_chart_plus_latest_passer_is_medium_projected(self):
        ctx,role=fixtures(latest="A First")
        x=self.a(build(ctx,role,{"Team A":source(["A First","A Backup"])},AT))
        self.assertEqual(x["starter"],"A First")
        self.assertEqual(x["confidence"],"MEDIUM_UNCONFIRMED")
    def test_no_chart_uses_recent_passer_but_rank_remains_unknown(self):
        ctx,role=fixtures()
        x=self.a(build(ctx,role,{},AT))
        self.assertEqual(x["starter"],"A Backup")
        self.assertEqual(x["confidence"],"LOW_UNCONFIRMED")
        self.assertIsNone(x["depth_rank"])
    def test_future_or_untrusted_chart_fails_closed(self):
        ctx,role=fixtures()
        chart=source(["A First"]);chart["observed_at_utc"]="2026-11-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            build(ctx,role,{"Team A":chart},AT)
    def test_source_publication_cannot_be_after_issued(self):
        ctx,role=fixtures()
        role["asof_utc"]="2026-11-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"after target"):
            build(ctx,role,{},AT)
if __name__=="__main__":unittest.main()

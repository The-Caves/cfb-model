"""QB official-availability board layer never infers starting QBs or mutates picks."""
import copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
from scripts.site_availability import merge,run
NOW=dt.datetime(2026,10,24,15,tzinfo=dt.timezone.utc)
def board():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED","games":[{
        "game_id":"401","home_team":"Mississippi State Bulldogs","away_team":"Oklahoma Sooners",
        "kickoff_utc":"2026-10-24T19:30:00Z",
        "model_home_margin":3.0,"model_ats_side":"HOME","qb_starters_verified":0,
        "qb_home":{"player":"Billy Puckett","status":"RECENT_GAME_PASSER",
                   "source_url":"https://www.espn.com/game"},
        "qb_away":{"player":None,"status":"UNKNOWN"}}]}
def status(player="Kamario Taylor",designation="QUESTIONABLE",**mod):
    s={"game_id":"401","team":"Mississippi State Bulldogs","kind":"AVAILABILITY",
       "position":"QB","player":player,"status":designation,
       "kickoff_utc":"2026-10-24T19:30:00Z",
       "published_at_utc":"2026-10-24T13:00:00Z",
       "captured_at_utc":"2026-10-24T14:00:00Z",
       "source_url":"https://www.secsports.com/fbreports"}
    s.update(mod)
    return s
class Tests(unittest.TestCase):
    def test_questionable_does_not_change_recent_passer_or_model(self):
        d=merge(board(),[status()],NOW)
        g=d["games"][0]
        self.assertEqual(g["qb_home"]["player"],"Billy Puckett")
        self.assertEqual(g["qb_home"]["status"],"RECENT_GAME_PASSER")
        self.assertEqual(g["qb_availability_home"][0]["player"],"Kamario Taylor")
        self.assertEqual(g["qb_availability_home"][0]["status"],"QUESTIONABLE")
        self.assertEqual(g["model_ats_side"],"HOME")
        self.assertFalse(d["qb_availability_display"]["changes_frozen_model_picks"])
    def test_available_backup_not_confused_with_starter_or_flood_widget(self):
        b=board()
        rows=[status("Kamario Taylor","QUESTIONABLE"),
              status("Parker Puckett","AVAILABLE"),
              status("AJ Swann","AVAILABLE")]
        d=merge(b,rows,NOW)
        self.assertEqual(d["qb_availability_display"]["official_qb_designations"],3)
        self.assertEqual(d["qb_availability_display"]["actionable_qb_designations"],1)
        self.assertEqual([(r["player"],r["status"]) for r in d["games"][0]["qb_availability_home"]],
                         [("Kamario Taylor","QUESTIONABLE")])
        self.assertEqual(d["games"][0]["qb_home"]["status"],"RECENT_GAME_PASSER")
    def test_out_qb_does_not_auto_appoint_backup(self):
        d=merge(board(),[status(designation="OUT")],NOW)
        self.assertEqual(d["games"][0]["qb_home"]["status"],"RECENT_GAME_PASSER")
    def test_out_conflicts_with_official_confirmed_starter(self):
        b=board()
        b["games"][0]["qb_home"]={"player":"Kamario Taylor","status":"CONFIRMED_OFFICIAL","source_url":"https://school.edu/official"}
        g=merge(b,[status(designation="OUT")],NOW)
        self.assertEqual(g["games"][0]["qb_home"]["status"],"CONFLICT_REVIEW")
        self.assertEqual(g["qb_availability_display"]["starter_conflicts"],1)
    def test_future_and_postkickoff_reports_rejected(self):
        for row in [status(published_at_utc="2026-10-24T16:00:00Z"),
                    status(captured_at_utc="2026-10-24T16:00:00Z"),
                    status(kickoff_utc="2026-10-25T19:30:00Z")]:
            self.assertEqual(merge(board(),[row],NOW)["games"][0]["qb_availability_home"],[])
    def test_identity_and_status_safeguards(self):
        for row in [status(team="LSU Tigers"),status(game_id="999"),
                    status(status="CLEAR"),status(position="RB"),
                    status(source_url="http://invalid.example/a")]:
            self.assertEqual(merge(board(),[row],NOW)["games"][0]["qb_availability_home"],[])
    def test_conflicting_same_timestamp_quarantined(self):
        rows=[status(designation="AVAILABLE"),status(designation="OUT")]
        r=merge(board(),rows,NOW)
        self.assertEqual(r["games"][0]["qb_availability_home"][0]["status"],"CONFLICT_REVIEW")
    def test_non_qb_official_reports_cover_every_position_without_inference(self):
        b=board()
        rows=[status("Starting RB","OUT",position="RB"),
              status("Receiver One","QUESTIONABLE",position="WR"),
              status("Left Tackle","AVAILABLE",position="OL"),
              status("Edge One","GAME_TIME_DECISION",position="EDGE")]
        d=merge(b,rows,NOW)
        g=d["games"][0]
        reports=g["player_availability_home"]
        self.assertEqual([(r["position"],r["status"]) for r in reports],
                         [("EDGE","GAME_TIME_DECISION"),("RB","OUT"),("WR","QUESTIONABLE")])
        self.assertEqual(g["qb_availability_home"],[])
        self.assertEqual(d["qb_availability_display"]["official_all_position_designations"],4)
        self.assertEqual(d["qb_availability_display"]["actionable_non_qb_designations"],3)
        self.assertEqual(d["qb_availability_display"]["games_with_actionable_non_qb_reports"],1)
        self.assertFalse(d["qb_availability_display"]["not_listed_player_is_assumed_available"])
        self.assertEqual(g["model_home_margin"],3.0)

    def test_non_qb_conflicting_reports_are_not_silently_resolved(self):
        rows=[status("Starting RB","OUT",position="RB"),
              status("Starting RB","QUESTIONABLE",position="RB")]
        d=merge(board(),rows,NOW)
        self.assertEqual(d["games"][0]["player_availability_home"][0]["status"],"CONFLICT_REVIEW")

    def test_non_qb_postkickoff_or_unknown_status_is_excluded(self):
        rows=[status("Receiver One","OUT",position="WR",
                     captured_at_utc="2026-10-24T21:00:00Z"),
              status("Receiver Two","HEALTHY",position="WR"),
              status("Receiver Three","OUT",position="WR",team="LSU Tigers")]
        d=merge(board(),rows,NOW)
        self.assertEqual(d["games"][0]["player_availability_home"],[])

    def test_live_fetch_cutoff_advances_past_report_capture(self):
        # A live request is captured *after* the initial run() invocation.
        # Latest source must be accepted without hindsight or future input.
        stamp=dt.datetime.now(dt.timezone.utc)
        kickoff=(stamp+dt.timedelta(days=2)).isoformat()
        b=board();g=b["games"][0];g["kickoff_utc"]=kickoff
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"board.json";p.write_text(json.dumps(b))
            def live(games,aliases,path):
                capture=dt.datetime.now(dt.timezone.utc)
                publication=capture-dt.timedelta(minutes=3)
                row=status(kickoff_utc=kickoff,
                           published_at_utc=publication.isoformat(),
                           captured_at_utc=capture.isoformat())
                return [row],{"feeds":{"SEC":{"official_reports_accepted":1}}}
            result=run(p,fetcher=live)
            self.assertEqual(len(result["games"][0]["qb_availability_home"]),1)
            self.assertEqual(result["games"][0]["qb_availability_home"][0]["status"],"QUESTIONABLE")
    def test_io_and_fetched_report_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"dashboard.json";file.write_text(json.dumps(board()))
            def fake(games,aliases,path):
                self.assertEqual(games[0]["date_et"],"2026-10-24")
                return [status()],{"feeds":{"SEC":{"status":"FETCHED","official_reports_accepted":1}}}
            r=run(file,now=NOW,fetcher=fake)
            self.assertEqual(r["qb_availability_display"]["games_with_qb_designations"],1)
if __name__=="__main__":unittest.main()

import csv,json,tempfile,unittest
from pathlib import Path
from scripts.pregame_evidence import create_capture,get_asof_feature,save

def writecsv(path,items):
    with path.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(items[0]))
        w.writeheader();w.writerows(items)
def writejson(path,data):path.write_text(json.dumps(data))
class PregameCaptureTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        self.p={k:root/k for k in ("games.csv","advanced.csv","a.json",
                                   "scores.json","context.json","registry.csv")}
        team1,team2="Texas Longhorns","Oklahoma Sooners"
        self.names=(team1,team2)
        writecsv(self.p["registry.csv"],[{"espn_display_name":t}
                 for t in [team1,team2]+["Fictional College "+str(i) for i in range(136)]])
        g=dict(game_id="past1",date="2026-10-10",
               kickoff_utc="2026-10-10T20:00:00Z",
               home=team1,away=team2,home_score="28",
               away_score="17",neutral="False")
        writecsv(self.p["games.csv"],[g])
        writecsv(self.p["advanced.csv"],[
            dict(game_id="past1",date="2026-10-10",team=team,opponent=opp,
                 off_epa_sum="10",epa_plays="50",def_epa_sum="5",
                 def_epa_plays="50",pass_plays="25",rush_plays="25",
                 scrimmage_plays="50")
            for team,opp in ((team1,team2),(team2,team1))])
        writejson(self.p["a.json"],{
            "status":"RESEARCH_PBP_IMPORTED_DRIVE_JOIN_VERIFIED",
            "betting_status":"PASS_UNVALIDATED","season":2026,
            "historical_pregame_availability_verified":False,
            "retrieved_at_utc":"2026-10-21T23:02:00Z",
            "sources":{"pbp":{"sha256":"a"*64}}})
        writejson(self.p["scores.json"],{
            "status":"SUCCESS","failures":[],"retrieved_at_utc":"2026-10-21T23:01:00Z"})
        writejson(self.p["context.json"],{
            "captured_at_utc":"2026-10-21T23:06:00Z",
            "asof_utc":"2026-10-21T23:05:00Z",
            "games":[dict(game_id="next1",date_et="2026-10-24",
                          kickoff_utc="2026-10-24T20:00:00Z",
                          home=team1,away=team2,
                          home_team_id="12",away_team_id="13")]})
        self.output=root/"captures"
    def capture(self,now="2026-10-21T23:10:00Z"):
        p=self.p
        return create_capture(p["games.csv"],p["advanced.csv"],p["a.json"],
             p["scores.json"],p["context.json"],p["registry.csv"],
             "123456",now=now)
    def test_future_capture_and_asof_lookup(self):
        c=self.capture()
        self.assertEqual(c["qa"]["eligible_games"],1)
        self.assertFalse(c["historical_publication_times_verified"])
        self.assertEqual(get_asof_feature(c,"next1","2026-10-23T12:00:00Z")
                         ["team_profiles"]["home"]["prior_game_ids"],["past1"])
    def test_historical_prediction_cannot_use_later_capture(self):
        with self.assertRaisesRegex(ValueError,"not available"):
            get_asof_feature(self.capture(),"next1","2026-10-20T20:00:00Z")
    def test_prediction_after_kickoff_rejected(self):
        with self.assertRaisesRegex(ValueError,"after kickoff"):
            get_asof_feature(self.capture(),"next1","2026-10-24T20:00:00Z")
    def test_future_source_time_rejected(self):
        with self.assertRaisesRegex(ValueError,"Future source"):
            self.capture(now="2026-10-21T23:01:00Z")
    def test_already_started_event_rejected(self):
        with self.assertRaisesRegex(ValueError,"No eligible future"):
            self.capture(now="2026-10-24T20:00:00Z")
    def test_calendar_date_validation(self):
        c=json.loads(self.p["context.json"].read_text())
        c["games"][0]["date_et"]="2026-10-23"
        writejson(self.p["context.json"],c)
        with self.assertRaisesRegex(ValueError,"No eligible future"):
            self.capture()
    def test_provider_provenance_not_falsified(self):
        a=json.loads(self.p["a.json"].read_text())
        a["historical_pregame_availability_verified"]=True
        writejson(self.p["a.json"],a)
        with self.assertRaisesRegex(ValueError,"Unverified retrospective"):
            self.capture()
    def test_mutated_capture_hash_rejected(self):
        c=self.capture()
        c["games"][0]["team_profiles"]["home"]["recent_form"]["win"]=999
        with self.assertRaisesRegex(ValueError,"checksum mismatch"):
            get_asof_feature(c,"next1","2026-10-23T12:00:00Z")
    def test_append_only_capture_prevents_overwrite(self):
        c=self.capture()
        r=save(c,self.output)
        p=self.output/r["file"]
        original=p.read_bytes()
        with self.assertRaises(FileExistsError):save(c,self.output)
        self.assertEqual(original,p.read_bytes())
    def test_changed_prior_source_changes_profile_evidence(self):
        before=self.capture()
        g=list(csv.DictReader(self.p["games.csv"].open()))
        g[0]["home_score"]="68"
        writecsv(self.p["games.csv"],g)
        after=self.capture()
        self.assertNotEqual(before["games"][0]["team_profiles_sha256"],
                            after["games"][0]["team_profiles_sha256"])
    def test_noncanonical_future_game_is_not_verified(self):
        c=json.loads(self.p["context.json"].read_text())
        c["games"][0]["home"]="Non-FBS"
        writejson(self.p["context.json"],c)
        with self.assertRaisesRegex(ValueError,"No eligible future"):
            self.capture()
if __name__=="__main__":unittest.main()

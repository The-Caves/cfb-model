import tempfile,unittest
from pathlib import Path
from scripts.build_profiles import read_games,build_profiles,write_profiles
HEADER="game_id,date,away,home,away_score,home_score,neutral\n"
class ProfileTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
    def write(self,rows):
        p=Path(self.tmp.name)/"games.csv";p.write_text(HEADER+rows);return p
    def test_asof_excludes_game_day(self):
        p=self.write("1,2026-09-03,B,A,10,28,false\n2,2026-10-20,A,B,70,0,false\n")
        games,qa=read_games(p,"2026-10-20")
        self.assertEqual(len(games),1);self.assertEqual(qa["excluded_on_or_after_asof"],1)
        profile={p["team"]:p for p in build_profiles(games,"2026-10-20")}
        self.assertEqual(profile["A"]["wins"],1)
        self.assertEqual(profile["A"]["points_for_per_game"],28)
        self.assertEqual(profile["A"]["epa_offense"],"")
    def test_duplicate_quarantine(self):
        p=self.write("1,2026-09-03,B,A,10,28,false\n1,2026-09-03,B,A,10,28,false\n")
        games,qa=read_games(p,"2026-10-20")
        self.assertEqual(len(games),1);self.assertEqual(qa["rejected"][0]["reason"],"duplicate game")
    def test_wrong_season_quarantine(self):
        p=self.write("1,2025-09-03,B,A,10,28,false\n2,2026-09-03,B,A,10,28,false\n")
        games,qa=read_games(p,"2026-10-20")
        self.assertEqual(len(games),1);self.assertEqual(qa["rejected"][0]["reason"],"wrong_season")
    def test_manifest(self):
        p=self.write("1,2026-09-03,B,A,10,28,false\n")
        n,qa=write_profiles(p,"2026-10-20",self.tmp.name)
        self.assertEqual(n,2)
        import json
        d=json.loads((Path(self.tmp.name)/"profile_manifest.json").read_text())
        self.assertEqual(d["betting_status"],"PASS_UNVALIDATED")
if __name__=="__main__":unittest.main()

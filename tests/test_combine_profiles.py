import csv,tempfile,unittest
from pathlib import Path
from scripts.combine_profiles import combine
class EnrichedProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
    def write(self,file,header,values):
        path=self.dir/file
        with path.open("w",newline="") as out:
            w=csv.DictWriter(out,fieldnames=header);w.writeheader();w.writerows(values)
        return path
    def inputs(self,advanced_asof="2026-10-20",other_team="A"):
        score=self.write("score.csv",["team","season","asof_exclusive","betting_status","wins","epa_offense","epa_defense"],[
            {"team":"A","season":2026,"asof_exclusive":"2026-10-20","betting_status":"PASS_UNVALIDATED","wins":4,"epa_offense":"","epa_defense":""}])
        adv=self.write("advanced.csv",["team","season","asof_exclusive","betting_status","games_covered","off_epa_per_play","source"],[
            {"team":other_team,"season":2026,"asof_exclusive":advanced_asof,"betting_status":"PASS_UNVALIDATED","games_covered":5,"off_epa_per_play":.15,"source":"SDV"}])
        return score,adv
    def test_join_and_gate(self):
        a,b=self.inputs()
        result=combine(a,b,self.dir,expected_teams=1)
        self.assertEqual(result["teams_with_advanced"],1)
        with (self.dir/"team_profiles_2026_enriched.csv").open() as f:rows=list(csv.DictReader(f))
        self.assertEqual(rows[0]["off_epa_per_play"],"0.15")
        self.assertEqual(rows[0]["advanced_source"],"SDV")
        self.assertEqual(rows[0]["betting_status"],"PASS_UNVALIDATED")
        self.assertNotIn("epa_offense",rows[0])
    def test_asof_mismatch_fails(self):
        a,b=self.inputs(advanced_asof="2026-10-19")
        with self.assertRaisesRegex(ValueError,"as-of"):combine(a,b,self.dir,1)
    def test_team_mismatch_fails(self):
        a,b=self.inputs(other_team="B")
        with self.assertRaisesRegex(ValueError,"registries"):combine(a,b,self.dir,1)
if __name__=="__main__":unittest.main()

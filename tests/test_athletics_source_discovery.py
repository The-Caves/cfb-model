import csv,tempfile,unittest
from pathlib import Path
from scripts.athletics_source_discovery import discover

class AthleticsDiscoveryTests(unittest.TestCase):
    def test_all_schools_preserved_and_unverified(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"teams.csv"
            with file.open("w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=["espn_display_name"])
                w.writeheader();w.writerows([{"espn_display_name":"Team A"},{"espn_display_name":"Team B"}])
            data={"sports":[{"leagues":[{"teams":[{"team":{"id":"1","displayName":"Team A",
                "links":[{"href":"https://espn.com/team/a"}]}}]}]}]}
            result=discover(file,data)
            self.assertEqual(result["expected"],2)
            self.assertEqual(result["matched"],1)
            self.assertEqual(result["unmatched"],["Team B"])
            self.assertTrue(all(not x["source_verified"] for x in result["teams"]))
            self.assertTrue(all(x["official_athletics_domain"] is None for x in result["teams"]))
if __name__=="__main__":unittest.main()

import csv,json,tempfile,unittest
from pathlib import Path
from scripts.official_school_source_registry import build

class OfficialSourceRegistryTests(unittest.TestCase):
    def test_no_false_verification_and_all_schools(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);aliases=root/"teams.csv";registry=root/"feeds.json"
            with aliases.open("w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=["espn_display_name"])
                w.writeheader();w.writerows([{"espn_display_name":"Team A"},{"espn_display_name":"Team B"}])
            registry.write_text(json.dumps({"status":"REVIEWED_OFFICIAL_RSS_REGISTRY_V1",
                "feeds":[{"team":"Team A","url":"https://sports.example.edu/rss",
                "reviewed":True,"publisher_host":"sports.example.edu"}]}))
            result=build(aliases,registry)
            self.assertEqual(result["expected"],2)
            self.assertEqual(result["official_rss_reviewed_count"],1)
            self.assertEqual(result["homepage_verified_count"],0)
            self.assertEqual(result["personnel_evidence_verified_count"],0)
            self.assertTrue(all(not row["personnel_evidence_verified"] for row in result["schools"]))
            self.assertEqual(result["schools"][1]["review_state"],"SOURCE_RESEARCH_REQUIRED")
if __name__=="__main__":unittest.main()

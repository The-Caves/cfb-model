import csv,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.official_school_source_registry import build
from scripts.official_source_connectivity import probe

class SiteCoverageTests(unittest.TestCase):
    def test_production_138_school_site_registry_is_complete(self):
        from scripts.official_school_source_registry import build
        result=build("data/archive/2026_team_aliases.csv",
            "config/official_qb_rss_registry.json",
            athletics="config/official_athletics_sites_2026.json")
        import json
        with open("config/official_athletics_sites_2026.json",encoding="utf-8") as handle:
            directory=json.load(handle)
        self.assertTrue(all("upstream_ncaa_id_unverified" not in row for row in directory["schools"]))
        self.assertEqual(result["expected"],138)
        self.assertEqual(result["homepage_candidate_count"],138)
        self.assertEqual(result["homepage_verified_count"],0)
        self.assertEqual(len({x["official_athletics_homepage"] for x in result["schools"]}),138)

    def test_site_candidates_do_not_imply_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            aliases=root/"teams.csv"; registry=root/"feeds.json"; directory=root/"sites.json"
            with aliases.open("w",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=["espn_display_name"])
                writer.writeheader()
                writer.writerows([{"espn_display_name":"Team A"},{"espn_display_name":"Team B"}])
            registry.write_text(json.dumps({"status":"REVIEWED_OFFICIAL_RSS_REGISTRY_V1","feeds":[]}))
            directory.write_text(json.dumps({
                "status":"EXTERNALLY_CROSS_REFERENCED_ATHLETICS_DIRECTORY_CANDIDATES_V1",
                "schools":[
                    {"team":"Team A","athletics_homepage":"https://a.example.edu/","source_host":"a.example.edu"},
                    {"team":"Team B","athletics_homepage":"https://b.example.edu/","source_host":"b.example.edu"}
                ]}))
            with patch("scripts.qb_official_news_watch.FEEDS",{}):
                result=build(aliases,registry,athletics=directory)
            self.assertEqual(result["homepage_candidate_count"],2)
            self.assertEqual(result["homepage_verified_count"],0)
            self.assertEqual(result["personnel_evidence_verified_count"],0)
            self.assertTrue(all(x["official_athletics_homepage"].startswith("https://") for x in result["schools"]))
            self.assertTrue(all(not x["homepage_verified"] for x in result["schools"]))

    def test_connectivity_is_not_personnel_evidence(self):
        result=probe({"Team A":"https://a.example.edu"},fetch=lambda url:(200,"text/html",b"<html>"))
        self.assertEqual(result["reachable"],1)
        self.assertEqual(result["feed_like"],0)
        self.assertFalse(result["sources"][0]["personnel_evidence_verified"])

if __name__=="__main__":
    unittest.main()

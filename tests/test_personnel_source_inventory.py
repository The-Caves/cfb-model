import csv,json,tempfile,unittest
from pathlib import Path
from scripts.personnel_source_inventory import inventory,run
from unittest.mock import patch

class InventoryTests(unittest.TestCase):
    def test_sources_never_imply_verified_players(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);aliases=base/"teams.csv";registry=base/"registry.json"
            with aliases.open("w",newline="") as stream:
                writer=csv.DictWriter(stream,fieldnames=["archived_team","espn_display_name"])
                writer.writeheader()
                writer.writerow({"archived_team":"Tulsa","espn_display_name":"Tulsa Golden Hurricane"})
                writer.writerow({"archived_team":"Other","espn_display_name":"Other Team"})
            registry.write_text(json.dumps({"status":"REVIEWED_OFFICIAL_RSS_REGISTRY_V1",
                "feeds":[{"team":"Tulsa Golden Hurricane","url":"https://tulsahurricane.com/rss?path=football",
                          "reviewed":True,"publisher_host":"tulsahurricane.com"}]}))
            with patch("scripts.personnel_source_inventory.load_feed_registry",return_value={"Tulsa Golden Hurricane":"https://tulsahurricane.com/rss?path=football"}):
                result=inventory(aliases,registry)
            self.assertEqual(result["inventory_team_count"],2)
            self.assertEqual(result["official_rss_configured"],1)
            self.assertFalse(result["expected_count_matches"])
            self.assertFalse(any(r["starting_qb_verified"] or r["injury_report_verified"] for r in result["teams"]))
    def test_expansion_queue_is_complete_and_does_not_invent_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);aliases=base/"teams.csv";registry=base/"registry.json"
            aliases.write_text("archived_team,espn_display_name\nA,Tulsa Golden Hurricane\nB,Other Team\n")
            registry.write_text(json.dumps({"status":"REVIEWED_OFFICIAL_RSS_REGISTRY_V1","feeds":[]}))
            with patch("scripts.personnel_source_inventory.load_feed_registry",
                       return_value={"Tulsa Golden Hurricane":"https://tulsahurricane.com/rss?path=football"}):
                result=run(aliases,base/"out.json",registry,base/"backlog.csv")
            with (base/"backlog.csv").open(newline="") as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["team"],"Other Team")
            self.assertEqual(rows[0]["official_rss_url"],"")
            self.assertEqual(result["official_rss_unconfigured"],1)
    def test_duplicate_canonical_team_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"teams.csv"
            file.write_text("archived_team,espn_display_name\\nA,Same\\nB,Same\\n")
            with self.assertRaises(ValueError):
                inventory(file)
if __name__=="__main__":unittest.main()

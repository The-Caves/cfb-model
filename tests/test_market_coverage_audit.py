import csv
import json
import tempfile
import unittest
from pathlib import Path
from scripts.market_coverage_audit import run,audit

RETRIEVED="2026-10-21T17:00:00Z"
KICK="2026-10-24T19:00:00Z"
GAME={"game_id":"401111000","home":"Ohio State Buckeyes",
      "away":"Penn State Nittany Lions","home_id":"194","away_id":"213",
      "kickoff_utc":KICK,"neutral":False,"completed":False}
def provider(home="Ohio State Buckeyes",away="Penn State Nittany Lions"):
    return [{"id":"p1","sport_key":"americanfootball_ncaaf","commence_time":KICK,
        "home_team":home,"away_team":away,
        "bookmakers":[{"key":"fanduel","last_update":"2026-10-21T16:50:00Z",
            "markets":[{"key":"spreads","outcomes":[
                {"name":home,"price":-110,"point":-4.5},
                {"name":away,"price":-110,"point":4.5}]},
                {"key":"h2h","outcomes":[
                {"name":home,"price":-200},{"name":away,"price":170}]}]}]}]
def registry(path):
    with path.open("w",newline="") as f:
        w=csv.writer(f)
        w.writerow(["archived_team","espn_display_name"])
        w.writerow(["Ohio State","Ohio State Buckeyes"])
        w.writerow(["Penn State","Penn State Nittany Lions"])
class CoverageAuditTests(unittest.TestCase):
    def test_matching_sample_reports_aggregate_counts_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"aliases.csv";registry(p)
            report=audit(provider(),{"asof_utc":"2026-10-21T16:00:00Z",
                                     "games":[GAME]},p,RETRIEVED)
            self.assertEqual(report["provider_event_coverage"]["matched"],1)
            self.assertEqual(report["source_quote_count"],4)
            self.assertEqual(len(report["market_event_counts"]),2)
            self.assertNotIn("american_odds",json.dumps(report))
            self.assertNotIn("line_points",json.dumps(report))
            self.assertEqual(report["betting_status"],"PASS_UNVALIDATED")
    def test_unknown_teams_not_misjoined(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"aliases.csv";registry(p)
            report=audit(provider("Ohio University Bobcats","Penn State Nittany Lions"),
                         {"asof_utc":"2026-10-21T16:00:00Z","games":[GAME]},
                         p,RETRIEVED)
            self.assertEqual(report["provider_event_coverage"]["matched"],0)
            self.assertEqual(report["provider_event_coverage"]["quarantined"],1)
    def test_retroactive_espn_context_does_not_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"aliases.csv";registry(p)
            historical={"timestamp":"2026-10-20T12:00:00Z","data":provider()}
            report=audit(historical,{"asof_utc":"2026-10-21T16:00:00Z","games":[GAME]},
                         p,"2026-10-21T17:00:00Z",historical=True)
            self.assertEqual(report["provider_event_coverage"]["matched"],0)
            self.assertIn("ESPN_SNAPSHOT_LATER_THAN_ODDS",
                          report["provider_event_coverage"]["reasons"])
    def test_persistent_report_no_sensitive_odds(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);a=base/"aliases.csv";registry(a)
            (base/"provider.json").write_text(json.dumps(provider()))
            (base/"espn.json").write_text(json.dumps({
                "asof_utc":"2026-10-21T16:00:00Z","games":[GAME]}))
            output=base/"out"/"summary.json"
            result=run(base/"provider.json",base/"espn.json",a,output,RETRIEVED)
            self.assertEqual(result["provider_event_coverage"]["matched"],1)
            self.assertTrue(output.is_file())
            self.assertNotIn("-110",output.read_text())
if __name__=="__main__":unittest.main()

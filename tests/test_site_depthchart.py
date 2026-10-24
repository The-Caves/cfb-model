"""Depth-chart ranks must be explicit, sourced, and never confirmed-QB1 evidence."""
import datetime as dt,unittest,json,tempfile
from pathlib import Path
from scripts.site_depthchart import (INDEX,SOURCE,IndexParser,TableParser,
    extract_chart,overlay,chart_for_teams,clean_name,normalized,candidate_name,source_updated,run)
UTC=dt.timezone.utc
NOW=dt.datetime(2026,10,24,14,tzinfo=UTC)
def board():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED","games":[{
      "game_id":"1","home_team":"Mississippi State Bulldogs","away_team":"Oklahoma Sooners",
      "kickoff_utc":"2026-10-24T19:30:00Z",
      "qb_home":{"player":"Parker Puckett","status":"RECENT_GAME_PASSER"},
      "qb_away":{"player":None,"status":"UNKNOWN"},
      "model_home_margin":4.5,"model_ats_side":"HOME"}]}
def chart(players=None):
    return {"source_url":"https://www.ourlads.com/ncaa-football-depth-charts/depth-chart.aspx?id=91211&s=mississippi-state",
       "source_type":SOURCE,"observed_at_utc":"2026-10-24T13:00:00Z",
       "players":players or ["Kamario Taylor","Parker Puckett","AJ Swann"]}
class DepthTests(unittest.TestCase):
    def test_explicit_qb_order_only(self):
        html='<html><table><tr><td>QB</td><td>1</td><td>Taylor, Kamario SO</td><td>15</td><td>Puckett, Parker RS FR</td><td>17</td><td>Swann, AJ RS SR/TR</td></tr></table></html>'
        self.assertEqual(extract_chart(html),["Kamario Taylor","Parker Puckett","AJ Swann"])
    def test_reject_missing_numbers_ambiguous_and_unrelated(self):
        self.assertEqual(extract_chart("<tr><td>QB</td><td>Kamario Taylor</td><td>Parker Puckett</td></tr>"),[])
        html="<tr><td>QB</td><td>1</td><td>John Smith SO</td></tr><tr><td>QB</td><td>2</td><td>Another Guy FR</td></tr>"
        self.assertEqual(extract_chart(html),[])
        self.assertEqual(extract_chart("<tr><td>RB</td><td>24</td><td>Bothwell, Fluff SO</td></tr>"),[])
    def test_unambiguous_school_name_aliases(self):
        self.assertEqual(candidate_name("Florida International"),"fiu")
        self.assertEqual(candidate_name("Central Florida"),"ucf")
        self.assertEqual(candidate_name("South Florida"),"usf")
        self.assertEqual(candidate_name("Miami (Ohio)"),"miami oh")
    def test_school_index_official_unique_routes(self):
        p=IndexParser()
        p.feed('<html><img alt="Mississippi State"><a href="/ncaa-football-depth-charts/depth-chart.aspx?id=91211&s=mississippi-state">Depth Chart</a>'
               '<img alt="Mississippi"><a href="/ncaa-football-depth-charts/depth-chart.aspx?id=92000&s=mississippi">Depth Chart</a></html>')
        self.assertIn("mississippi state",p.pages)
        self.assertEqual(p.pages["ole miss"],"https://www.ourlads.com/ncaa-football-depth-charts/depth-chart.aspx?id=92000&s=mississippi")
    def test_display_does_not_modify_forecast_or_promote(self):
        b=overlay(board(),{"Mississippi State Bulldogs":chart()},NOW)
        game=b["games"][0]
        self.assertEqual([p["label"] for p in game["qb_depth_home"]],["QB1","QB2","QB3"])
        self.assertEqual(game["qb_depth_home"][1]["player"],"Parker Puckett")
        self.assertFalse(game["qb_depth_home"][0]["confirmed_starter"])
        self.assertEqual(game["qb_home"]["status"],"RECENT_GAME_PASSER")
        self.assertEqual(game["model_home_margin"],4.5)
        self.assertFalse(b["qb_depth_display"]["changes_frozen_model_picks"])
    def test_future_capture_and_kickoff_quarantined(self):
        future=chart();future["observed_at_utc"]="2026-10-24T15:00:00Z"
        b=overlay(board(),{"Mississippi State Bulldogs":future},NOW)
        self.assertEqual(b["games"][0]["qb_depth_home"],[])
        late=chart();late["observed_at_utc"]="2026-10-24T20:00:00Z"
        self.assertEqual(overlay(board(),{"Mississippi State Bulldogs":late},NOW)["games"][0]["qb_depth_home"],[])
    def test_untrusted_url_or_source_not_promoted(self):
        bad=chart();bad["source_url"]="https://other-site.example/depth-chart"
        self.assertEqual(overlay(board(),{"Mississippi State Bulldogs":bad},NOW)["games"][0]["qb_depth_home"],[])
    def test_source_page_update_has_trustworthy_year_and_time(self):
        page='<div>Updated: 10/23/2026 7:04PM ET</div>'
        observed=dt.datetime(2026,10,24,14,tzinfo=UTC)
        self.assertIn("2026-10-23",source_updated(page,observed)["source_updated_et"])
        self.assertIsNone(source_updated(page,dt.datetime(2026,10,20,14,tzinfo=UTC)))
        self.assertIsNone(source_updated("<div>Updated: 10/23/2025 7:04PM ET</div>",observed))
    def test_daily_cache_keeps_charts_without_network_recrawl(self):
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/"board.json";cache=Path(folder)/"charts.json"
            src.write_text(json.dumps(board()))
            counter=[0]
            def reader(*_):
                counter[0]+=1
                return {"Mississippi State Bulldogs":chart()},{"charted_schools":1}
            first=run(src,now=NOW,collector=reader,cache=cache)
            self.assertEqual(first["games"][0]["qb_depth_home"][0]["label"],"QB1")
            self.assertFalse(first["qb_depth_display"]["cache_reused"])
            src.write_text(json.dumps(board()))
            second=run(src,now=NOW,collector=reader,cache=cache)
            self.assertEqual(counter[0],1)
            self.assertTrue(second["qb_depth_display"]["cache_reused"])
    def test_name_parsing(self):
        self.assertEqual(clean_name("Taylor, Kamario SO"),"Kamario Taylor")
        self.assertEqual(clean_name("Puckett, Parker RS FR"),"Parker Puckett")
        self.assertIsNone(clean_name("QB #1 ???"))

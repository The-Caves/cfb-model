import unittest
from scripts.ingest_espn import parse_event
from scripts.predict import fit_predict

class PipelineTests(unittest.TestCase):
    def test_parse_final(self):
        event={"id":"123","date":"2026-09-05T16:00Z","status":{"type":{"completed":True}},
          "competitions":[{"neutralSite":False,"competitors":[
            {"homeAway":"home","score":"24","team":{"displayName":"Home"}},
            {"homeAway":"away","score":"17","team":{"displayName":"Away"}}]}]}
        row=parse_event(event)
        self.assertEqual((row["home_score"],row["away_score"]),(24,17))
    def test_asof_blocks_future_results(self):
        rows=[{"date":"2026-09-01","home":"A","away":"B","home_score":"24","away_score":"14","neutral":"False"},
              {"date":"2026-10-21","home":"A","away":"B","home_score":"0","away_score":"70","neutral":"False"}]
        p=fit_predict(rows,"B","A","2026-10-20")
        self.assertEqual(p["training_games"],1)
        self.assertEqual(p["status"],"PASS_UNVALIDATED")
    def test_blowout_cap_symmetry(self):
        rows=[{"date":"2026-09-01","home":"A","away":"B","home_score":"70","away_score":"0","neutral":"False"},
              {"date":"2026-09-08","home":"B","away":"A","home_score":"0","away_score":"70","neutral":"False"}]
        p=fit_predict(rows,"B","A","2026-10-20",cap=28)
        self.assertGreater(p["home_margin"],0)
        self.assertLess(p["home_margin"],28)
    def test_incomplete_event_not_used(self):
        self.assertIsNone(parse_event({"competitions":[],"status":{"type":{"completed":False}}}))
if __name__=="__main__":unittest.main()

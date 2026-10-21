import unittest
from scripts.ingest_espn import parse_event
from scripts.predict import fit_predict
class Tests(unittest.TestCase):
    def test_completed(self):
        e={"id":"42","date":"2026-09-01T12:00Z","status":{"type":{"completed":True}},
           "competitions":[{"neutralSite":False,"competitors":[
             {"homeAway":"home","score":"21","team":{"displayName":"A"}},
             {"homeAway":"away","score":"14","team":{"displayName":"B"}}]}]}
        self.assertEqual(parse_event(e)["home_score"],21)
    def test_incomplete_excluded(self):
        self.assertIsNone(parse_event({"status":{"type":{"completed":False}},"competitions":[]}))
    def test_asof_exclusion(self):
        rows=[{"date":"2026-09-01","home":"A","away":"B","home_score":"24","away_score":"14","neutral":"False"},
              {"date":"2026-10-21","home":"A","away":"B","home_score":"0","away_score":"70","neutral":"False"}]
        result=fit_predict(rows,"B","A","2026-10-20")
        self.assertEqual(result["training_games"],1)
        self.assertEqual(result["status"],"PASS_UNVALIDATED")
if __name__=="__main__":unittest.main()

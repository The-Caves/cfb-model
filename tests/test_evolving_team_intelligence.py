import copy
import unittest
from scripts.evolving_team_intelligence import build

DECISION="2026-10-30T18:00:00Z"
KICK="2026-10-31T19:00:00Z"

def observations():
    out=[]
    for i in range(9):
        for team,other,side in (("A","B",1),("B","A",-1)):
            out.append({
                "game_id":str(i),"team":team,"opponent":other,
                "date":"2026-09-"+str(i+1).zfill(2),
                "kickoff_utc":"2026-09-"+str(i+1).zfill(2)+"T18:00:00Z",
                "outcome_known_at_utc":"2026-09-"+str(i+1).zfill(2)+"T23:00:00Z",
                "source_observed_at_utc":"2026-10-20T12:00:00Z",
                "source_url":"https://example.edu/official", 
                "source_status":"CAPTURED_COMPLETED_GAME_RESEARCH_ONLY",
                "pass_off":.1+side*.03+i*.005,"run_off":.04+side*.01,
                "pass_def_allowed":.05-side*.02,"run_def_allowed":-.01,
                "turnover_margin":side*(i%2)
            })
    return out

def slate():
    return [{"game_id":"future","home":"A","away":"B","date":"2026-10-31","kickoff_utc":KICK}]

class EvolutionTests(unittest.TestCase):
    def test_prior_date_opponent_adjustment_then_trajectory(self):
        result=build(observations(),slate(),DECISION)
        p=result["profiles"]["A"]
        self.assertEqual(p["prior_games"],9)
        self.assertGreater(p["adjusted_games"]["pass_off_adj"],0)
        self.assertEqual(p["trajectory"]["pass_off_adj"]["status"],"OBSERVED_TRAJECTORY_NOT_CAUSAL")
        self.assertFalse(p["structural_change_verified"])
        self.assertIsNone(result["upcoming_games"][0]["model_impact_points"])

    def test_uneven_two_sided_source_rejected(self):
        rows=observations()[:-1]
        with self.assertRaises(ValueError):build(rows,slate(),DECISION)

    def test_future_capture_is_not_backfilled(self):
        rows=observations()
        rows[0]["source_observed_at_utc"]="2026-11-01T00:00:00Z"
        with self.assertRaises(ValueError):build(rows,slate(),DECISION)

    def test_same_football_date_ignored(self):
        rows=observations()
        for r in rows[-2:]:r["date"]="2026-10-31"
        result=build(rows,slate(),DECISION)
        self.assertEqual(result["profiles"]["A"]["prior_games"],8)

    def test_outlier_turnover_does_not_claim_structural_shift(self):
        rows=observations()
        rows[0]["turnover_margin"]=3
        rows[1]["turnover_margin"]=-3
        result=build(rows,slate(),DECISION)
        self.assertEqual(result["structural_changes_claimed"],0)

if __name__=="__main__":
    unittest.main()

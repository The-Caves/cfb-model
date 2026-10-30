import copy
import unittest
from scripts.prospective_model_competition import digest,evaluate

KICK="2026-10-24T20:00:00Z"
ISSUED="2026-10-22T20:00:00Z"
KNOWN="2026-10-25T01:00:00Z"
NOW="2026-10-30T12:00:00Z"

def forecast(version,margin,total=41):
    row={"game_id":"99","home":"A","away":"B","kickoff_utc":KICK,
        "issued_at_utc":ISSUED,"model_version":version,
        "predicted_margin":margin,"predicted_total":total,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    row["record_sha256"]=digest(row)
    return row

def final():
    return {"game_id":"99","home":"A","away":"B","kickoff_utc":KICK,
        "home_score":30,"away_score":20,"outcome_known_at_utc":KNOWN,
        "source_url":"https://example.edu/official-boxscore"}

class ProspectiveCompetitionTests(unittest.TestCase):
    def test_same_game_v03_and_challenger(self):
        r=evaluate([forecast("V03",8),forecast("CHALLENGER",10)],[final()],NOW,minimum_pairs=2)
        self.assertEqual(r["versions"]["CHALLENGER"]["paired_games"],1)
        self.assertEqual(r["versions"]["CHALLENGER"]["paired_margin_mae_delta"],-2)
        self.assertFalse(r["model_promoted"])
        self.assertFalse(r["versions"]["CHALLENGER"]["promotion_eligible"])

    def test_challenger_only_never_claims_improvement(self):
        r=evaluate([forecast("V03",8),forecast("CHALLENGER",10)],[],NOW,minimum_pairs=2)
        self.assertIsNone(r["versions"]["CHALLENGER"]["paired_margin_mae_delta"])

    def test_edited_forecast_and_postkickoff_forecast_rejected(self):
        x=forecast("V03",8);x["predicted_margin"]=100
        with self.assertRaises(ValueError):evaluate([x], [final()], NOW)
        x=forecast("V03",8);x["issued_at_utc"]=KNOWN;x["record_sha256"]=digest(x)
        with self.assertRaises(ValueError):evaluate([x], [final()], NOW)

    def test_mismatched_matchup_and_future_final_rejected(self):
        a=forecast("V03",8);b=forecast("CHALLENGER",10)
        b["away"]="C";b["record_sha256"]=digest(b)
        with self.assertRaises(ValueError):evaluate([a,b],[final()],NOW,minimum_pairs=2)
        f=final();f["outcome_known_at_utc"]="2026-11-01T00:00:00Z"
        with self.assertRaises(ValueError):evaluate([a],[f],NOW)

if __name__=="__main__":
    unittest.main()

import unittest
from scripts.turnover_boxscore import parse,collect,STATUS
G={"game_id":"401000123","date":"2026-10-20","home":"A","away":"B",
   "home_score":"21","away_score":"14"}
def payload(home=2,away=0):
    return {"header":{"competitions":[{"status":{"type":{"completed":True}},
        "competitors":[{"homeAway":"home","team":{"displayName":"A"},"score":21},
                       {"homeAway":"away","team":{"displayName":"B"},"score":14}]}]},
        "boxscore":{"teams":[{"team":{"displayName":"A"},"statistics":[
             {"name":"turnovers","displayValue":str(home)}]},
             {"team":{"displayName":"B"},"statistics":[
             {"name":"turnovers","displayValue":str(away)}]}]}}
class TurnoverTests(unittest.TestCase):
    def test_two_sided_espn_game_verified(self):
        rows=parse(G,payload(), "2026-10-21T12:00:00Z")
        a=next(r for r in rows if r["team"]=="A")
        self.assertEqual(a["turnovers_committed"],2)
        self.assertEqual(a["takeaways_observed"],0)
        self.assertFalse(a["historical_pregame_publication_verified"])
    def test_missing_not_zero_and_score_conflict_rejected(self):
        missing=payload();missing["boxscore"]["teams"][0]["statistics"]=[]
        with self.assertRaisesRegex(ValueError,"missing"):
            parse(G,missing,"2026-10-21T12:00:00Z")
        wrong=payload();wrong["header"]["competitions"][0]["competitors"][0]["score"]=100
        with self.assertRaisesRegex(ValueError,"final"):
            parse(G,wrong,"2026-10-21T12:00:00Z")
    def test_missing_game_withheld_not_leaked_into_zero(self):
        x=collect([G],"2026-10-21T12:00:00Z",lambda _:{"no":"data"})
        self.assertEqual(x["fully_verified_games"],0)
        self.assertEqual(x["rows"],[])
        self.assertEqual(x["unknown_games"],1)
    def test_wrong_opponent_rejected(self):
        bad=payload();bad["boxscore"]["teams"][1]["team"]["displayName"]="C"
        with self.assertRaisesRegex(ValueError,"identity"):
            parse(G,bad,"2026-10-21T12:00:00Z")
if __name__=="__main__":unittest.main()

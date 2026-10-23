import unittest
from scripts.free_market_capture import normalize
from scripts.free_market_compare import compare,grade

def event(home_favorite=True):
    return {"events":[{"id":"42","date":"2026-10-25T20:00:00Z","competitions":[{
        "competitors":[{"homeAway":"home","team":{"displayName":"Home"}},
                       {"homeAway":"away","team":{"displayName":"Away"}}],
        "odds":[{"spread":4.5,"overUnder":50.5,"provider":{"name":"Example"},
                 "homeTeamOdds":{"favorite":home_favorite},
                 "awayTeamOdds":{"favorite":not home_favorite}}]}]}]}

def forecast():
    return {"record":{"games":[{"game_id":"42","home":"Home","away":"Away",
        "kickoff_utc":"2026-10-25T20:00:00Z",
        "forecast_observed_utc":"2026-10-24T12:00:00Z",
        "projection":{"predicted_home_margin":7.0,"predicted_total_points":54.0}}]}}

class MarketCompareTests(unittest.TestCase):
    def test_home_favorite_spread_and_grading(self):
        q=normalize(event(),"2026-10-24T11:00:00Z")
        self.assertEqual(q["quotes"][0]["market_home_spread"],-4.5)
        b=compare(forecast(),[q]);r=b["rows"][0]
        self.assertEqual((r["ats_selection"],r["total_selection"]),("HOME","OVER"))
        result=grade(b,[{"game_id":"42","home":"Home","away":"Away",
            "kickoff_utc":"2026-10-25T20:00:00Z","home_score":31,"away_score":24}],
            "2026-10-26T00:00:00Z")
        self.assertEqual(result["rows"][0]["ats"],"WIN")
        self.assertEqual(result["rows"][0]["total"],"WIN")
    def test_away_favorite(self):
        q=normalize(event(False),"2026-10-24T11:00:00Z")
        self.assertEqual(q["quotes"][0]["market_home_spread"],4.5)
    def test_future_market_rejected(self):
        q=normalize(event(),"2026-10-24T13:00:00Z")
        self.assertEqual(compare(forecast(),[q])["rows"],[])
    def test_ambiguous_spread_passes(self):
        e=event();del e["events"][0]["competitions"][0]["odds"][0]["awayTeamOdds"]
        q=normalize(e,"2026-10-24T11:00:00Z")
        b=compare(forecast(),[q])
        self.assertEqual(b["rows"][0]["ats_selection"],"PASS")
        self.assertEqual(b["rows"][0]["total_selection"],"OVER")
    def test_final_identity_mismatch(self):
        q=normalize(event(),"2026-10-24T11:00:00Z")
        b=compare(forecast(),[q])
        self.assertEqual(grade(b,[{"game_id":"42","home":"Wrong","away":"Away",
            "kickoff_utc":"2026-10-25T20:00:00Z","home_score":31,"away_score":24}],
            "2026-10-26T00:00:00Z")["rows"],[])

if __name__=="__main__":unittest.main()

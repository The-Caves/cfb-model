import copy,unittest
from scripts.site_team_branding import capture,logo_url,parse_brand,STATUS
BASE={"schema_version":2,"betting_status":"PASS_UNVALIDATED","games":[
    {"game_id":"123","kickoff_utc":"2026-10-31T19:00:00Z",
     "home_team":"North Texas Mean Green","away_team":"Florida Atlantic Owls",
     "model_home_margin":7.5,"model_total":55.}]}
def payload():
    return {"events":[{"id":"123","date":"2026-10-31T19:00:00Z","competitions":[
        {"competitors":[{"homeAway":"home","team":{"displayName":"North Texas Mean Green",
            "abbreviation":"UNT","color":"008C76",
            "logo":"https://a.espncdn.com/i/teamlogos/ncaa/500/249.png"}},
          {"homeAway":"away","team":{"displayName":"Florida Atlantic Owls",
            "abbreviation":"FAU","color":"003366","logo":"https://a.espncdn.com/i/teamlogos/ncaa/500/2226.png"}}]}]}]}
class BrandTests(unittest.TestCase):
    def test_exact_game_identity_and_forecast_preserved(self):
        result=capture(copy.deepcopy(BASE),payload())
        self.assertEqual(result["team_brand_display"]["status"],STATUS)
        self.assertEqual(result["team_brand_display"]["matched_games"],1)
        self.assertEqual(result["games"][0]["team_brand_home"]["color"],"#008c76")
        self.assertEqual(result["games"][0]["model_total"],55.)
        self.assertEqual(result["games"][0]["model_home_margin"],7.5)
    def test_wrong_game_name_or_time_rejected(self):
        d=payload();d["events"][0]["competitions"][0]["competitors"][0]["team"]["displayName"]="Not That Team"
        self.assertIsNone(capture(copy.deepcopy(BASE),d)["games"][0]["team_brand_home"])
        d=payload();d["events"][0]["date"]="2026-11-01T19:00:00Z"
        self.assertIsNone(capture(copy.deepcopy(BASE),d)["games"][0]["team_brand_home"])
    def test_no_untrusted_img_or_fake_team_color(self):
        self.assertIsNone(logo_url({"logo":"https://evil.example/i/teamlogos/ncaa/500/2226.png"}))
        self.assertIsNone(logo_url({"logo":"https://a.espncdn.com/i/teamlogos/ncaa/500/2.svg"}))
        self.assertIsNone(parse_brand({"color":"nothex","logo":"https://bad.example/logo.png"})["color"])
        self.assertIsNone(parse_brand({"color":"nothex","logo":"https://bad.example/logo.png"})["logo_url"])
    def test_missing_source_is_explicit_neutral_fallback(self):
        r=capture(copy.deepcopy(BASE),{"events":[]})
        self.assertIsNone(r["games"][0]["team_brand_away"])
        self.assertFalse(r["team_brand_display"]["changes_frozen_forecast"])
if __name__=="__main__":unittest.main()

import csv
import tempfile
import unittest
from pathlib import Path
from scripts.market_event_crosswalk import load_registry,load_market_registry,crosswalk

AT="2026-10-21T16:00:00Z"
OBS="2026-10-21T17:00:00Z"
KICK="2026-10-24T19:00:00Z"
GAME={"game_id":"401111000","home":"Ohio State Buckeyes",
      "away":"Penn State Nittany Lions","home_id":"194","away_id":"213",
      "kickoff_utc":KICK,"neutral":False,"completed":False}
ALIASES={"ohiostatebuckeyes":"Ohio State Buckeyes","ohiostate":"Ohio State Buckeyes",
         "pennstatenittanylions":"Penn State Nittany Lions",
         "pennstate":"Penn State Nittany Lions"}
def quote(pid="p1",home="Ohio State Buckeyes",away="Penn State Nittany Lions",kickoff=KICK,observed=OBS):
    return {"provider_event_id":pid,"home_team_source":home,"away_team_source":away,
            "kickoff_utc":kickoff,"observed_at_utc":observed,"market":"SPREAD",
            "selection":"HOME","bookmaker":"fanduel","line_points":-4.5,
            "american_odds":-110,"espn_game_id":None}
def bundle(quotes):
    return {"quotes":quotes,"rejected":[],"betting_status":"PASS_UNVALIDATED"}
def slate(games=None,asof=AT):
    return {"asof_utc":asof,"games":[GAME] if games is None else games}
class CrosswalkTests(unittest.TestCase):
    def join(self,quotes,games=None,asof=AT):
        return crosswalk(bundle(quotes),slate(games,asof),ALIASES)
    def test_exact_home_away_and_espn_ids(self):
        r=self.join([quote()])
        row=r["quotes"][0]
        self.assertEqual(row["espn_game_id"],"401111000")
        self.assertEqual(row["home_espn_team_id"],"194")
        self.assertEqual(row["away_espn_team_id"],"213")
        self.assertEqual(row["match_status"],"MATCHED_ASOF")
        self.assertEqual(r["coverage"]["matched"],1)
        self.assertFalse(r["safe_for_betting"])
    def test_curated_alias_not_fuzzy_matching(self):
        self.assertEqual(self.join([quote(home="Ohio State",away="Penn State")])["coverage"]["matched"],1)
        self.assertEqual(self.join([quote(home="OSU")])["coverage"]["quarantined"],1)
    def test_reversed_sides_not_silently_inverted(self):
        q=self.join([quote(home=GAME["away"],away=GAME["home"])])["quotes"][0]
        self.assertEqual(q["match_reject_reason"],"HOME_AWAY_REVERSED")
        self.assertIsNone(q["espn_game_id"])
    def test_date_and_kickoff_matched(self):
        self.assertEqual(self.join([quote(kickoff="2026-10-24T19:10:00Z")])["coverage"]["matched"],1)
        self.assertEqual(self.join([quote(kickoff="2026-10-25T19:00:00Z")])["coverage"]["matched"],0)
    def test_leakage_prevention(self):
        row=self.join([quote(observed="2026-10-20T17:00:00Z")])["quotes"][0]
        self.assertEqual(row["match_reject_reason"],"ESPN_SNAPSHOT_LATER_THAN_ODDS")
        self.assertIsNone(row["espn_game_id"])
    def test_ambiguous_duplicate_game_is_quarantined(self):
        other={**GAME,"game_id":"401111001"}
        row=self.join([quote()],games=[GAME,other])["quotes"][0]
        self.assertEqual(row["match_reject_reason"],"AMBIGUOUS_ESPN_MATCH")
    def test_multiple_provider_events_one_game_no_double_join(self):
        result=self.join([quote(pid="one"),quote(pid="two")])
        self.assertEqual(result["coverage"]["matched"],1)
        self.assertEqual(result["coverage"]["quarantined"],1)
    def test_invalid_identifiers(self):
        no_id={**GAME,"away_id":None}
        self.assertEqual(self.join([quote()],games=[no_id])["coverage"]["matched"],0)
    def test_registry_collision_quarantined(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"alias.csv"
            with p.open("w",newline="") as handle:
                w=csv.writer(handle)
                w.writerow(["archived_team","espn_display_name"])
                w.writerow(["OSU","Ohio State Buckeyes"])
                w.writerow(["OSU","Oklahoma State Cowboys"])
                w.writerow(["OSU","Oregon State Beavers"])
            mapping,conflicts=load_registry(p)
            self.assertIn("osu",conflicts)
            self.assertNotIn("osu",mapping)
    def test_registry_real_2026_fbs(self):
        path=Path("data/archive/2026_team_aliases.csv")
        aliases,conflicts=load_registry(path)
        self.assertEqual(aliases["ohiostate"],"Ohio State Buckeyes")
        self.assertEqual(aliases["pennstate"],"Penn State Nittany Lions")
        self.assertNotIn("ohiostate",conflicts)
    def test_real_source_aliases_from_public_october_sample(self):
        aliases,conflicts=load_market_registry(
            Path("data/archive/2026_team_aliases.csv"),
            Path("data/archive/2026_market_provider_aliases.csv"))
        for source,target in [
            ("Sam Houston State Bearkats","Sam Houston Bearkats"),
            ("Appalachian State Mountaineers","App State Mountaineers"),
            ("UMass Minutemen","Massachusetts Minutemen")
        ]:
            self.assertEqual(aliases[source.lower().replace(" ","")],target)
        self.assertNotIn("umassminutemen",conflicts)
        self.assertNotIn("unknownuniversity",aliases)

    def test_bad_or_collision_market_aliases_are_quarantined(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"sportsbook.csv"
            p.write_text("provider_team_name,espn_display_name\nOhio State Buckeyes,Penn State Nittany Lions\n")
            with self.assertRaises(ValueError):
                load_market_registry("data/archive/2026_team_aliases.csv",p)
            p.write_text("provider_team_name,espn_display_name\nFake Name,Imaginary School\n")
            with self.assertRaises(ValueError):
                load_market_registry("data/archive/2026_team_aliases.csv",p)

    def test_no_espn_asof_rejected(self):
        with self.assertRaises((KeyError,ValueError)):
            crosswalk(bundle([quote()]),{"games":[GAME]},ALIASES)
    def test_two_sided_market_rows_map_same_event(self):
        other={**quote(),"selection":"AWAY","line_points":4.5}
        result=self.join([quote(),other])
        self.assertEqual(len(result["quotes"]),2)
        self.assertEqual(result["coverage"]["matched"],1)
        self.assertEqual({x["espn_game_id"] for x in result["quotes"]},{"401111000"})
if __name__=="__main__":
    unittest.main()

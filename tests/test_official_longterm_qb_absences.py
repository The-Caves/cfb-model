"""Original university source verified after review, never backdated into October."""
import copy
import json
from pathlib import Path
import unittest
from scripts.official_longterm_qb_absences import apply,STATUS,AUDIT
from scripts.v04_market_challenger import apply as research
from scripts.v04_direct_scores import MODEL as V04_MODEL, STATUS as V04_STATUS

REGISTRY=json.loads(Path("data/context/official_longterm_qb_absences_2026.json").read_text())
KICK="2026-11-07T20:00:00Z"
SCORE={"model":V04_MODEL,"status":V04_STATUS,
       "home_points":30.,"away_points":20.,"home_margin":10.,
       "total_points":50.,"no_market_lines_in_training":True,
       "direct_scoring_fit_uses_v03_total":False,"model_promoted":False}


def board():
    return {"schema_version":2,"betting_status":"PASS_UNVALIDATED",
            "games":[{"game_id":"500","home_team":"Mississippi State Bulldogs",
              "away_team":"Florida State Seminoles","kickoff_utc":KICK,
              "qb_home":{"status":"UNKNOWN","player":None},
              "qb_away":{"status":"UNKNOWN","player":None},
              "qb_starters_verified":0,
              "home_bias_quarantined":True,
              "model_home_margin":15.,"model_total":51.,
              "v04_direct_scores":copy.deepcopy(SCORE),
              "market_home_spread":3.,"market_total":35.,
              "market_provider":"ESPN","market_observed_utc":"2026-11-04T01:57:00Z"}]}


class OfficialOutageTests(unittest.TestCase):
    def test_university_absence_evidence_is_recorded_without_points(self):
        self.assertEqual(REGISTRY["status"],STATUS)
        base=board()
        old=copy.deepcopy(base["games"][0]["v04_direct_scores"])
        result=apply(base,REGISTRY,"2026-11-04T02:00:00Z")
        row=result["games"][0]
        self.assertEqual(row["v04_direct_scores"],old)
        self.assertEqual(row["official_longterm_qb_absence_home"]["player"],"Kamario Taylor")
        self.assertEqual(row["official_longterm_qb_absence_home"]["designation"],"OUT_REMAINDER_2026")
        self.assertTrue(row["official_longterm_qb_absence_home"]["source_url"].startswith("https://hailstate.com/news/"))
        self.assertFalse(row["official_longterm_qb_absence_home"]["verified_replacement_starter"])
        self.assertIsNone(row["official_longterm_qb_absence_away"])
        self.assertEqual(result["official_longterm_qb_absence_audit"]["status"],AUDIT)
        self.assertEqual(result["official_longterm_qb_absence_audit"]["future_team_sides_with_verified_longterm_absence"],1)

    def test_october_pregame_and_earlier_november_archives_not_backfilled(self):
        before=apply(board(),REGISTRY,"2026-11-03T23:59:59Z")
        self.assertIsNone(before["games"][0]["official_longterm_qb_absence_home"])
        self.assertEqual(before["official_longterm_qb_absence_audit"]["future_team_sides_with_verified_longterm_absence"],0)
        past=board()
        past["games"][0]["kickoff_utc"]="2026-10-31T23:30:00Z"
        result=apply(past,REGISTRY,"2026-11-04T02:00:00Z")
        self.assertIsNone(result["games"][0]["official_longterm_qb_absence_home"])

    def test_two_official_miami_qb_outages_are_retained_and_never_change_scores(self):
        b=board()
        b["games"][0]["home_team"]="Miami (OH) RedHawks"
        b["games"][0]["away_team"]="Buffalo Bulls"
        b["games"][0]["kickoff_utc"]="2026-11-07T20:00:00Z"
        original=copy.deepcopy(b["games"][0]["v04_direct_scores"])
        out=apply(b,REGISTRY,"2026-11-04T02:00:00Z")
        game=out["games"][0]
        self.assertEqual(
            {r["player"] for r in game["official_longterm_qb_absences_home"]},
            {"David McComb","Thomas Gotkowski"})
        self.assertEqual(game["v04_direct_scores"],original)
        self.assertEqual(out["official_longterm_qb_absence_audit"]["active_future_outage_player_records"],2)
        self.assertEqual(out["official_longterm_qb_absence_audit"]["future_team_sides_with_verified_longterm_absence"],1)
        self.assertFalse(game["official_longterm_qb_absence_home"]["verified_replacement_starter"])
        older=board()
        older["games"][0]["home_team"]="Miami (OH) RedHawks"
        older["games"][0]["kickoff_utc"]="2026-11-03T23:30:00Z"
        older=apply(older,REGISTRY,"2026-11-03T23:20:00Z")
        self.assertEqual(older["games"][0]["official_longterm_qb_absences_home"],[])

    def test_current_verified_replacement_is_distinct_from_outage(self):
        b=board()
        b["games"][0]["qb_home"]={"status":"CONFIRMED_OFFICIAL","player":"Other QB"}
        got=apply(b,REGISTRY,"2026-11-04T02:00:00Z")
        self.assertTrue(got["games"][0]["official_longterm_qb_absence_home"]["verified_replacement_starter"])
        self.assertFalse(got["games"][0]["official_longterm_qb_absence_home"]["replacement_value_calibrated"])

    def test_web_source_host_clock_and_review_bypass_are_rejected(self):
        def corrupt(key,value):
            payload=copy.deepcopy(REGISTRY)
            payload["records"][0][key]=value
            return payload
        with self.assertRaisesRegex(ValueError,"not trusted"):
            apply(board(),corrupt("source_url","https://other.example/news/2026/bogus"),"2026-11-04T02:00:00Z")
        with self.assertRaisesRegex(ValueError,"Unreviewed"):
            apply(board(),corrupt("human_reviewed",False),"2026-11-04T02:00:00Z")
        with self.assertRaisesRegex(ValueError,"predates source"):
            apply(board(),corrupt("first_eligible_at_utc","2026-10-26T00:00:00Z"),"2026-11-04T02:00:00Z")
        conflicting=copy.deepcopy(REGISTRY)
        conflicting["records"].append(copy.deepcopy(conflicting["records"][0]))
        with self.assertRaisesRegex(ValueError,"conflicting"):
            apply(board(),conflicting,"2026-11-04T02:00:00Z")

    def test_official_outage_forces_v04_research_pass_not_point_downgrade(self):
        b=apply(board(),REGISTRY,"2026-11-04T02:00:00Z")
        before=copy.deepcopy(b["games"][0]["v04_direct_scores"])
        research(b,"2026-11-04T02:00:00Z")
        r=b["games"][0]["v04_market_research"]
        self.assertEqual((r["ats_side"],r["ou_side"]),("PASS","PASS"))
        self.assertEqual(r["ats_reason"],"OFFICIAL_QB_SEASON_OUT_REPLACEMENT_NOT_ESTIMATED")
        self.assertEqual(r["ou_reason"],"OFFICIAL_QB_SEASON_OUT_REPLACEMENT_NOT_ESTIMATED")
        self.assertTrue(r["qb_confirmed_season_out_unverified_replacement"])
        self.assertEqual(b["v04_market_research_audit"]["official_qb_out_no_verified_replacement_passes"],1)
        self.assertEqual(b["games"][0]["v04_direct_scores"],before)
        b2=board()
        research(b2,"2026-11-04T02:00:00Z")
        self.assertEqual((b2["games"][0]["v04_market_research"]["ats_side"],
                          b2["games"][0]["v04_market_research"]["ou_side"]),("HOME","OVER"))


if __name__=="__main__":
    unittest.main()

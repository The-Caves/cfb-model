"""Long-term university QB OUT filters actual expected QB choices, never grades."""
import copy
import json
from pathlib import Path
import unittest
from scripts.qb_longterm_expected import apply, STATUS
from scripts.qb_expected_starters import STATUS as EXPECTED
from scripts.qb_scenario_exposure import mixture

REGISTRY=json.loads(Path("data/context/official_longterm_qb_absences_2026.json").read_text())
NOW="2026-11-05T15:00:00Z"
KICK="2026-11-07T20:00:00Z"


def expected():
    return {
        "status":EXPECTED,"season":2026,"observed_at_utc":"2026-11-05T14:59:00Z",
        "model_promoted":False,"betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
        "team_slots":2,
        "summary":{"projected_or_confirmed_starters":2,"confirmed_starters":0,
                   "charted_teams":2,"unknown_starters":0,"conflicting_chart_vs_last_game":0},
        "games":[
            {"game_id":"109","team":"Mississippi State Bulldogs",
             "opponent":"Other School","kickoff_utc":KICK,
             "observed_at_utc":"2026-11-05T14:59:00Z",
             "starter":"Kamario Taylor","starter_status":"PROJECTED_DEPTH_CHART_ONLY",
             "confidence":"LOW_UNCONFIRMED","reason":"CHART_QB1_NO_RECENT_USAGE_CONFIRMATION",
             "depth_rank":1,"depth_label":"QB1","is_confirmed_starter":False,
             "availability_by_player":{},
             "scenarios":[{"player":"Kamario Taylor","depth_rank":1},
                          {"player":"AJ Swann","depth_rank":2}],
             "betting_status":"PASS_UNVALIDATED"},
            {"game_id":"109","team":"Other School",
             "opponent":"Mississippi State Bulldogs","kickoff_utc":KICK,
             "observed_at_utc":"2026-11-05T14:59:00Z",
             "starter":"Other QB","starter_status":"PROJECTED_DEPTH_CHART_ONLY",
             "confidence":"LOW_UNCONFIRMED","reason":"CHART",
             "depth_rank":1,"depth_label":"QB1","is_confirmed_starter":False,
             "availability_by_player":{},
             "scenarios":[{"player":"Other QB","depth_rank":1}],
             "betting_status":"PASS_UNVALIDATED"}]}


class LongTermStarterTests(unittest.TestCase):
    def test_official_out_qb_is_not_current_starter_or_playable_scenario(self):
        initial=expected();unchanged=copy.deepcopy(initial)
        result=apply(initial,REGISTRY,NOW)
        self.assertEqual(initial,unchanged)
        first=result["games"][0]
        self.assertIsNone(first["starter"])
        self.assertEqual(first["starter_status"],
                         "UNKNOWN_OFFICIAL_SEASON_OUT_NO_VERIFIED_REPLACEMENT")
        self.assertEqual([x["player"] for x in first["scenarios"]],["AJ Swann"])
        self.assertEqual(first["official_longterm_out_qb"]["player"],"Kamario Taylor")
        self.assertTrue(first["official_longterm_out_qb"]["does_not_confirm_replacement"])
        self.assertEqual(first["observed_at_utc"],NOW.replace("Z","+00:00"))
        self.assertEqual(result["summary"]["unknown_starters"],1)
        self.assertEqual(result["qb_longterm_out_audit"]["projected_out_qbs_changed_to_unknown"],1)
        self.assertEqual(result["qb_longterm_out_audit"]["unavailable_qb_scenarios_removed"],1)
        self.assertFalse(result["qb_longterm_out_audit"]["replacement_starter_inferred"])
        self.assertEqual(result["games"][1]["starter"],"Other QB")

    def test_filtered_out_qb_pass_exposure_is_unknown_not_moved_to_qb2(self):
        row=apply(expected(),REGISTRY,NOW)["games"][0]
        exposure=mixture([],"Mississippi State Bulldogs",row,"2026-11-07",NOW)
        self.assertEqual(exposure["weights"],{"AJ Swann":0.})
        self.assertEqual(exposure["unknown_weight"],1.)
        self.assertEqual(exposure["status"],"PASS_NO_SOURCED_PRIOR_QB_EXPOSURE")

    def test_not_backdated_into_older_capture(self):
        prior=expected()
        prior["observed_at_utc"]="2026-11-03T17:59:00Z"
        for row in prior["games"]:
            row["observed_at_utc"]="2026-11-03T17:59:00Z"
        before=apply(prior,REGISTRY,"2026-11-03T18:00:00Z")
        self.assertEqual(before["games"][0]["starter"],"Kamario Taylor")
        self.assertNotIn("official_longterm_out_qb",before["games"][0])
        self.assertEqual(before["qb_longterm_out_audit"]["official_future_team_slots_annotated"],0)

    def test_game_specific_replacement_starter_stays_confirmed(self):
        x=expected()
        x["games"][0]["starter"]="AJ Swann"
        x["games"][0]["starter_status"]="CONFIRMED_REVIEWED_PREKICKOFF"
        x["games"][0]["is_confirmed_starter"]=True
        x["summary"]["confirmed_starters"]=1
        r=apply(x,REGISTRY,NOW)
        self.assertEqual(r["games"][0]["starter"],"AJ Swann")
        self.assertTrue(r["games"][0]["is_confirmed_starter"])
        self.assertEqual([q["player"] for q in r["games"][0]["scenarios"]],["AJ Swann"])

    def test_conflicting_explicit_confirmed_out_player_fails(self):
        x=expected()
        x["games"][0]["starter_status"]="CONFIRMED_REVIEWED_PREKICKOFF"
        x["games"][0]["is_confirmed_starter"]=True
        with self.assertRaisesRegex(ValueError,"contradicts"):
            apply(x,REGISTRY,NOW)

    def test_fake_publisher_and_future_observation_fail_closed(self):
        bad=copy.deepcopy(REGISTRY)
        bad["records"][0]["source_url"]="https://invalid.example/news/2026/football"
        with self.assertRaisesRegex(ValueError,"publisher mismatch"):
            apply(expected(),bad,NOW)
        with self.assertRaisesRegex(ValueError,"future"):
            apply(expected(),REGISTRY,"2026-11-05T14:00:00Z")


if __name__=="__main__":
    unittest.main()

"""Canonical CFB pregame player evidence joins: no guessed starters or health."""
import copy
import json
import unittest
from pathlib import Path

from scripts.personnel_intake_board import build, STATUS
from scripts.qb_expected_starters import STATUS as QB_STATUS

REGISTRY=json.loads(Path("data/context/official_longterm_qb_absences_2026.json").read_text())
KICK="2026-11-07T20:00:00Z"
AT="2026-11-05T15:00:00Z"
HOME="Mississippi State Bulldogs"
AWAY="Test University"


def fixture():
    reports=[
        {"team": HOME, "player": "Starting RB", "position": "RB",
         "signal_kind": "AVAILABILITY", "status": "OUT",
         "published_at_utc": "2026-11-05T13:00:00Z",
         "captured_at_utc": "2026-11-05T13:10:00Z",
         "source_url": "https://example.edu/news/2026/rb"},
        {"team": HOME, "player": "Backup WR", "position": "WR",
         "signal_kind": "AVAILABILITY", "status": "QUESTIONABLE",
         "published_at_utc": "2026-11-05T13:00:00Z",
         "captured_at_utc": "2026-11-05T13:10:00Z",
         "source_url": "https://example.edu/news/2026/wr"}]
    context={
        "betting_status":"PASS_UNVALIDATED",
        "asof_utc":"2026-11-05T14:00:00Z",
        "captured_at_utc":"2026-11-05T14:10:00Z",
        "games":[{
            "game_id":"500","home":HOME,"away":AWAY,"kickoff_utc":KICK,
            "injury_coverage_by_team":{HOME:"VERIFIED_REPORT_REVIEWED",AWAY:"UNKNOWN"},
            "injury_reports":reports,"verified_qb_starters":{}}]}
    expected={
        "status":QB_STATUS,"season":2026,
        "observed_at_utc":"2026-11-05T14:55:00Z",
        "model_promoted":False,"betting_status":"PASS_UNVALIDATED",
        "games":[
            {"game_id":"500","team":HOME,"opponent":AWAY,"kickoff_utc":KICK,
             "observed_at_utc":"2026-11-05T14:55:00Z",
             "starter":"Kamario Taylor","is_confirmed_starter":False},
            {"game_id":"500","team":AWAY,"opponent":HOME,"kickoff_utc":KICK,
             "observed_at_utc":"2026-11-05T14:55:00Z",
             "starter":"Other QB","is_confirmed_starter":False}]}
    return context,expected


class IntakeBoardTests(unittest.TestCase):
    def test_all_position_evidence_and_season_out_reconcile(self):
        context,expected=fixture()
        original=copy.deepcopy(context)
        result=build(context,expected,REGISTRY,AT)
        self.assertEqual(context,original)
        self.assertEqual(result["status"],STATUS)
        home,away=result["games"]
        self.assertEqual(home["team"],HOME)
        self.assertEqual(home["report_coverage"],"VERIFIED_REPORT_REVIEWED")
        self.assertEqual(away["report_coverage"],"UNKNOWN")
        self.assertEqual(away["unlisted_player_status"],"UNKNOWN")
        self.assertEqual(home["current_qb_evidence"],"CONFLICT_REVIEW")
        self.assertIsNone(home["current_qb_candidate"])
        self.assertFalse(home["starter_eligible_for_model_input"])
        self.assertEqual(away["current_qb_evidence"],"PROJECTED_NOT_CONFIRMED")
        self.assertIsNone(away["current_qb_candidate"])
        self.assertEqual(away["historical_or_chart_qb_scenario"],"Other QB")
        self.assertFalse(away["starter_eligible_for_model_input"])
        self.assertEqual({(x["player"],x["position"],x["status"]) for x in home["players"]},
                         {("Starting RB","RB","OUT"),
                          ("Backup WR","WR","QUESTIONABLE"),
                          ("Kamario Taylor","QB","OUT")})
        self.assertEqual(result["summary"]["official_game_report_slots"],1)
        self.assertEqual(result["summary"]["official_player_designations"],3)
        self.assertFalse(result["original_scores_changed"])
        self.assertFalse(result["model_promoted"])

    def test_normalized_name_collision_quarantines_all_candidates(self):
        context,expected=fixture()
        row=context["games"][0]["injury_reports"][0]
        context["games"][0]["injury_reports"].append({
            **row,"player":"Starting-RB","status":"AVAILABLE",
            "published_at_utc":"2026-11-05T13:30:00Z",
            "captured_at_utc":"2026-11-05T13:35:00Z"})
        result=build(context,expected,REGISTRY,AT)
        home=result["games"][0]
        self.assertFalse(any(x["player"] in ("Starting RB","Starting-RB")
                             for x in home["players"]))
        self.assertEqual(result["summary"]["normalized_player_id_collisions"],1)
        self.assertIn("NORMALIZED_PLAYER_ID_COLLISION_REQUIRES_REVIEW",
                      {x["reason"] for x in home["quarantined_evidence"]})
        self.assertFalse(home["starter_eligible_for_model_input"])

    def test_unavailable_qb_cannot_be_reported_confirmed(self):
        context,expected=fixture()
        expected["games"][0]["is_confirmed_starter"]=True
        context["games"][0]["verified_qb_starters"]={HOME:{
            "player":"Kamario Taylor",
            "published_at_utc":"2026-11-05T12:00:00Z",
            "captured_at_utc":"2026-11-05T13:00:00Z",
            "reviewed_at_utc":"2026-11-05T13:20:00Z"}}
        r=build(context,expected,REGISTRY,AT)
        self.assertEqual(r["games"][0]["current_qb_evidence"],"CONFLICT_REVIEW")
        self.assertFalse(r["games"][0]["confirmed_qb_starter"])

    def test_verified_active_qb_requires_original_game_claim(self):
        context,expected=fixture()
        expected["games"][0]["starter"]="Available QB"
        expected["games"][0]["is_confirmed_starter"]=True
        with self.assertRaisesRegex(ValueError,"corroborated"):
            build(context,expected,REGISTRY,AT)
        context["games"][0]["verified_qb_starters"]={HOME:{
            "player":"Available QB",
            "published_at_utc":"2026-11-05T12:00:00Z",
            "captured_at_utc":"2026-11-05T13:00:00Z",
            "reviewed_at_utc":"2026-11-05T13:20:00Z"}}
        r=build(context,expected,REGISTRY,AT)
        self.assertTrue(r["games"][0]["confirmed_qb_starter"])
        self.assertEqual(r["games"][0]["current_qb_candidate"],"Available QB")
        self.assertTrue(r["games"][0]["starter_eligible_for_model_input"])

    def test_conflicting_university_and_conference_claims_are_review_only(self):
        context,expected=fixture()
        context["games"][0]["injury_reports"].append({
            "team":HOME,"player":"Kamario Taylor","position":"QB",
            "signal_kind":"AVAILABILITY","status":"AVAILABLE",
            "published_at_utc":"2026-11-05T13:00:00Z",
            "captured_at_utc":"2026-11-05T13:10:00Z",
            "source_url":"https://example.edu/availability"})
        result=build(context,expected,REGISTRY,AT)
        qb=next(x for x in result["games"][0]["players"] if x["position"]=="QB")
        self.assertEqual(qb["status"],"CONFLICT_REVIEW")
        self.assertEqual(result["games"][0]["current_qb_evidence"],"CONFLICT_REVIEW")

    def test_future_report_rejected_instead_of_reclassifying_injury(self):
        context,expected=fixture()
        context["games"][0]["injury_reports"][0]["published_at_utc"]="2026-11-06T00:00:00Z"
        result=build(context,expected,REGISTRY,AT)
        self.assertNotIn("Starting RB",[x["player"] for x in result["games"][0]["players"]])
        self.assertGreater(result["summary"]["quarantined_rows"],0)

    def test_wrong_fixture_or_future_qb_review_fails_closed(self):
        context,expected=fixture()
        expected["games"][0]["opponent"]="Wrong University"
        with self.assertRaisesRegex(ValueError,"fixture identity"):
            build(context,expected,REGISTRY,AT)
        context,expected=fixture()
        expected["observed_at_utc"]="2026-11-06T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"after decision"):
            build(context,expected,REGISTRY,AT)


if __name__=="__main__":
    unittest.main()

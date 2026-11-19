"""Availability is a separate forecast-eligibility decision, never guessed points."""
import copy
import datetime as dt
import unittest

from scripts.site_injury_forecast_gate import attach,STATUS
from scripts.official_longterm_qb_absences import apply as apply_official
from tests.test_official_longterm_qb_absences import board as sample,REGISTRY
from scripts.site_availability import merge as overlay

NOW="2026-11-04T02:00:00Z"
FUTURE="2026-11-07T20:00:00Z"


def baseline():
    g=sample()
    row=g["games"][0]
    row["model_ou_side"]="PASS"
    row["v14_matchup_shadow"]={"margin":9.,"total":53.}
    row["player_stat_outlook"]={"passing_yards":150.}
    row["v13_probability_shadow"]={"home_win_probability":.64}
    row["player_availability_home"]=[]
    row["player_availability_away"]=[]
    row["qb_availability_home"]=[]
    row["qb_availability_away"]=[]
    return g


def report(*,position="OL",player="Big Lineman",status="OUT",
           team="Mississippi State Bulldogs",published="2026-11-04T00:30:00Z",
           observed="2026-11-04T01:00:00Z"):
    return {"player":player,"position":position,"status":status,
        "source_url":"https://www.secsports.com/reports/current",
        "source_type":"OFFICIAL_CONFERENCE_AVAILABILITY",
        "published_at_utc":published,
        "observed_at_utc":observed,
        "not_starter_confirmation":True}


class RosterEligibilityTests(unittest.TestCase):
    def test_longterm_verified_qb_out_is_high_risk_and_original_model_untouched(self):
        board=apply_official(baseline(),REGISTRY,NOW)
        original=copy.deepcopy(board["games"][0])
        output=attach(board,NOW)
        risk=output["games"][0]["roster_model_eligibility"]
        self.assertEqual(risk["status"],STATUS)
        self.assertEqual(risk["injury_sensitive_ats_action"],
                         "PASS_QB_STATUS_OR_REPLACEMENT_UNRESOLVED")
        self.assertEqual(risk["injury_sensitive_total_action"],
                         "PASS_QB_STATUS_OR_REPLACEMENT_UNRESOLVED")
        self.assertEqual(risk["injury_sensitive_player_prop_action"],
                         "PASS_QB_STATUS_OR_REPLACEMENT_UNRESOLVED")
        side=risk["sides"]["home"]
        self.assertEqual(side["status"],"VERIFIED_LONGTERM_QB_OUT_UNCALIBRATED")
        self.assertEqual(side["confirmed_longterm_absences"][0]["player"],
                         "Kamario Taylor")
        self.assertFalse(side["verified_replacement_starter"])
        self.assertFalse(risk["model_promoted"])
        self.assertFalse(risk["safe_for_betting"])
        for field in ("v04_direct_scores","v14_matchup_shadow",
                      "v13_probability_shadow","model_ats_side",
                      "model_ou_side","model_home_margin","model_total",
                      "player_stat_outlook"):
            self.assertEqual(board["games"][0].get(field),original.get(field))

    def test_unknown_reports_do_not_imply_healthy_or_injury_points(self):
        b=baseline()
        result=attach(b,NOW)
        risk=result["games"][0]["roster_model_eligibility"]
        self.assertEqual(risk["injury_sensitive_total_action"],
                         "PASS_NO_VALIDATED_PERSONNEL_EFFECT")
        self.assertEqual(risk["sides"]["home"]["status"],
                         "NO_ACTIONABLE_VERIFIED_ISSUE_DETECTED")
        self.assertTrue(risk["unknown_is_not_healthy"])
        self.assertEqual(risk["sides"]["home"]["confirmed_longterm_absences"],[])
        self.assertFalse(result["roster_model_eligibility_summary"]
                         ["independent_injury_scoring_improvement_proven"])

    def test_outdated_future_and_postkickoff_sources_excluded(self):
        b=baseline()
        b["games"][0]["player_availability_home"]=[
            report(observed="2026-11-05T02:00:00Z"),
            report(player="Future",published="2026-11-05T01:00:00Z",
                   observed="2026-11-05T03:00:00Z")]
        result=attach(b,NOW)
        self.assertEqual(result["games"][0]["roster_model_eligibility"]["sides"]
                         ["home"]["other_actionable_reports"],[])
        future=baseline()
        future["games"][0]["official_longterm_qb_absences_home"]=[{
            "status":"OFFICIAL_SEASON_OUT_VERIFIED_AFTER_SOURCE_REVIEW",
            "source_type":"OFFICIAL_UNIVERSITY_STATEMENT",
            "player":"Starting QB",
            "first_eligible_at_utc":"2026-11-05T12:00:00Z",
            "source_url":"https://example.edu/news/2026/qb-out",
            "designation":"OUT_REMAINDER_2026",
            "replacement_value_calibrated":False,
            "changes_frozen_score":False}]
        r=attach(future,NOW)
        self.assertEqual(r["games"][0]["roster_model_eligibility"]["sides"]
                         ["home"]["confirmed_longterm_absences"],[])
        latest=baseline()
        latest["games"][0]["kickoff_utc"]="2026-11-03T19:00:00Z"
        self.assertIsNone(attach(latest,NOW)["games"][0]
                          ["roster_model_eligibility"])

    def test_nonqb_absence_is_visible_without_inventing_offensive_line_value(self):
        b=baseline()
        b["games"][0]["player_availability_home"]=[
            report(position="OL",status="OUT"),
            report(position="EDGE",player="Defender",status="QUESTIONABLE")]
        original=copy.deepcopy(b["games"][0])
        result=attach(b,NOW)
        risk=result["games"][0]["roster_model_eligibility"]
        self.assertEqual(risk["injury_sensitive_ats_action"],
                         "PASS_VERIFIED_NON_QB_EFFECT_UNCALIBRATED")
        self.assertEqual(len(risk["sides"]["home"]["other_actionable_reports"]),2)
        self.assertFalse(risk["sides"]["home"]["other_actionable_reports"][0]
                         ["point_replacement_value_known"])
        self.assertEqual(result["games"][0]["v14_matchup_shadow"],
                         original["v14_matchup_shadow"])

    def test_confirmed_qb_conflict_produces_conservative_pass(self):
        b=baseline()
        b["games"][0]["qb_home"]={"status":"CONFLICT_REVIEW",
                                  "player":"Kamario Taylor"}
        b["games"][0]["qb_availability_home"]=[
            report(position="QB",player="Kamario Taylor",status="OUT")]
        result=attach(b,NOW)
        self.assertEqual(result["games"][0]["roster_model_eligibility"]["sides"]
                         ["home"]["status"],"STARTER_IDENTITY_CONFLICT")
        self.assertEqual(result["roster_model_eligibility_summary"]["review_qb"],1)

    def test_unobserved_conference_report_fails_source_gate(self):
        b=baseline()
        b["games"][0]["player_availability_home"]=[
            {**report(),"source_type":"BLOG_POST"},
            {**report(player="Later"),"observed_at_utc":"2026-11-08T15:00:00Z"},
            {**report(player="No Source"),"source_url":""}]
        result=attach(b,NOW)
        self.assertEqual(result["games"][0]["roster_model_eligibility"]["sides"]
                         ["home"]["other_actionable_reports"],[])

    def test_duplicate_games_rejected(self):
        b=baseline()
        b["games"].append(copy.deepcopy(b["games"][0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            attach(b,NOW)

if __name__=="__main__":
    unittest.main()

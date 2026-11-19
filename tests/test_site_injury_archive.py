"""Roster risk must be frozen with the original game forecast and source time."""
import copy
import unittest
from scripts.site_decision_archive import freeze
from scripts.site_injury_forecast_gate import attach,STATUS
from tests.test_site_decision_archive import board,NOW

def ready():
    b=board()
    g=b["games"][0]
    g["qb_home"]={"player":"Current QB","status":"CONFLICT_REVIEW"}
    g["qb_away"]={"player":"Other QB","status":"UNKNOWN"}
    g["player_availability_home"]=[{
        "player":"Lineman","position":"OL","status":"OUT",
        "source_type":"OFFICIAL_CONFERENCE_AVAILABILITY",
        "not_starter_confirmation":True,
        "published_at_utc":"2026-10-24T14:00:00Z",
        "observed_at_utc":"2026-10-24T15:30:00Z",
        "source_url":"https://www.secsports.com/football/availability"}]
    return attach(b,NOW.isoformat())


class InjuryFreezeTests(unittest.TestCase):
    def test_archive_preserves_frozen_roster_decision_with_existing_model(self):
        b=ready()
        result=freeze(b,NOW,"888")
        row=result["rows"][0]
        risk=row["roster_frozen_forecast_eligibility"]
        self.assertEqual(risk["status"],STATUS)
        self.assertEqual(risk["sides"]["home"]["status"],
                         "STARTER_IDENTITY_CONFLICT")
        self.assertEqual(risk["injury_sensitive_ats_action"],
                         "PASS_QB_STATUS_OR_REPLACEMENT_UNRESOLVED")
        self.assertFalse(risk["model_promoted"])
        self.assertEqual(row["frozen_forecast_home_margin"],10.)
        self.assertEqual(row["displayed_ats_side"],"HOME")

    def test_archive_refuses_roster_risk_stamped_after_capture(self):
        b=ready()
        b["games"][0]["roster_model_eligibility"]["asof_utc"]="2026-10-24T16:00:00Z"
        with self.assertRaisesRegex(ValueError,"after prediction"):
            freeze(b,NOW,"888")

    def test_archive_refuses_forged_qb_and_team_identity(self):
        b=ready()
        modified=copy.deepcopy(b)
        modified["games"][0]["roster_model_eligibility"]["sides"]["home"]["team"]="Wrong School"
        with self.assertRaisesRegex(ValueError,"identity mismatch"):
            freeze(modified,NOW,"888")
        modified=copy.deepcopy(b)
        modified["games"][0]["roster_model_eligibility"]["model_promoted"]=True
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            freeze(modified,NOW,"888")

    def test_archive_refuses_source_first_seen_after_decision(self):
        b=ready()
        item=b["games"][0]["roster_model_eligibility"]["sides"]["home"]["other_actionable_reports"][0]
        item["observed_at_utc"]="2026-10-24T16:20:00Z"
        with self.assertRaisesRegex(ValueError,"observed after decision"):
            freeze(b,NOW,"888")

    def test_preexisting_snapshots_without_roster_layer_still_accepted(self):
        result=freeze(board(),NOW,"888")
        self.assertIsNone(result["rows"][0]["roster_frozen_forecast_eligibility"])

if __name__=="__main__":
    unittest.main()

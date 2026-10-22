"""Step 3B timestamp-safe availability snapshots; no health or betting inference."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.injury_history import observe, lookup, verify_observation, run

NOW = "2026-10-22T10:00:00Z"
KICK = "2026-10-24T20:00:00Z"
HOME = "Texas Longhorns"
AWAY = "Georgia Bulldogs"


def signal(player="Player One", status="OUT", published="2026-10-22T08:00:00Z",
           captured="2026-10-22T08:30:00Z", **changes):
    s = {"team": HOME, "player": player, "position": "QB", "signal_kind": "AVAILABILITY",
         "status": status, "published_at_utc": published, "captured_at_utc": captured,
         "source_url": "https://example.edu/football/availability"}
    s.update(changes)
    return s


def context(rows=None, coverage=None, kickoff=KICK):
    return {"asof_utc": "2026-10-22T09:45:00Z",
            "captured_at_utc": "2026-10-22T09:50:00Z",
            "games": [{"game_id": "101", "home": HOME, "away": AWAY,
                       "kickoff_utc": kickoff,
                       "injury_coverage_by_team": coverage if coverage is not None else
                            {HOME: "VERIFIED_REPORT_REVIEWED", AWAY: "UNKNOWN"},
                       "injury_reports": rows if rows is not None else []}]}


class InjuryHistoryTests(unittest.TestCase):
    def test_complete_game_team_slots_and_unknown_missing_report(self):
        snap = observe(context(), NOW)
        self.assertTrue(verify_observation(snap))
        self.assertEqual(snap["summary"]["game_team_slots"], 2)
        self.assertEqual(snap["summary"]["verified_team_reports"], 1)
        self.assertEqual(snap["summary"]["unknown_team_reports"], 1)
        self.assertEqual(snap["summary"]["reported_player_designations"], 0)
        self.assertEqual(lookup([snap], "101", AWAY, NOW)["coverage_status"], "UNKNOWN")
        self.assertEqual(lookup([snap], "101", HOME, NOW, "Unlisted Player")["status"], "UNKNOWN")
        self.assertFalse(snap["safe_for_betting"])

    def test_reported_out_is_not_diagnosis_or_participation(self):
        snap = observe(context([signal()]), NOW)
        result = lookup([snap], "101", HOME, NOW, "Player One")
        self.assertEqual(result["status"], "OUT")
        self.assertFalse(result["diagnosis_verified"])
        self.assertFalse(result["participation_verified"])
        self.assertEqual(result["source"]["signal_kind"], "AVAILABILITY")

    def test_future_source_after_context_cutoff_is_quarantined(self):
        snap = observe(context([signal(published="2026-10-22T09:46:00Z",
                                       captured="2026-10-22T09:47:00Z")]), NOW)
        self.assertEqual(snap["summary"]["reported_player_designations"], 0)
        self.assertEqual(snap["summary"]["quarantined_source_rows"], 1)
        self.assertNotIn('"reported_status": "OUT"', json.dumps(snap["rows"]))
        self.assertNotIn("Player One", json.dumps(snap["rows"]))
        self.assertEqual(snap["rows"][0]["quarantined_evidence"][0]["player"], "")

    def test_late_postobservation_or_postkickoff_source_rejected(self):
        snap = observe(context([signal(published="2026-10-25T01:00:00Z",
                                       captured="2026-10-25T02:00:00Z")]), NOW)
        self.assertEqual(snap["summary"]["reported_player_designations"], 0)
        self.assertEqual(snap["summary"]["quarantined_source_rows"], 1)

    def test_contradictory_equal_publication_never_selects_winner(self):
        one = signal(status="OUT")
        two = signal(status="AVAILABLE", captured="2026-10-22T09:00:00Z")
        snap = observe(context([one, two]), NOW)
        self.assertEqual(snap["summary"]["reported_player_designations"], 0)
        result = lookup([snap], "101", HOME, NOW, "Player One")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["reason"], "CONFLICT_REQUIRES_REVIEW")

    def test_out_to_available_is_only_a_reported_transition(self):
        s1 = observe(context([signal()]), NOW)
        s2 = observe(context([signal(status="AVAILABLE", published="2026-10-22T10:05:00Z",
                                    captured="2026-10-22T10:15:00Z")]), "2026-10-22T11:00:00Z")
        # Later context run has its own later evidence cutoff.
        self.assertEqual(s2["summary"]["reported_player_designations"], 0)
        c2 = context([signal(status="AVAILABLE", published="2026-10-22T10:05:00Z",
                             captured="2026-10-22T10:15:00Z")])
        c2["asof_utc"] = "2026-10-22T10:45:00Z"
        c2["captured_at_utc"] = "2026-10-22T10:50:00Z"
        s2 = observe(c2, "2026-10-22T11:00:00Z")
        early = lookup([s1, s2], "101", HOME, "2026-10-22T10:00:00Z", "Player One")
        late = lookup([s1, s2], "101", HOME, "2026-10-22T11:30:00Z", "Player One")
        self.assertEqual(early["status"], "OUT")
        self.assertEqual(late["status"], "AVAILABLE")
        self.assertEqual(late["reported_transitions"][0]["interpretation"],
                         "REPORTED_DESIGNATION_CHANGE_ONLY")
        self.assertFalse(late["diagnosis_verified"])

    def test_conflicting_cross_snapshot_same_publication_quarantined(self):
        s1 = observe(context([signal()]), NOW)
        c2 = context([signal(status="AVAILABLE", captured="2026-10-22T09:00:00Z")])
        s2 = observe(c2, "2026-10-22T11:00:00Z")
        r = lookup([s1, s2], "101", HOME, "2026-10-22T12:00:00Z", "Player One")
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertEqual(r["reason"], "CONFLICT_REQUIRES_REVIEW")

    def test_missing_latest_player_never_means_healed_or_stays_out(self):
        s1 = observe(context([signal()]), NOW)
        s2 = observe(context([]), "2026-10-22T11:00:00Z")
        self.assertEqual(lookup([s1, s2], "101", HOME,
                                "2026-10-22T11:15:00Z", "Player One")["status"], "UNKNOWN")

    def test_past_decision_and_postkickoff_not_eligible(self):
        snap = observe(context([signal()]), NOW)
        self.assertEqual(lookup([snap], "101", HOME, "2026-10-22T09:59:00Z", "Player One")["status"], "UNKNOWN")
        self.assertEqual(lookup([snap], "101", HOME, KICK, "Player One")["status"], "UNKNOWN")

    def test_invalid_integrity_and_future_tampering(self):
        base = observe(context([signal()]), NOW)
        for mutator in (
            lambda s: s["rows"][0].update(kickoff_utc="2026-10-22T09:00:00Z"),
            lambda s: s["rows"].append(copy.deepcopy(s["rows"][0])),
            lambda s: s["rows"][0]["reported_players"][0].update(
                published_at_utc="2026-10-23T00:00:00Z"),
            lambda s: s["summary"].update(reported_player_designations=999),
            lambda s: s["rows"][0].update(diagnosis_verified=True),
        ):
            changed = copy.deepcopy(base)
            mutator(changed)
            with self.assertRaises(ValueError):
                verify_observation(changed)

    def test_no_postkickoff_backfill(self):
        with self.assertRaisesRegex(ValueError, "No pregame"):
            observe(context([signal()], kickoff="2026-10-22T09:00:00Z"), NOW)

    def test_exclusive_create_persists_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "context.json").write_text(json.dumps(context([signal()])))
            output = root / "history.json"
            result = run(root / "context.json", output, NOW)
            self.assertTrue(verify_observation(json.loads(output.read_text())))
            self.assertEqual(result["summary"]["reported_player_designations"], 1)
            with self.assertRaises(FileExistsError):
                run(root / "context.json", output, NOW)


if __name__ == "__main__":
    unittest.main()

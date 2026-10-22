"""Step 3C point-in-time joins and research ablation gates."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.injury_history import observe as injury_observe
from scripts.qb_history import observe as qb_observe
from scripts.personnel_features import (
    join_capture, verify_joined, BASE_FIELDS, STATUS_FIELDS)
from scripts.personnel_ablation import (
    choose_capture_rows, ablate)
from scripts.personnel_capture import build as capture_join
from scripts.weekly_profiles import canonical
from scripts.pregame_evidence import sha

HOME = "Texas Longhorns"
AWAY = "Georgia Bulldogs"
KICK = "2026-10-24T20:00:00Z"
OBS = "2026-10-22T09:50:00Z"
CAPTURE = "2026-10-22T10:00:00Z"


def context(gid="101", home=HOME, away=AWAY, kickoff=KICK,
            reports=None, coverage=None):
    return {"asof_utc": "2026-10-22T09:45:00Z",
            "captured_at_utc": OBS,
            "games": [{"game_id": gid, "home": home, "away": away,
                       "kickoff_utc": kickoff, "injury_reports": reports or [],
                       "qb_availability_reports": [],
                       "verified_qb_starters": {},
                       "injury_coverage_by_team": coverage or
                       {home: "VERIFIED_REPORT_REVIEWED",
                        away: "VERIFIED_REPORT_REVIEWED"}},
                      ]}


def signal(team=HOME, status="OUT", name="Player One"):
    return {"team": team, "player": name, "position": "QB",
            "signal_kind": "AVAILABILITY", "status": status,
            "published_at_utc": "2026-10-22T08:00:00Z",
            "captured_at_utc": "2026-10-22T09:00:00Z",
            "source_url": "https://example.edu/football"}


def profile(team, val):
    return {"team": team, "prior_game_ids": ["older1"],
            "last_game_kickoff_utc": "2026-10-17T20:00:00Z",
            "recent_form": {
                "points_for": 30+val, "points_against": 20-val,
                "margin": 5+val, "win": 0.5+val/10,
                "epa_off_adj": 0.2+val/10, "epa_def_adj": 0.1,
                "epa_pass": 0.3, "epa_rush": 0.2,
                "success": 0.4, "explosive_pass": 0.1,
                "explosive_rush": 0.08, "pressure": 0.03,
                "drive_yards": 30, "pass_rate": 0.5, "epa_coverage": 1.0}}


def capture(ctx, when=CAPTURE, run="123456", val=1):
    game = ctx["games"][0]
    teams = {"home": profile(game["home"],val),
             "away": profile(game["away"],-val)}
    return {"status": "OBSERVED_PREGAME_RESEARCH_CAPTURE",
            "season": 2026, "run_id": run, "captured_at_utc": when,
            "sources": {
                "score_retrieved_utc": "2026-10-22T09:40:00Z",
                "advanced_retrieved_utc": "2026-10-22T09:41:00Z",
                "context_asof_utc": ctx["asof_utc"],
                "context_captured_utc": ctx["captured_at_utc"]},
            "games": [{"game_id": game["game_id"],
                       "kickoff_utc": game["kickoff_utc"],
                       "home": game["home"], "away": game["away"],
                       "team_profiles": teams,
                       "team_profiles_sha256": sha(canonical(teams)),
                       "profile_source": "RETROSPECTIVE_RECONSTRUCTION_UNVERIFIED"}],
            "historical_publication_times_verified": False,
            "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"}


def qb(ctx):
    queue = {"status": "QB_REVIEW_RESEARCH_ONLY",
             "asof_utc": "2026-10-22T09:48:00Z",
             "rows": [], "safe_for_betting": False,
             "betting_status": "PASS_UNVALIDATED"}
    return qb_observe(ctx, queue, OBS)


def personnel(ctx):
    return join_capture(capture(ctx), [qb(ctx)], [injury_observe(ctx, OBS)])


class PersonnelFeaturesTests(unittest.TestCase):
    def test_valid_join_source_backed_out_is_not_injury_diagnosis(self):
        ctx = context(reports=[signal()])
        joined = personnel(ctx)
        self.assertTrue(verify_joined(joined))
        row = joined["games"][0]
        self.assertEqual(row["features"]["availability_out_diff"], 1)
        self.assertEqual(row["features"]["availability_qb_out_diff"], 1)
        self.assertEqual(row["features"]["home_qb_reviewed"], 0)
        self.assertEqual(row["features"]["home_report_verified"], 1)
        self.assertEqual(row["personnel_by_side"]["home"]["unlisted_player_status"], "UNKNOWN")
        self.assertFalse(row["personnel_by_side"]["home"]["diagnosis_verified"])
        self.assertFalse(joined["model_validated"])
        self.assertNotIn("home_score", row)

    def test_missing_report_not_zero_inferred(self):
        ctx = context(reports=[signal()], coverage={HOME: "VERIFIED_REPORT_REVIEWED",
                                                     AWAY: "UNKNOWN"})
        joined = personnel(ctx)
        row = joined["games"][0]
        for k in STATUS_FIELDS:
            self.assertIsNone(row["features"][k])
        self.assertEqual(joined["summary"]["matchups_without_complete_availability"], 1)
        self.assertEqual(row["features"]["away_report_verified"], 0)

    def test_future_observation_does_not_leak(self):
        ctx = context(reports=[signal()])
        old = personnel(ctx)
        later_ctx = copy.deepcopy(ctx)
        later_ctx["asof_utc"] = "2026-10-22T10:45:00Z"
        later_ctx["captured_at_utc"] = "2026-10-22T10:50:00Z"
        later_ctx["games"][0]["injury_reports"] = [signal(status="AVAILABLE")]
        future = injury_observe(later_ctx, "2026-10-22T11:00:00Z")
        future_qb = qb_observe(later_ctx,
            {"status": "QB_REVIEW_RESEARCH_ONLY",
             "asof_utc": "2026-10-22T10:55:00Z", "rows": [],
             "safe_for_betting": False, "betting_status": "PASS_UNVALIDATED"},
            "2026-10-22T11:00:00Z")
        combined = join_capture(capture(ctx), [qb(ctx),future_qb],
                                [injury_observe(ctx,OBS),future])
        self.assertEqual(old["games"][0]["features"], combined["games"][0]["features"])

    def test_mismatched_game_team_or_kickoff_fails(self):
        ctx = context(reports=[signal()])
        wrong = injury_observe(ctx, OBS)
        wrong["rows"][0]["team"] = "Wrong school"
        with self.assertRaises(ValueError):
            join_capture(capture(ctx), [qb(ctx)], [wrong])

    def test_provenance_and_hash_tampering_fails(self):
        joined = personnel(context(reports=[signal()]))
        for mutation in (
            lambda o: o["games"][0]["features"].update(availability_out_diff=99),
            lambda o: o["games"][0]["team_profiles"]["home"]["recent_form"].update(margin=999),
            lambda o: o["games"][0].update(captured_at_utc="2026-10-25T10:00:00Z"),
        ):
            obj = copy.deepcopy(joined)
            mutation(obj)
            with self.assertRaises(ValueError):
                verify_joined(obj)

    def test_same_context_capture_source_mismatch_rejected(self):
        ctx = context()
        p = capture(ctx)
        ctx["asof_utc"] = "2026-10-22T09:46:00Z"
        with self.assertRaisesRegex(ValueError,"context identity mismatch"):
            capture_join(p,ctx)

    def test_end_to_end_capture_from_actual_context_with_no_news(self):
        ctx = context(reports=[signal()])
        joined = capture_join(capture(ctx), ctx)
        self.assertEqual(joined["summary"]["matchups"],1)
        self.assertEqual(joined["summary"]["reviewed_qb_slots"],0)
        self.assertEqual(joined["games"][0]["features"]["availability_out_diff"],1)

    def test_real_ablation_no_observed_labels_is_insufficient(self):
        joined = personnel(context(reports=[signal()]))
        result = ablate([joined],[],"2026-10-30T20:00:00Z")
        self.assertEqual(result["eligible_distinct_games"],1)
        self.assertEqual(result["labeled_eligible_games"],0)
        self.assertFalse(result["evidence_sufficient_for_real_ablation"])
        self.assertFalse(result["model_promoted"])
        self.assertEqual(result["betting_status"],"PASS_UNVALIDATED")
        self.assertIsNone(result["aggregate"]["profile_baseline"])
        self.assertEqual(result["ats_and_totals_betting_grades"],
                         "UNAVAILABLE_NO_VERIFIED_POINT_IN_TIME_MARKET")

    def test_outcome_known_after_cutoff_not_used_in_fold_training(self):
        ctx = context(reports=[signal()])
        joined = personnel(ctx)
        labels = [{"game_id":"101", "home":HOME, "away":AWAY, "kickoff_utc":KICK,
                   "home_score":21,"away_score":14,
                   "outcome_known_at_utc":"2026-11-01T12:00:00Z",
                   "source_url":"https://example.edu/final",
                   "evidence_status":"OBSERVED_POSTGAME_FINAL"}]
        report = ablate([joined], labels, "2026-10-30T00:00:00Z",min_train_games=2)
        self.assertEqual(report["labeled_eligible_games"],0)
        self.assertFalse(report["evidence_sufficient_for_real_ablation"])
        with self.assertRaisesRegex(ValueError,"Outcome timestamp"):
            bad = copy.deepcopy(labels)
            bad[0]["outcome_known_at_utc"]="2026-10-24T19:00:00Z"
            ablate([joined],bad,"2026-11-02T12:00:00Z")

    def test_policy_deduplicates_repeated_captures(self):
        ctx = context()
        first = personnel(ctx)
        second = copy.deepcopy(first)
        second["captured_at_utc"] = "2026-10-22T11:00:00Z"
        # Editing observation timestamp invalidates its proof; cannot silently resubmit.
        with self.assertRaises(ValueError):
            choose_capture_rows([first,second])

    def test_synthetic_ablation_uses_same_games_and_never_promotes(self):
        # Build six distinct fake observations with the same verified capture
        # contract. Synthetic labels are NOT empirical performance evidence.
        captures=[]
        labels=[]
        for i in range(6):
            day=(dt.date(2026,9,26)+dt.timedelta(days=7*i))
            start=dt.datetime.combine(day,dt.time(20),dt.timezone.utc)
            kickoff=start.isoformat()
            now=(start-dt.timedelta(hours=36)).isoformat()
            ctx=context(gid=str(200+i),kickoff=kickoff,
                        reports=[signal(status="OUT" if i%2 else "AVAILABLE")])
            ctx["asof_utc"]=(start-dt.timedelta(hours=38)).isoformat()
            ctx["captured_at_utc"]=(start-dt.timedelta(hours=37)).isoformat()
            p=capture(ctx,when=now,run=str(100000+i),val=i+1)
            p["sources"]["score_retrieved_utc"]=(start-dt.timedelta(hours=39)).isoformat()
            p["sources"]["advanced_retrieved_utc"]=(start-dt.timedelta(hours=39)).isoformat()
            # For synthetic fixtures the snapshot construction is equivalent
            # to an observed game/team report at the contextual capture instant.
            future=[]
            for team, opponent in ((HOME,AWAY),(AWAY,HOME)):
                future.append({
                    "game_id":str(200+i), "team":team,"opponent":opponent,
                    "kickoff_utc":kickoff,
                    "observed_at_utc":ctx["captured_at_utc"],
                    "coverage_status":"VERIFIED_REPORT_REVIEWED",
                    "reported_players":[],
                    "quarantined_evidence":[],
                    "unlisted_players_status":"UNKNOWN",
                    "diagnosis_verified":False,"participation_verified":False})
            # A fully validated pregame capture can join with zero personnel
            # source history; every unknown is explicit.  This tests training
            # mechanics only, not real injury signals.
            j=join_capture(p,[],[])
            captures.append(j)
            labels.append({"game_id":str(200+i), "home":HOME,"away":AWAY,
                           "kickoff_utc":kickoff,"home_score":21+i,
                           "away_score":18+i//2,
                           "outcome_known_at_utc":(start+dt.timedelta(hours=5)).isoformat(),
                           "source_url":"https://example.edu/fictional-final",
                           "evidence_status":"OBSERVED_POSTGAME_FINAL"})
        result=ablate(captures,labels,"2026-12-15T00:00:00Z",
                      start_date="2026-10-10",min_train_games=2,min_test_games=1)
        self.assertGreater(result["aggregate"]["profile_baseline"]["games"],0)
        self.assertFalse(result["evidence_sufficient_for_real_ablation"])
        self.assertEqual(result["comparisons"]["all_personnel"]["status"],
                         "NOT_COMPARABLE_MISSING_MATCHED_FOLDS")
        self.assertFalse(result["model_promoted"])


if __name__ == "__main__":
    unittest.main()

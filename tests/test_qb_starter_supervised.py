"""Exact as-of starter-label joins must not train on future or guessed QBs."""
import copy,unittest,hashlib,json,tempfile
from pathlib import Path
from scripts import context_archive as store
from scripts.personnel_forecast import checksum
from scripts.qb_starter_supervised import build,read_archives,STATUS
from scripts.qb_postgame_starter_archive import empty,LABEL,UNKNOWN,DANGER

KICK="2026-10-31T20:00:00Z"
PRE="2026-10-29T16:00:00Z"
LATE="2026-11-01T02:00:00Z"
NOW="2026-11-02T12:00:00Z"
URL="https://a.edu/sports/football/stats/2026/b/boxscore/1"

def snapshot(at=PRE,run="991",players=("A One","A Two")):
    return {"status":"QB_CONDITIONAL_PLAYER_EPA_FROZEN_SHADOW_RESEARCH_ONLY",
      "season":2026,"observed_at_utc":at,"baseline_forecast_run_id":run,
      "baseline_forecast_sha256":"a"*64,
      "historical_pbp_publication_authenticated":False,
      "model_promoted":False,"safe_for_betting":False,
      "betting_status":"PASS_UNVALIDATED",
      "games":[{"game_id":"401856727","home":"A","away":"B","kickoff_utc":KICK,
        "baseline_row_sha256":"b"*64,
        "candidate":{"status":"QB_PLAYER_CONDITIONAL_SHADOW",
          "model_promoted":False,"betting_status":"PASS_UNVALIDATED",
          "expected_starters_by_side":{
            "home":{"player":"A One","status":"PROJECTED_DEPTH_CHART_ONLY",
                    "confidence":"LOW_UNCONFIRMED"},
            "away":{"player":None,"status":"UNKNOWN","confidence":"UNKNOWN"}},
          "empirical_pass_exposure_by_side":{
            "home":{"weights":{"A One":.7,"A Two":.2},"unknown_weight":.1},
            "away":{"weights":{},"unknown_weight":1.}},
          "player_scenarios_by_side":{
            "home":{name:{"depth_rank":i+1,"prior_passing_plays":40,
                          "player_passing_epa":.1,"margin_impact":.3}
                    for i,name in enumerate(players)},
            "away":{}}}}]}
def registry():
    return {"status":"MANUALLY_REVIEWED_OFFICIAL_SCHOOL_POSTGAME_BOXSCORES",
       "season":2026,"entries":[{"game_id":"401856727","home":"A","away":"B",
        "home_starting_qb_name":"A Two","away_starting_qb_name":"B QB",
        "source_url":URL,"reviewed_official_publisher":True}]}
def ledger(player="A Two",captured=LATE,source=URL):
    p="research_2026/qb_postgame_starters/2026/11/01/run-991.json.gz"
    o={"path":p,"captured_at_utc":captured,
        "label_status":LABEL,"starter_player":player,
        "source_url":source,"source_class":"REVIEWED_OFFICIAL_SCHOOL_BOXSCORE_HTML",
        "source_payload_sha256":"f"*64}
    return {"status":"QB_POSTGAME_STARTER_OBSERVATION_LEDGER_RESEARCH_ONLY",
       "season":2026,"runs":[{"run_id":"991","path":p,
          "sha256":"e"*64,"captured_at_utc":captured}],
       "slots":{"401856727|A":{"game_id":"401856727","team":"A",
          "effective_status":LABEL,"starter_player":player,"observations":[o]}},
       "model_promoted":False,"betting_status":"PASS_UNVALIDATED"}

class SupervisedQBTests(unittest.TestCase):
    def test_exact_reviewed_source_creates_one_trainable_group(self):
        x=build([snapshot()],ledger(),registry(),NOW)
        self.assertEqual(x["status"],STATUS)
        self.assertFalse(x["ready_for_calibrated_starter_training"])
        self.assertFalse(x["can_estimate_calibrated_starter_probabilities"])
        self.assertEqual(x["summary"]["labeled_trainable_slots"],1)
        row=x["examples"][0]
        self.assertEqual(row["actual_starter_player"],"A Two")
        self.assertEqual(row["starter_expected_source_confidence"],"LOW_UNCONFIRMED")
        self.assertEqual(row["unknown_pregame_pass_exposure"],.1)
        self.assertEqual(sum(p["is_actual_postgame_starter"] for p in row["candidates"]),1)
        self.assertEqual(sum(p["is_projected_next_starter"] for p in row["candidates"]),1)
    def test_older_frozen_prediction_is_not_selected_when_newer_predecision(self):
        older=snapshot("2026-10-28T22:00:00Z","990")
        later=snapshot("2026-10-29T19:00:00Z","991")
        x=build([older,later],ledger(),registry(),NOW)
        self.assertEqual(x["examples"][0]["pregame_run_id"],"991")
        self.assertEqual(x["examples"][0]["pregame_observed_utc"],later["observed_at_utc"])
    def test_stale_or_postkickoff_forecasts_cannot_be_labeled(self):
        out=build([snapshot("2026-10-27T12:00:00Z")],ledger(),registry(),NOW)
        self.assertEqual(out["summary"]["labeled_trainable_slots"],0)
        with self.assertRaisesRegex(ValueError,"Postkickoff"):
            build([snapshot("2026-10-31T20:01:00Z")],ledger(),registry(),NOW)
    def test_late_observed_actual_label_cannot_enter_early_training(self):
        out=build([snapshot()],ledger(),registry(),"2026-10-31T22:00:00Z")
        self.assertEqual(out["summary"]["labeled_trainable_slots"],0)
    def test_historical_parser_name_corruption_is_excluded(self):
        bad=ledger(player="A B Team Two")
        x=build([snapshot()],bad,registry(),NOW)
        self.assertEqual(x["summary"]["labeled_trainable_slots"],0)
        self.assertEqual(x["summary"]["skip_reasons"]["SCHOOL_PARSER_NAME_OR_SOURCE_UNREVIEWED"],1)
    def test_true_starter_outside_frozen_roster_is_not_fabricated_training_label(self):
        out=build([snapshot(players=("A One","A Three"))],ledger(),registry(),NOW)
        self.assertEqual(out["summary"]["labeled_trainable_slots"],0)
        self.assertEqual(out["summary"]["out_of_roster_verified_labels"],1)
    def test_no_postgame_source_keeps_training_empty(self):
        index=ledger();index["slots"]={}
        out=build([snapshot()],index,registry(),NOW)
        self.assertEqual(out["summary"]["labeled_trainable_slots"],0)
        self.assertFalse(out["ready_for_calibrated_starter_training"])
    def test_explicit_source_must_match_current_reviewed_gamebook(self):
        out=build([snapshot()],ledger(source="https://wrong.edu/sports/football/stats/2026/b/boxscore/1"),
                  registry(),NOW)
        self.assertEqual(out["summary"]["labeled_trainable_slots"],0)
        self.assertEqual(out["summary"]["skip_reasons"]["SCHOOL_PARSER_NAME_OR_SOURCE_UNREVIEWED"],1)
    def test_edited_or_conflicted_effective_status_cannot_train(self):
        index=ledger();index["slots"]["401856727|A"]["effective_status"]=DANGER
        index["slots"]["401856727|A"]["starter_player"]=None
        out=build([snapshot()],index,registry(),NOW)
        self.assertEqual(out["summary"]["labeled_trainable_slots"],0)
    def test_unknown_postgame_starter_creates_targeted_review_not_train_label(self):
        index=ledger()
        slot=index["slots"]["401856727|A"]
        slot["starter_player"]=None
        slot["effective_status"]=UNKNOWN
        slot["observations"][0]["label_status"]=UNKNOWN
        slot["observations"][0]["starter_player"]=None
        out=build([snapshot()],index,registry(),NOW)
        self.assertEqual(out["summary"]["labeled_trainable_slots"],0)
        self.assertEqual(out["summary"]["postgame_manual_source_review_targets"],1)
        t=out["review_targets"][0]
        self.assertEqual((t["game_id"],t["team"]),("401856727","A"))
        self.assertEqual(t["reason"],"NOT_REVIEWED_ACTUAL_STARTER")
        self.assertIsNone(t["exact_school_gamebook_url"])
        self.assertEqual(t["frozen_qb_candidate_names"],["A One","A Two"])
        self.assertTrue(t["do_not_guess_gamebook_url"])

    def test_verified_but_unlisted_actual_qb_still_requires_roster_review(self):
        out=build([snapshot(players=("A One","A Three"))],ledger(),registry(),NOW)
        self.assertEqual(out["summary"]["postgame_manual_source_review_targets"],1)
        t=out["review_targets"][0]
        self.assertEqual(t["reason"],"VERIFIED_STARTER_NOT_IN_FROZEN_CANDIDATES")
        self.assertEqual(t["actual_starter"],"A Two")
        self.assertEqual(out["summary"]["labeled_trainable_slots"],0)

    def test_verified_trainable_source_does_not_emit_unneeded_review(self):
        out=build([snapshot()],ledger(),registry(),NOW)
        self.assertEqual(out["summary"]["postgame_manual_source_review_targets"],0)

    def test_no_completed_evidence_is_not_targeted_for_source_review(self):
        idx=ledger();idx["slots"]={}
        out=build([snapshot()],idx,registry(),NOW)
        self.assertEqual(out["summary"]["postgame_manual_source_review_targets"],0)

    def test_duplicate_frozen_run_rejected(self):
        r=snapshot()
        with self.assertRaisesRegex(ValueError,"Repeated immutable"):
            build([r,r],ledger(),registry(),NOW)
    def test_untrusted_rank_causes_failure_without_training(self):
        r=snapshot();r["games"][0]["candidate"]["player_scenarios_by_side"]["home"]["A One"]["depth_rank"]=0
        with self.assertRaisesRegex(ValueError,"depth rank"):
            build([r],ledger(),registry(),NOW)
    def test_missing_registrar_and_fake_betting_clearance_rejected(self):
        with self.assertRaises(ValueError):
            build([snapshot()],ledger(),{"status":"MISSING"},NOW)
        r=snapshot();r["betting_status"]="PROMOTED"
        with self.assertRaises(ValueError):build([r],ledger(),registry(),NOW)

    def test_local_checkout_verifies_candidate_and_postgame_archive(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            candidate=snapshot()
            forecast_path="research_2026/candidate_shadow_qb/2026/10/29/run-991.json.gz"
            ci={"season":2026,"status":candidate["status"],
                "runs":[{"run_id":"991","path":forecast_path,
                         "sha256":checksum(candidate)}]}
            known=ledger()
            source_path=known["runs"][0]["path"]
            source={"run_id":"991","rows":[{
                "game_id":"401856727","team":"A","starter_player":"A Two",
                "label_status":LABEL,"source_url":URL,
                "source_payload_sha256":"f"*64}]}
            known["runs"][0]["sha256"]=hashlib.sha256(store.encode(source)).hexdigest()
            fixtures={
                "research_2026/candidate_shadow_qb/index.json":store.encode(ci),
                forecast_path:store.pack(candidate),
                "research_2026/qb_postgame_starters/index.json":store.encode(known),
                source_path:store.pack(source)}
            for name,data in fixtures.items():
                file=base/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
            forecasts,labels=read_archives(base)
            result=build(forecasts,labels,registry(),NOW)
            self.assertEqual(result["summary"]["labeled_trainable_slots"],1)
            tampered=dict(source,rows=[{**source["rows"][0],"starter_player":"A One"}])
            (base/source_path).write_bytes(store.pack(tampered))
            with self.assertRaisesRegex(ValueError,"Tampered postgame"):
                read_archives(base)

if __name__=="__main__":unittest.main()

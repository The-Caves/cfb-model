"""Exact as-of starter-label joins must not train on future or guessed QBs."""
import copy,unittest
from scripts.qb_starter_supervised import build,STATUS
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
        for t in ("2026-10-27T12:00:00Z","2026-10-31T20:01:00Z"):
            out=build([snapshot(t)],ledger(),registry(),NOW)
            self.assertEqual(out["summary"]["labeled_trainable_slots"],0)
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

if __name__=="__main__":unittest.main()

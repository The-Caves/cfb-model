"""Step 3D audit: archived observed pregame-to-postgame final pairing."""
import copy
import datetime as dt
import json
import unittest

from scripts.personnel_results_archive import (
    _choose, _empty_index, _observe_index, _valid_manifest, _finals,
    _fresh_capture, _link_observed_finals, plan, POLICY, STATUS)
from scripts.personnel_features import join_capture
from scripts.pregame_evidence import sha
from scripts.weekly_profiles import canonical

HOME = "Texas Longhorns"
AWAY = "Georgia Bulldogs"
KICK = "2026-10-24T20:00:00Z"
WHEN = "2026-10-22T20:00:00Z"
NOW = "2026-10-22T20:02:00Z"


def fixture(gid="101", captured=WHEN, kickoff=KICK, run="123456"):
    profile = {
        "recent_form": {"margin":1,"points_for":21,"points_against":20,
                        "win":.5,"epa_off_adj":.1,"epa_def_adj":.2},
        "prior_game_ids":["old"]}
    profiles = {"home": {**profile, "team":HOME},
                "away": {**profile,"team":AWAY}}
    capture = {
        "status": "OBSERVED_PREGAME_RESEARCH_CAPTURE", "season":2026,
        "run_id":str(run), "captured_at_utc":captured,
        "sources": {
            "score_retrieved_utc": "2026-10-22T19:40:00Z",
            "advanced_retrieved_utc": "2026-10-22T19:40:00Z",
            "context_asof_utc": "2026-10-22T19:45:00Z",
            "context_captured_utc": "2026-10-22T19:50:00Z"},
        "games": [{
            "game_id":gid,"home":HOME,"away":AWAY,"kickoff_utc":kickoff,
            "team_profiles":profiles,
            "team_profiles_sha256":sha(canonical(profiles)),
            "profile_source":"RETROSPECTIVE_RECONSTRUCTION_UNVERIFIED"}],
        "historical_publication_times_verified":False,
        "capture_artifact_authenticity_verified":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    joined = join_capture(capture, [], [])
    return capture, joined


def manifest(t="2026-10-25T02:00:00Z"):
    return {"status":"SUCCESS","failures":[],
            "scoreboard_date_timezone":"America/New_York",
            "retrieved_at_utc":t}


def final(gid="101", kickoff=KICK, home=HOME, away=AWAY, hs="28", as_="17"):
    return {"game_id":gid,"home":home,"away":away,"kickoff_utc":kickoff,
            "home_score":hs,"away_score":as_}


def compose(cap=None, joined=None, index=None, outcomes=None, games=None,
            run="123456", now=NOW, scoreboard=None):
    if cap is None or joined is None:
        cap,joined = fixture()
    if scoreboard is None:
        scoreboard = manifest("2026-10-22T20:01:00Z")
    return plan(cap,joined,index or _empty_index(),outcomes or _empty_index(),
                games or [],scoreboard,now,run,"a"*64)


class ResultsArchiveTests(unittest.TestCase):
    def test_new_capture_has_observation_and_unknown_by_default(self):
        c,j=fixture()
        bundle,index,outcomes,labels,summary=compose(c,j)
        self.assertEqual(summary["new_pregame_game_slots"],1)
        self.assertEqual(summary["newly_linked_final_games"],0)
        self.assertEqual(summary["distinct_games_observed"],1)
        self.assertFalse(summary["model_promoted"])
        self.assertFalse(bundle["safe_for_betting"])
        self.assertEqual(index["games"]["101"][0]["home"],HOME)
        self.assertNotIn("home_score",str(bundle["joined"]["games"]))

    def test_append_only_retry_same_run_id_and_digest(self):
        c,j=fixture()
        _,index,prior,_,s=compose(c,j)
        _,again,_,_,s2=compose(c,j,index=index)
        self.assertEqual(s2["new_pregame_game_slots"],0)
        self.assertEqual(again,index)
        j["games"][0]["personnel_by_side"]["home"]["diagnosis_verified"]=True
        with self.assertRaises(ValueError):
            compose(c,j,index=index)

    def test_postkickoff_cannot_become_pregame_capture(self):
        # Profile join itself must reject the invalid after-kickoff record.
        with self.assertRaises(ValueError):
            fixture(captured="2026-10-25T00:00:00Z")

    def test_future_or_stale_capture_does_not_archive(self):
        c,j=fixture()
        with self.assertRaises(ValueError):
            compose(c,j,now="2026-10-22T19:59:00Z",
                    scoreboard=manifest("2026-10-22T19:58:00Z"))
        with self.assertRaises(ValueError):
            compose(c,j,now="2026-10-23T12:00:00Z",
                    scoreboard=manifest("2026-10-23T11:59:00Z"))

    def test_wrong_workflow_run_id_rejected(self):
        c,j=fixture()
        with self.assertRaises(ValueError):
            compose(c,j,run="55555")

    def test_pre_decision_window_selects_latest_observed(self):
        a={"captured_at_utc":"2026-10-21T22:00:00Z","path":"early","kickoff_utc":KICK}
        b={"captured_at_utc":"2026-10-22T10:00:00Z","path":"late","kickoff_utc":KICK}
        future={"captured_at_utc":"2026-10-24T19:00:00Z","path":"1h","kickoff_utc":KICK}
        selected=_choose([a,b,future],dt.datetime(2026,10,24,20,tzinfo=dt.timezone.utc))
        self.assertEqual(selected["path"],"late")
        self.assertIsNone(_choose([future],dt.datetime(2026,10,24,20,tzinfo=dt.timezone.utc)))

    def test_outcome_final_only_after_observation(self):
        c,j=fixture()
        _,index,_,_,_=compose(c,j)
        next_capture,next_joined=fixture(gid="102",run="123457",
            captured="2026-10-25T02:00:00Z",
            kickoff="2026-10-27T20:00:00Z")
        bundle,index2,out,labels,summary=compose(
            next_capture,next_joined,index=index,games=[final()],
            run="123457",now="2026-10-25T02:01:00Z",
            scoreboard=manifest("2026-10-25T02:00:00Z"))
        self.assertEqual(summary["newly_linked_final_games"],1)
        self.assertEqual(summary["new_pregame_game_slots"],1)
        self.assertEqual(summary["cumulative_linked_final_games"],1)
        self.assertEqual(out["games"]["101"]["selected_pregame"]["path"],
                         index["games"]["101"][0]["path"])
        self.assertEqual(labels[0][1]["actual_margin"],11)
        self.assertEqual(labels[0][1]["actual_total"],45)
        self.assertEqual(labels[0][1]["outcome_known_at_utc"],
                         "2026-10-25T02:00:00+00:00")
        self.assertFalse(labels[0][1]["safe_for_betting"])
        self.assertNotIn("home_score",json.dumps(bundle["joined"]))
        # Score revisions are never silently accepted; label stays original.
        later_capture,later_join=fixture(gid="103",run="123458",
            captured="2026-10-25T03:00:00Z",
            kickoff="2026-10-27T20:00:00Z")
        _,_,still,none,new_summary=compose(later_capture,later_join,
            index=index2,outcomes=out,games=[final(hs="29")],
            run="123458",now="2026-10-25T03:01:00Z",
            scoreboard=manifest("2026-10-25T03:00:00Z"))
        self.assertFalse(none)
        self.assertEqual(still["games"]["101"]["home_score"],28)
        self.assertEqual(new_summary["pending"]["conflicting_later_score_requires_review"],1)


    def test_game_rescheduling_keeps_old_observations_but_prevents_mismatch(self):
        c,j=fixture()
        _,index,_,_,_=compose(c,j)
        new_c,new_j=fixture(run="123457",captured="2026-10-22T20:01:00Z",kickoff="2026-10-25T20:00:00Z")
        _,second,_,_,_=compose(new_c,new_j,index=index,run="123457")
        self.assertEqual(len(second["games"]["101"]),2)
        observed=second["games"]["101"]
        self.assertEqual(_choose(observed,dt.datetime(2026,10,24,20,
                               tzinfo=dt.timezone.utc))["kickoff_utc"],KICK)
        rescheduled=_choose(observed,dt.datetime(2026,10,25,20,
                               tzinfo=dt.timezone.utc))
        self.assertEqual(rescheduled["kickoff_utc"],"2026-10-25T20:00:00Z")

    def test_invalid_and_future_score_manifest_rejected(self):
        with self.assertRaises(ValueError):
            compose(scoreboard=manifest("2026-10-22T20:10:00Z"))
        bad=manifest("2026-10-22T20:01:00Z")
        bad["status"]="INCOMPLETE"
        with self.assertRaises(ValueError):
            compose(scoreboard=bad)
        with self.assertRaises(ValueError):
            compose(games=[final()],scoreboard=manifest("2026-10-22T20:01:00Z"))

    def test_duplicate_scoreboard_game_and_wrong_team_block(self):
        with self.assertRaises(ValueError):
            _finals([final(),final()],dt.datetime(2026,10,25,2,
                                                 tzinfo=dt.timezone.utc))
        c,j=fixture()
        _,index,_,_,_=compose(c,j)
        new_c,new_j=fixture(gid="102",run="123457",
            captured="2026-10-25T02:00:00Z",
            kickoff="2026-10-27T20:00:00Z")
        _,_,_,labels,summary=compose(new_c,new_j,index=index,
            games=[final(home="Other school")],run="123457",
            now="2026-10-25T02:01:00Z",
            scoreboard=manifest("2026-10-25T02:00:00Z"))
        self.assertEqual(labels,[])
        self.assertEqual(summary["pending"]["missing_24_to_72_hour_capture"],1)


    def test_settlement_only_links_previous_pregame_without_new_capture(self):
        capture,joined=fixture()
        _,original_index,_,_,_=compose(capture,joined)
        frozen=json.loads(json.dumps(original_index))
        known=dt.datetime(2026,10,25,2,tzinfo=dt.timezone.utc)
        finals=_finals([final()],known)
        out,labels,counts=_link_observed_finals(
            original_index,_empty_index(),finals,known,
            "d"*64,known+dt.timedelta(minutes=1))
        self.assertEqual(original_index,frozen)
        self.assertEqual(len(labels),1)
        self.assertEqual(out["games"]["101"]["home_score"],28)
        self.assertEqual(out["games"]["101"]["selected_pregame"]["path"],
                         original_index["games"]["101"][0]["path"])
        self.assertEqual(labels[0][1]["source_scoreboard_sha256"],"d"*64)
        self.assertEqual(labels[0][1]["betting_status"],"PASS_UNVALIDATED")
        again,none,pending=_link_observed_finals(
            original_index,out,finals,known,
            "d"*64,known+dt.timedelta(minutes=5))
        self.assertFalse(none)
        self.assertEqual(pending["already_archived"],1)

    def test_settlement_only_does_not_turn_future_games_into_labels(self):
        cap,j=fixture()
        _,idx,_,_,_=compose(cap,j)
        now=dt.datetime(2026,10,22,20,1,tzinfo=dt.timezone.utc)
        with self.assertRaises(ValueError):
            _finals([final()],now)
        outcomes,labels,pending=_link_observed_finals(
            idx,_empty_index(),{},now,"e"*64,now)
        self.assertFalse(labels)
        self.assertEqual(pending["no_observed_final_yet"],1)
        self.assertFalse(outcomes["games"])


if __name__ == "__main__":
    unittest.main()

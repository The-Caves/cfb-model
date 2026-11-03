"""Same-run independent V04 control must predate QB forecast and final."""
import copy
import unittest

from scripts.qb_v04_same_intake import build,attach,STATUS
from scripts.qb_v04_archive_pair import enrich
from scripts.candidate_shadow_grade import evaluate
from test_candidate_shadow_grade import candidate,grade
from test_site_home_bias_guard import completed,context,manifest

SOURCE_TIME="2026-10-31T15:19:00Z"
QB_TIME="2026-10-31T15:25:00Z"
KICK="2026-11-02T20:00:00Z"


def setup():
    ctx=context(1)
    ctx["games"][0]["kickoff_utc"]=KICK
    scores=build(ctx,completed(),manifest(),SOURCE_TIME,"1"*64,"2"*64)
    q=candidate("qb")
    q["observed_at_utc"]=QB_TIME
    q["games"][0].update({"game_id":"1000","home":"Navy Midshipmen",
                          "away":"Notre Dame Fighting Irish","kickoff_utc":KICK})
    q["summary"]={}
    final=grade()
    final.update({"game_id":"1000","home":"Navy Midshipmen",
                  "away":"Notre Dame Fighting Irish","kickoff_utc":KICK,
                  "final_outcome_known_at_utc":"2026-11-03T02:00:00Z"})
    return ctx,scores,q,final


class SameIntakeV04Tests(unittest.TestCase):
    def test_source_cutoff_and_frozen_v04_are_independent(self):
        ctx,scores,q,final=setup()
        self.assertEqual(scores["status"],STATUS)
        self.assertEqual(scores["source_training_games"],120)
        self.assertEqual(scores["summary"]["games_with_v04"],1)
        self.assertFalse(scores["market_used_for_fit"])
        self.assertFalse(scores["direct_score_fit_uses_v03"])
        self.assertLess(scores["observed_at_utc"],QB_TIME)
        self.assertIsNotNone(scores["games"][0]["v04_direct_score"])
        self.assertEqual(scores["games"][0]["v04_direct_score"]["model"],
                         scores["model"])

    def test_frozen_same_intake_is_graded_and_not_forged_website_record(self):
        ctx,scores,q,final=setup()
        snap=attach(q,scores)
        score=snap["games"][0]["same_intake_v04"]
        self.assertEqual(score["source_bundle_sha256"],
                         snap["same_intake_v04_source_sha256"])
        self.assertTrue(score["before_qb_shadow_issued"])
        self.assertTrue(score["not_a_published_website_snapshot"])
        original=copy.deepcopy(snap)
        grade_report=evaluate({"qb":[snap],"venue":[]},[final],
                              "2026-11-03T03:00:00Z")
        paired=enrich(grade_report,[snap],[])
        self.assertEqual(paired["v04_comparison_audit"]["same_game_v04_pair_count"],1)
        self.assertEqual(paired["v04_comparison_audit"]["same_intake_frozen_score_pairs"],1)
        pair=paired["per_game"][0]["v04_paired_reference"]
        self.assertEqual(pair["v04_source_kind"],"SAME_INTAKE_BEFORE_QB_SHADOW")
        self.assertIsNone(pair["site_snapshot_run_id"])
        self.assertIsNone(pair["site_snapshot_sha256"])
        self.assertTrue(pair["source_hashed_before_qb_decision"])
        self.assertEqual(pair["v04_source_receipt_sha256"],
                         snap["same_intake_v04_source_sha256"])
        self.assertEqual(original["games"][0]["same_intake_v04"]["home_margin"],
                         score["home_margin"])

    def test_future_scores_and_same_day_garbage_time_not_allowed(self):
        ctx,scores,q,final=setup()
        late=manifest()
        late["retrieved_at_utc"]="2026-10-31T15:26:00Z"
        with self.assertRaisesRegex(ValueError,"Late or untrusted"):
            build(ctx,completed(),late,SOURCE_TIME,"1"*64,"2"*64)
        rows=completed()
        rows[-1]["date"]="2026-10-31"
        rows[-1]["kickoff_utc"]="2026-10-31T14:00:00Z"
        valid=build(ctx,rows,manifest(),SOURCE_TIME,"1"*64,"2"*64)
        self.assertEqual(valid["same_day_completed_scores_embargoed"],1)
        self.assertEqual(valid["source_training_games"],119)
        rows[-1]["kickoff_utc"]="2026-10-31T21:00:00Z"
        with self.assertRaisesRegex(ValueError,"after forecast cutoff"):
            build(ctx,rows,manifest(),SOURCE_TIME,"1"*64,"2"*64)

    def test_source_after_qb_and_identity_change_rejected(self):
        ctx,scores,q,final=setup()
        bad=copy.deepcopy(scores)
        bad["observed_at_utc"]="2026-10-31T15:26:00Z"
        with self.assertRaisesRegex(ValueError,"observed after QB"):
            attach(q,bad)
        bad=copy.deepcopy(scores)
        bad["games"][0]["away"]="Other Team"
        with self.assertRaisesRegex(ValueError,"game/clock changed"):
            attach(q,bad)

    def test_tampered_predecision_score_or_provenance_rejected(self):
        ctx,scores,q,final=setup()
        snap=attach(q,scores)
        recorded=evaluate({"qb":[snap],"venue":[]},[final],
                          "2026-11-03T03:00:00Z")
        bad=copy.deepcopy(snap)
        bad["games"][0]["same_intake_v04"]["market_used_for_fit"]=True
        with self.assertRaisesRegex(ValueError,"Untrusted earlier"):
            enrich(recorded,[bad],[])
        bad=copy.deepcopy(snap)
        bad["games"][0]["same_intake_v04"]["source_bundle_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"Untrusted earlier"):
            enrich(recorded,[bad],[])
        bad=copy.deepcopy(snap)
        bad["games"][0]["same_intake_v04"]["source_observed_at_utc"]="2026-11-03T12:00:00Z"
        with self.assertRaisesRegex(ValueError,"Untrusted earlier"):
            enrich(recorded,[bad],[])


if __name__=="__main__":
    unittest.main()

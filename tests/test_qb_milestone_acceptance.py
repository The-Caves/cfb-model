import unittest
from scripts.qb_milestone_acceptance import assess

def inputs(verified=0,slots=4,missing=2,failed=0):
    news={"betting_status":"PASS_UNVALIDATED","manifest":{
        "status":"OFFICIAL_NEWS_REVIEW_ONLY","feeds_configured":7,
        "feeds_read":2,"feeds_failed":failed,
        "unconfigured_upcoming_team_slots":missing,"candidate_count":0}}
    queue={"betting_status":"PASS_UNVALIDATED","summary":{"team_game_slots":slots}}
    coverage={"status":"STEP3H_PERSONNEL_COVERAGE_RESEARCH_ONLY",
              "summary":{"team_slots":slots,"reviewed_qb_slots":verified,
                         "qb_coverage_fraction":verified/slots if slots else None}}
    return news,queue,coverage

class AcceptanceTests(unittest.TestCase):
    def test_zero_coverage_fails(self):
        result=assess(*inputs())
        self.assertFalse(result["ready_for_milestone_2"])
        self.assertEqual(result["observed"]["reviewed_qb_slots"],0)
    def test_complete_verified_slate_passes(self):
        self.assertTrue(assess(*inputs(4,4,0))["ready_for_milestone_2"])
    def test_feed_failure_blocks_completion(self):
        self.assertFalse(assess(*inputs(4,4,0,1))["ready_for_milestone_2"])
    def test_mismatched_denominators_rejected(self):
        news,queue,coverage=inputs()
        queue["summary"]["team_game_slots"]=3
        with self.assertRaises(ValueError):assess(news,queue,coverage)

if __name__=="__main__":unittest.main()

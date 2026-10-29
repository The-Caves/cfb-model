import unittest,os
from unittest.mock import patch
from scripts.candidate_shadow_archive import validate,archive
from scripts.qb_conditional_forecast import STATUS as QB
from scripts.venue_travel_forecast import STATUS as VENUE
def basic(kind="qb"):
    status=QB if kind=="qb" else VENUE
    x={"status":status,"season":2026,
       "observed_at_utc":"2026-10-29T12:00:00Z",
       "baseline_forecast_sha256":"a"*64,
       "model_promoted":False,"safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
       "games":[{"game_id":"123","home":"A","away":"B",
            "kickoff_utc":"2026-10-31T18:00:00Z",
            "baseline_row_sha256":"b"*64}]}
    if kind=="qb":
        x["baseline_forecast_run_id"]="991"
        x["historical_pbp_publication_authenticated"]=False
        x["games"][0]["candidate"]={"model_promoted":False,"betting_status":"PASS_UNVALIDATED"}
    else:
        x["baseline_run_id"]="991"
        x["historical_publication_authenticated"]=False
        x["games"][0]["small_travel_adjustment_points"]=1.
    return x
class ShadowArchiveTests(unittest.TestCase):
    def test_both_kinds_provenance(self):
        for k in ("qb","venue"):
            self.assertEqual(validate(basic(k),k)[0],"991")
    def test_postkickoff_and_duplicate_rejected(self):
        x=basic()
        x["games"][0]["kickoff_utc"]="2026-10-29T11:00:00Z"
        with self.assertRaisesRegex(ValueError,"Postkickoff"):
            validate(x,"qb")
        x=basic();x["games"].append(dict(x["games"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate"):
            validate(x,"qb")
    def test_excessive_travel_rejected(self):
        x=basic("venue");x["games"][0]["small_travel_adjustment_points"]=9
        with self.assertRaisesRegex(ValueError,"Excessive"):
            validate(x,"venue")
    def test_foreign_github_run_cannot_publish(self):
        with patch.dict(os.environ,{"GITHUB_RUN_ID":"992"}):
            with self.assertRaisesRegex(ValueError,"current GitHub run"):
                archive(basic(),"qb")
if __name__=="__main__":unittest.main()

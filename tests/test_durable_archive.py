"""S3 tests use only a mocked client; never send AWS requests from CI."""
import datetime as dt,json,tempfile,unittest
from pathlib import Path
from io import BytesIO
from scripts.weekly_profiles import canonical
from scripts.durable_archive import archive_file,save_receipt,sha,STATUS
UTC=dt.timezone.utc
NOW=dt.datetime(2026,10,21,23,20,tzinfo=UTC)
RUN="14712"
BUCKET="private-locked-cfb-archive"
def sample():
    tp={"home":{"team":"Texas Longhorns"},"away":{"team":"Oklahoma Sooners"}}
    return {
        "status":"OBSERVED_PREGAME_RESEARCH_CAPTURE",
        "run_id":RUN,"captured_at_utc":"2026-10-21T23:10:00Z",
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED",
        "historical_publication_times_verified":False,
        "sources":{"score_retrieved_utc":"2026-10-21T23:00:00Z",
                   "advanced_retrieved_utc":"2026-10-21T23:01:00Z",
                   "context_captured_utc":"2026-10-21T23:06:00Z",
                   "context_asof_utc":"2026-10-21T23:05:00Z"},
        "source_file_sha256":{i:"a"*64 for i in
            ("score_csv","advanced_csv","advanced_manifest",
             "score_manifest","context_json","registry_csv")},
        "games":[{"game_id":"future","kickoff_utc":"2026-10-24T20:00:00Z",
                  "profile_source":"RETROSPECTIVE_RECONSTRUCTION_UNVERIFIED",
                  "team_profiles":tp,"team_profiles_sha256":sha(canonical(tp))}]
    }
class FakeS3:
    def __init__(self):
        self.calls=[];self.version=True;self.lock=True;self.private=True
        self.corrupt=False;self.short=False;self.encrypted=True;self.no_version=False
    def get_bucket_versioning(self,**kw):
        self.calls.append("version")
        return {"Status":"Enabled" if self.version else "Suspended"}
    def get_object_lock_configuration(self,**kw):
        self.calls.append("lock")
        return {"ObjectLockConfiguration":{"ObjectLockEnabled":
                "Enabled" if self.lock else "Disabled"}}
    def get_public_access_block(self,**kw):
        self.calls.append("public")
        return {"PublicAccessBlockConfiguration":{
          k:self.private for k in
          ("BlockPublicAcls","IgnorePublicAcls","BlockPublicPolicy","RestrictPublicBuckets")}}
    def put_object(self,**kw):
        self.calls.append("put")
        if kw["IfNoneMatch"]!="*" or kw["ObjectLockMode"]!="COMPLIANCE":
            raise ValueError("Unsafe upload")
        self.content=kw["Body"];self.req=kw
        return {"VersionId":None if self.no_version else "v1"}
    def head_object(self,**kw):
        self.calls.append("head")
        return {"VersionId":"v1","ObjectLockMode":"COMPLIANCE",
            "ObjectLockRetainUntilDate":self.req["ObjectLockRetainUntilDate"]-(
                 dt.timedelta(seconds=1) if self.short else dt.timedelta(0)),
            "ServerSideEncryption":"AES256" if self.encrypted else None,
            "ContentLength":len(self.content),"Metadata":self.req["Metadata"]}
    def get_object(self,**kw):
        self.calls.append("get")
        return {"Body":BytesIO(self.content+b"x" if self.corrupt else self.content)}
class Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/("capture-"+RUN+".json")
        self.path.write_bytes(canonical(sample()))
        self.s3=FakeS3()
    def go(self,**kw):
        return archive_file(self.path,self.s3,BUCKET,"us-east-1",RUN,
                            now=NOW,**kw)
    def test_happy_path_and_receipt(self):
        receipt=self.go()
        self.assertEqual(self.s3.calls,
                         ["version","lock","public","put","head","get"])
        self.assertEqual(receipt["status"],STATUS)
        self.assertTrue(receipt["remote_compliance_retention_verified"])
        self.assertFalse(receipt["historical_publication_times_verified"])
        self.assertEqual(receipt["betting_status"],"PASS_UNVALIDATED")
        target=self.path.parent/"receipt.json"
        save_receipt(receipt,target)
        with self.assertRaises(FileExistsError):save_receipt(receipt,target)
        written=target.read_text()
        self.assertNotIn(BUCKET,written)
        self.assertNotIn("version_id",written)
        self.assertNotIn("key",written)
        self.assertIn(receipt["sha256"],written)
    def test_versioning_disabled_fails_closed(self):
        self.s3.version=False
        with self.assertRaisesRegex(ValueError,"versioning"):self.go()
        self.assertNotIn("put",self.s3.calls)
    def test_lock_disabled_fails_closed(self):
        self.s3.lock=False
        with self.assertRaisesRegex(ValueError,"Object Lock"):self.go()
        self.assertNotIn("put",self.s3.calls)
    def test_public_access_not_fully_blocked(self):
        self.s3.private=False
        with self.assertRaisesRegex(ValueError,"public access"):self.go()
        self.assertNotIn("put",self.s3.calls)
    def test_missing_version_id_does_not_issue_receipt(self):
        self.s3.no_version=True
        with self.assertRaisesRegex(ValueError,"immutable object version"):self.go()
    def test_retention_shortening_detected(self):
        self.s3.short=True
        with self.assertRaisesRegex(ValueError,"retention less"):self.go()
    def test_readback_corruption_detected(self):
        self.s3.corrupt=True
        with self.assertRaisesRegex(ValueError,"readback failed"):self.go()
    def test_encryption_missing_is_rejected(self):
        self.s3.encrypted=False
        with self.assertRaisesRegex(ValueError,"encryption"):self.go()
    def test_less_than_365_days_rejected(self):
        with self.assertRaisesRegex(ValueError,"365 days"):self.go(days=30)
        self.assertNotIn("put",self.s3.calls)
    def test_wrong_run_id_refused_before_network(self):
        with self.assertRaisesRegex(ValueError,"workflow run ID"):
            archive_file(self.path,self.s3,BUCKET,"us-east-1","999",now=NOW)
        self.assertEqual(self.s3.calls,[])
    def test_later_capture_than_now_refused(self):
        with self.assertRaisesRegex(ValueError,"Archive time precedes"):
            archive_file(self.path,self.s3,BUCKET,"us-east-1",RUN,
                         now="2026-10-21T23:09:00Z")
        self.assertNotIn("put",self.s3.calls)
    def test_mutated_team_profile_fails_before_network(self):
        record=sample()
        record["games"][0]["team_profiles"]["home"]["team"]="Fake"
        self.path.write_bytes(canonical(record))
        with self.assertRaisesRegex(ValueError,"checksum mismatch"):self.go()
        self.assertEqual(self.s3.calls,[])
    def test_retroactive_status_fails_before_network(self):
        record=sample();record["historical_publication_times_verified"]=True
        self.path.write_bytes(canonical(record))
        with self.assertRaisesRegex(ValueError,"Invalid research"):self.go()
        self.assertEqual(self.s3.calls,[])
    def test_capture_from_after_game_rejected(self):
        record=sample();record["games"][0]["kickoff_utc"]="2026-10-21T23:00:00Z"
        self.path.write_bytes(canonical(record))
        with self.assertRaisesRegex(ValueError,"kickoff"):self.go()
        self.assertEqual(self.s3.calls,[])
    def test_noncanonical_bytes_rejected(self):
        self.path.write_text(json.dumps(sample(),indent=2))
        with self.assertRaisesRegex(ValueError,"Noncanonical"):self.go()
        self.assertEqual(self.s3.calls,[])
if __name__=="__main__":
    unittest.main()

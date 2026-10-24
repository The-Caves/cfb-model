import unittest
from scripts.official_school_source_audit import merge

class SchoolSourceAuditTests(unittest.TestCase):
    def test_reachability_does_not_promote_verification(self):
        registry={"expected":2,"schools":[
            {"team":"A","official_athletics_homepage":"https://a.edu","homepage_verified":False},
            {"team":"B","official_athletics_homepage":"https://b.edu","homepage_verified":False}]}
        connectivity={"checked_at_utc":"2026-10-24T00:00:00Z",
            "athletics_homepages":[
                {"team":"A","url":"https://a.edu","reachable":True},
                {"team":"B","url":"https://b.edu","reachable":False}]}
        result=merge(registry,connectivity)
        self.assertEqual(result["homepage_reachable_count"],1)
        self.assertEqual(result["homepage_unreachable_or_blocked_count"],1)
        self.assertTrue(all(not x["homepage_verified"] for x in result["schools"]))
        self.assertTrue(all(not x["personnel_evidence_verified"] for x in result["schools"]))

    def test_missing_probe_fails(self):
        with self.assertRaises(ValueError):
            merge({"expected":1,"schools":[{"team":"A","official_athletics_homepage":"https://a.edu"}]},
                  {"athletics_homepages":[]})
if __name__=="__main__":unittest.main()

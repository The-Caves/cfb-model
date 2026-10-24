import unittest
from scripts.official_personnel_source_coverage import evaluate

class PersonnelSourceCoverageTests(unittest.TestCase):
    def test_canonical_coverage_and_missing_vs_unpublished(self):
        schools=[]
        for n in range(138):
            schools.append({"team":"Team "+str(n),"crawl_status":"AUDITED",
                            "football_page":"https://example.edu/football",
                            "game_notes":[{"url":"https://example.edu/n.pdf",
                                           "game_specific_evidence_verified":False}] if n==0 else [],
                            "depth_chart":[],"injury_report":[]})
        result=evaluate({"expected_teams":138,"schools":schools})
        self.assertEqual(result["source_type_counts"]["game_notes"]["CANDIDATES_FOUND_REVIEW_REQUIRED"],1)
        self.assertEqual(result["source_type_counts"]["game_notes"]["NO_CANDIDATE_LOCATED"],137)
        self.assertTrue(result["missing_source_not_equivalent_to_unpublished"])
        self.assertEqual(result["personnel_verified_count"],0)
    def test_refuse_unreviewed_personnel_claim(self):
        rows=[{"team":str(i),"crawl_status":"AUDITED","game_notes":[{"url":"https://example.edu/n.pdf",
             "game_specific_evidence_verified":i==0}],"depth_chart":[],"injury_report":[]} for i in range(138)]
        with self.assertRaises(ValueError):
            evaluate({"expected_teams":138,"schools":rows})
if __name__=="__main__":unittest.main()

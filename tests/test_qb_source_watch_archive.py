import copy,datetime as dt,hashlib,unittest
from scripts.qb_source_watch_archive import plan,STATUS
NOW=dt.datetime(2026,10,26,23,30,tzinfo=dt.timezone.utc)
SHA="a"*64
def pair():
    base={"season":2026,"betting_status":"PASS_UNVALIDATED",
          "captured_at_utc":"2026-10-26T23:20:00+00:00","model_predictions_modified":False}
    row={"game_id":"1","team":"School","opponent":"Opponent",
         "kickoff_utc":"2026-10-27T23:00:00+00:00",
         "captured_at_utc":"2026-10-26T23:20:00+00:00",
         "source_url":"https://officialschool.edu/gameweek",
         "status":"REVIEW_ONLY_NOT_CONFIRMED","confirmed_starter":False,
         "content_sha256":SHA}
    html={**base,"status":"OFFICIAL_GAMEWEEK_QB_LANGUAGE_REVIEW_ONLY",
          "confirmed_starters_added":0,"summary":{"full_articles_fetched":0},
          "entries":[{**row,"source_read_status":"FETCHED_METADATA_ONLY"}]}
    pdf={**base,"status":"OFFICIAL_QB_NOTES_DOCUMENT_REVIEW_ONLY",
         "official_starting_qb_confirmations":0,
         "summary":{"direct_pdf_extracted":1},
         "entries":[{**row,"source_url":"https://officialschool.edu/notes.pdf","source_read_status":"DIRECT_PDF_TEXT"}]}
    return html,pdf
class SourceArchiveTests(unittest.TestCase):
    def test_preserves_immutable_screening_without_starter_claim(self):
        report=plan(*pair(),NOW,123456)
        self.assertEqual(report["status"],STATUS)
        self.assertEqual(report["summary"]["full_text_source_rows"],1)
        self.assertEqual(report["official_starting_qb_confirmations"],0)
        self.assertEqual(report["run_id"],"123456")
        self.assertEqual(len(report["pdf_review_sha256"]),64)
    def test_cannot_archive_future_or_stale_source(self):
        html,pdf=pair();html["captured_at_utc"]="2026-10-26T23:50:00Z"
        with self.assertRaises(ValueError):plan(html,pdf,NOW,1)
        html,pdf=pair();html["captured_at_utc"]="2026-10-25T20:20:00Z"
        with self.assertRaises(ValueError):plan(html,pdf,NOW,1)
    def test_cannot_launder_starting_qb_from_scrape(self):
        html,pdf=pair();pdf["official_starting_qb_confirmations"]=1
        with self.assertRaises(ValueError):plan(html,pdf,NOW,1)
        html,pdf=pair();html["entries"][0]["confirmed_starter"]=True
        with self.assertRaises(ValueError):plan(html,pdf,NOW,1)
    def test_cannot_archive_postkickoff_source(self):
        html,pdf=pair();pdf["entries"][0]["kickoff_utc"]="2026-10-26T22:00:00Z"
        with self.assertRaises(ValueError):plan(html,pdf,NOW,1)
    def test_rejects_bad_source_hash_duplicate_or_retiming(self):
        html,pdf=pair();html["entries"][0]["content_sha256"]="notahash"
        with self.assertRaises(ValueError):plan(html,pdf,NOW,1)
        html,pdf=pair();pdf["entries"].append(copy.deepcopy(pdf["entries"][0]))
        with self.assertRaises(ValueError):plan(html,pdf,NOW,1)
        html,pdf=pair();html["entries"][0]["captured_at_utc"]="2026-10-25T10:00:00Z"
        with self.assertRaises(ValueError):plan(html,pdf,NOW,1)
if __name__=="__main__":unittest.main()

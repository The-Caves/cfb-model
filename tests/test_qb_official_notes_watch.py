import datetime as dt,unittest
from scripts.qb_official_notes_watch import observe,trusted_notes,verified_pdf_leads,STATUS
NOW=dt.datetime(2026,10,26,21,tzinfo=dt.timezone.utc)
def conf(link="https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/bluehens.com/documents/2026/10/26/notes.pdf"):
    return {"status":"REVIEWED_OFFICIAL_GAMEWEEK_LINKS_NOT_QB_STARTERS","season":2026,
            "entries":[{"game_id":"401","team":"Delaware Blue Hens","opponent":"WKU",
                        "kickoff_utc":"2026-10-27T23:00:00Z",
                        "preview_url":"https://bluehens.com/news/2026/10/26/preview",
                        "game_notes_url":link,"starter_confirmed":False,
                        "evidence_type":"OFFICIAL_GAMEWEEK_PREVIEW_NO_QB1_CLAIM"}]}
class NotesTests(unittest.TestCase):
    def test_direct_pdf_extract_captures_candidates_not_confirmation(self):
        content=("Team notes QB Nick Minicucci will start at quarterback on Tuesday. "
                 "The backup was questionable but these are game notes, not a reviewed official declaration. ")*3
        result=observe(conf(),NOW,fetcher=lambda u:(b"%PDF-1.7 safe payload","application/pdf"),extractor=lambda raw:(content,77))
        self.assertEqual(result["status"],STATUS)
        self.assertEqual(result["summary"]["direct_pdf_extracted"],1)
        self.assertTrue(result["entries"][0]["possible_qb1_language"])
        self.assertFalse(result["entries"][0]["confirmed_starter"])
        self.assertEqual(result["official_starting_qb_confirmations"],0)
    def test_landing_page_not_mistaken_for_pdf(self):
        x=observe(conf("https://bluehens.com/documents/2026/10/26/notes.pdf"),NOW,
                  fetcher=lambda u:(b"<html>download PDF</html>","text/html"),
                  extractor=lambda raw:self.fail("Do not parse HTML as PDF"))
        self.assertEqual(x["summary"]["pdf_landing_pages"],1)
        self.assertEqual(x["summary"]["keyword_candidates"],0)
    def test_html_landing_pdf_leads_must_match_document_and_publisher(self):
        landing="https://bluehens.com/documents/2026/10/26/notes.pdf"
        page=b'<html><a href="https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/bluehens.com/documents/2026/10/26/notes.pdf?download=1">Download</a><a href="https://attacker.test/notes.pdf">Evil</a><a href="/documents/2026/10/26/other.pdf">Wrong notes</a></html>'
        c=verified_pdf_leads(page,landing,"https://bluehens.com/news/2026/10/26/preview")
        self.assertEqual(len(c),1)
        self.assertIn("sidearm.nextgen.sites/bluehens.com/",c[0])
        self.assertEqual(verified_pdf_leads(b'<html><a href="http://attacker.test/notes.pdf">bad</a></html>',landing,"https://bluehens.com/news/a"),[])
    def test_official_single_matching_pdf_is_followed_automatically(self):
        landing="https://gobearkats.com/documents/2026/10/26/Game_8_at_MOST.pdf"
        full="https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/gobearkats.com/documents/2026/10/26/Game_8_at_MOST.pdf?timestamp=20261026090000"
        config={"status":"REVIEWED_OFFICIAL_GAMEWEEK_LINKS_NOT_QB_STARTERS","season":2026,
            "entries":[{"game_id":"1","team":"Sam Houston Bearkats",
            "opponent":"Missouri State Bears","kickoff_utc":"2026-10-28T00:00:00Z",
            "preview_url":"https://gobearkats.com/news/2026/10/25/football-game-8-preview-at-missouri-state",
            "game_notes_url":landing,"starter_confirmed":False,
            "evidence_type":"OFFICIAL_GAMEWEEK_PREVIEW_NO_QB1_CLAIM"}]}
        calls=[]
        def fake(u):
            calls.append(u)
            if u==landing:
                return ('<a href="'+full+'">Download game 8 notes</a>').encode(),"text/html"
            if u==full:
                return b"%PDF-1.7 official synthetic PDF bytes","application/pdf"
            raise AssertionError("Unexpected URL")
        result=observe(config,NOW,fetcher=fake,extractor=lambda raw:("Football game notes "+"sample "*40,12))
        self.assertEqual(calls,[landing,full])
        self.assertEqual(result["summary"]["direct_pdf_extracted"],1)
        self.assertEqual(result["entries"][0]["resolved_direct_pdf_url"],full)
        self.assertEqual(result["official_starting_qb_confirmations"],0)
    def test_fau_game_8_landing_only_resolves_identical_official_document(self):
        landing="https://fausports.com/documents/2026/10/26/2026_Game_Notes__8_remediated.pdf"
        good="https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/fausports.com/documents/2026/10/26/2026_Game_Notes__8_remediated.pdf?timestamp=20261026010000"
        previous="https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/fausports.com/documents/2026/10/20/2026_Game_Notes__7_remediated.pdf"
        html=('<html><a href="'+previous+'">Previous-game notes</a>'
              '<a href="'+good+'">Game 8 PDF</a>'
              '<a href="https://attacker.test/2026_Game_Notes__8_remediated.pdf">Unofficial</a></html>').encode()
        self.assertEqual(verified_pdf_leads(html,landing,
                         "https://fausports.com/news/2026/10/26/football-game-notes-8"),[good])

    def test_changed_pdf_preserves_snapshot_scope(self):
        first=observe(conf(),NOW,fetcher=lambda u:(b"%PDF-1.7 first","application/pdf"),
                      extractor=lambda raw:("Football content with QB and opponent "+"x"*110,4))
        same=observe(conf(),NOW,fetcher=lambda u:(b"%PDF-1.7 first","application/pdf"),
                     extractor=lambda raw:("Football content with QB and opponent "+"x"*110,4),previous=first)
        changed=observe(conf(),NOW,fetcher=lambda u:(b"%PDF-1.7 second","application/pdf"),
                        extractor=lambda raw:("Football content with QB and opponent "+"x"*110,4),previous=first)
        self.assertEqual(same["entries"][0]["source_change"],"UNCHANGED")
        self.assertEqual(changed["entries"][0]["source_change"],"CHANGED_REVIEW_REQUIRED")
    def test_host_restriction_and_future_exclusion(self):
        self.assertFalse(trusted_notes("https://fake.edu/qb.pdf","https://bluehens.com/news/a"))
        with self.assertRaises(ValueError):observe(conf("https://fake.edu/qb.pdf"),NOW)
        x=observe(conf(),NOW+dt.timedelta(days=4),fetcher=lambda _:self.fail("Past-game access"))
        self.assertEqual(len(x["entries"]),0)
    def test_malformed_pdf_fails_closed(self):
        result=observe(conf(),NOW,fetcher=lambda u:(b"%PDF-1.7 bad","application/pdf"),
                       extractor=lambda raw:(_ for _ in ()).throw(ValueError("corrupt")))
        self.assertEqual(result["summary"]["unreadable"],1)
        self.assertEqual(result["official_starting_qb_confirmations"],0)
if __name__=="__main__":unittest.main()

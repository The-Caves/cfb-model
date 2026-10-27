import datetime as dt,unittest
from scripts.qb_media_notes_index_watch import observe,extract_links
NOW=dt.datetime(2026,10,26,22,tzinfo=dt.timezone.utc)
CFG={"status":"REVIEWED_OFFICIAL_FOOTBALL_MEDIA_INDEX_PILOT_2026","season":2026,
 "entries":[{"game_id":"1","team":"North Texas Mean Green","opponent":"Florida Atlantic Owls",
  "kickoff_utc":"2026-10-29T23:30:00Z","game_number":8,
  "target_game_date_label":"Oct. 29","opponent_short":"Florida Atlantic",
  "owner_label":"UNT",
  "index_url":"https://meangreensports.com/sports/2026/9/2/unt-media-center",
  "preview_url":"https://meangreensports.com/news/2026/10/26/football-unt-hosting-fau-on-espn-in-national-spotlight"}]}
prefix="<html><p>Game 7</p><p>Oct. 24 at Navy</p><a href='/documents/2026/10/23/old-notes.pdf'>UNT Game Notes</a>"
section="<p>Game 8</p><p>Oct. 29</p><p>vs. Florida Atlantic</p>"
link="<a href='/documents/2026/10/29/unt-vs-fau-notes.pdf'>UNT Game Notes</a>"
tail="<p>Game 9</p><p>Nov. 7 vs. Rice</p><a href='/documents/2026/11/6/old.pdf'>UNT Game Notes</a></html>"
class Tests(unittest.TestCase):
 def test_only_exact_game_8_link_emitted(self):
  x=observe(CFG,NOW,reader=lambda _:prefix+section+link+tail)
  self.assertEqual(x["summary"]["game_note_candidate_links"],1)
  self.assertIn("2026/10/29/unt-vs-fau-notes.pdf",x["entries"][0]["links"][0])
  self.assertEqual(x["starter_confirmations_added"],0)
 def test_published_label_without_href_is_not_a_source(self):
  x=observe(CFG,NOW,reader=lambda _:prefix+section+"<span>UNT Game Notes</span>"+tail)
  self.assertEqual(x["summary"]["game_note_candidate_links"],0)
  self.assertEqual(x["entries"][0]["link_match_status"],"GAME_SECTION_PRESENT_NOTES_NOT_PUBLISHED")
 def test_prior_game_note_never_recycled(self):
  html=prefix+section+tail
  x=observe(CFG,NOW,reader=lambda _:html)
  self.assertEqual(x["summary"]["game_note_candidate_links"],0)
 def test_mismatched_school_or_late_capture_rejected(self):
  c={"status":CFG["status"],"season":2026,"entries":[dict(CFG["entries"][0])]}
  c["entries"][0]["preview_url"]="https://attacker.test/story"
  with self.assertRaises(ValueError):observe(c,NOW,reader=lambda _:prefix+section+link+tail)
  x=observe(CFG,NOW+dt.timedelta(days=5),reader=lambda _:self.fail("No post-game fetch"))
  self.assertEqual(x["summary"]["indexes_checked"],0)
 def test_no_current_game_date_or_opponent_is_not_valid(self):
  x=observe(CFG,NOW,reader=lambda _:prefix+"<p>Game 8</p><p>Oct. 28 at Florida Atlantic</p>"+link+tail)
  self.assertEqual(x["summary"]["game_note_candidate_links"],0)
if __name__=="__main__":unittest.main()

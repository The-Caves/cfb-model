import os, sqlite3, stat, tempfile, unittest
from pathlib import Path
from scripts.market_quotes import normalize
from scripts.market_vault import store,asof_quotes,audit,connect,safe_path,ROOT

KICK="2026-10-24T20:00:00Z"
def fixture(observed="2026-10-21T17:00:00Z",spread=-4.5):
    return [{"id":"example123","sport_key":"americanfootball_ncaaf",
      "commence_time":KICK,"home_team":"Home School","away_team":"Away School",
      "bookmakers":[{"key":"fanduel","last_update":observed,
       "markets":[{"key":"spreads","outcomes":[
         {"name":"Home School","point":spread,"price":-110},
         {"name":"Away School","point":-spread,"price":-110}]},
         {"key":"totals","outcomes":[
         {"name":"Over","point":49.5,"price":-112},
         {"name":"Under","point":49.5,"price":-108}]}]}]}]
def result(time="2026-10-21T17:00:00Z",spread=-4.5):
    return normalize(fixture(time,spread),time)

class VaultTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.db=Path(self.dir.name)/"private.sqlite3"
    def test_idempotent_private_save(self):
        bundle=result()
        first=store(self.db,bundle,{"x-requests-last":3,"x-requests-remaining":80})
        second=store(self.db,bundle)
        self.assertEqual(first["snapshots_added"],1)
        self.assertEqual(first["quotes_added"],4)
        self.assertEqual(second["status"],"DUPLICATE_SNAPSHOT")
        self.assertEqual(audit(self.db)["quotes"],4)
        self.assertEqual(stat.S_IMODE(self.db.stat().st_mode),0o600)
        with connect(self.db) as db:
            self.assertEqual(db.execute("SELECT credits_last FROM snapshots").fetchone()[0],3)
    def test_two_price_observations_are_immutable(self):
        store(self.db,result())
        store(self.db,result("2026-10-21T18:00:00Z",-6.5))
        early=asof_quotes(self.db,"example123","fanduel","SPREAD","HOME",
                          "2026-10-21T17:30:00Z")
        later=asof_quotes(self.db,"example123","fanduel","SPREAD","HOME",
                          "2026-10-21T18:30:00Z")
        self.assertEqual((early["line_points"],later["line_points"]),(-4.5,-6.5))
        self.assertFalse(later["price_executable_verified"])
        self.assertEqual(audit(self.db)["snapshots"],2)
    def test_stale_price_is_not_called_executable(self):
        store(self.db,result())
        stale=asof_quotes(self.db,"example123","fanduel","SPREAD","HOME",
                          "2026-10-22T17:01:00Z")
        self.assertEqual(stale["status"],"STALE_PRICE")
    def test_post_kickoff_asof_is_not_a_betting_price(self):
        store(self.db,result())
        price=asof_quotes(self.db,"example123","fanduel","SPREAD","HOME",
                          "2026-10-24T20:05:00Z")
        self.assertEqual(price["status"],"GAME_ALREADY_STARTED")
        self.assertNotIn("american_odds",price)
    def test_retrospectively_downloaded_historical_quote_not_live(self):
        p=normalize({"timestamp":"2026-10-21T17:00:00Z","data":fixture()},
                    "2026-10-26T12:00:00Z",historical=True)
        store(self.db,p)
        price=asof_quotes(self.db,"example123","fanduel","SPREAD","HOME",
                          "2026-10-21T17:30:00Z")
        self.assertEqual(price["status"],"HISTORICAL_RECONSTRUCTION_NOT_LIVE")
        self.assertFalse(price["price_executable_verified"])
    def test_future_quote_rejected_for_earlier_cutoff(self):
        store(self.db,result())
        q=asof_quotes(self.db,"example123","fanduel","SPREAD","HOME",
                      "2026-10-21T16:00:00Z")
        self.assertEqual(q["status"],"NO_OBSERVED_QUOTE")
    def test_no_update_or_delete_allowed(self):
        store(self.db,result())
        with connect(self.db) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM quotes")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE snapshots SET provider='x'")
        self.assertEqual(audit(self.db)["quotes"],4)
    def test_public_repo_path_refused(self):
        with self.assertRaises(ValueError):
            store(ROOT/"data"/"market_quotes.sqlite3",result())
    def test_nonprivate_directory_refused(self):
        public=Path(self.dir.name)/"public"
        public.mkdir(mode=0o755)
        with self.assertRaises(PermissionError):
            store(public/"market.sqlite3",result())
    def test_nonprivate_file_refused(self):
        self.db.write_bytes(b"")
        self.db.chmod(0o644)
        with self.assertRaises(PermissionError):
            store(self.db,result())
    def test_tampered_quote_checksum_rejected(self):
        p=result()
        p["quotes"][0]["snapshot_sha256"]="0"*64
        with self.assertRaises(ValueError):
            store(self.db,p)
        self.assertFalse(self.db.exists())
    def test_unsafe_clearance_rejected(self):
        p=result();p["safe_for_betting"]=True
        with self.assertRaises(ValueError):
            store(self.db,p)
    def test_historical_observation_is_separate_from_retrieval(self):
        p=normalize({"timestamp":"2026-10-21T17:00:00Z",
                     "data":fixture()},
                    "2026-10-26T12:00:00Z",historical=True)
        store(self.db,p)
        with connect(self.db) as db:
            observed,retrieved,kind=db.execute(
                "SELECT observed_at_utc,retrieved_at_utc,kind FROM snapshots"
            ).fetchone()
        self.assertEqual(observed,"2026-10-21T17:00:00+00:00")
        self.assertEqual(retrieved,"2026-10-26T12:00:00+00:00")
        self.assertEqual(kind,"HISTORICAL")
    def test_post_kickoff_quote_refused(self):
        p=result()
        for q in p["quotes"]:q["kickoff_utc"]="2026-10-20T20:00:00Z"
        with self.assertRaises(ValueError):
            store(self.db,p)
if __name__=="__main__":unittest.main()

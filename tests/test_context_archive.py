import datetime as dt,gzip,json,unittest
from unittest.mock import patch
from scripts.context_archive import pack,unpack,asof_id
class ArchiveTests(unittest.TestCase):
    def test_pack_is_roundtrip_and_reproducible(self):
        x={"asof_utc":"2026-10-24T17:00:00Z","games":[{"game_id":"1"}]}
        self.assertEqual(unpack(pack(x)),x)
        self.assertEqual(pack(x),pack(x))
        self.assertEqual(asof_id(x),"20261024T170000Z")
    def test_close_after_sources_keeps_only_true_pregame_records(self):
        from scripts.context_archive import close_snapshot
        snapshot={"asof_utc":"2026-10-24T19:58:00Z",
                  "games":[{"game_id":"1","kickoff_utc":"2026-10-24T20:00:00Z"},
                           {"game_id":"2","kickoff_utc":"2026-10-24T22:00:00Z"}]}
        result=close_snapshot(snapshot,"2026-10-24T20:01:00Z")
        self.assertEqual(result["excluded_game_kickoffs_during_collection"],1)
        self.assertEqual(result["games"][0]["game_id"],"2")
        self.assertEqual(result["collection_started_utc"],"2026-10-24T19:58:00Z")
        self.assertEqual(result["asof_utc"],"2026-10-24T20:01:00+00:00")
    def test_restore_empty_branch(self):
        from scripts.context_archive import restore
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.context_archive.branch_head",return_value=None):
                result=restore(tmp)
            self.assertFalse(result["prior_available"])
            from pathlib import Path
            self.assertEqual(json.loads((Path(tmp)/"previous.json").read_text()),None)
if __name__=="__main__":unittest.main()

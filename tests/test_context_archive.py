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
    def test_transient_github_get_disconnect_retries_without_retrying_writes(self):
        import http.client,io,os
        from unittest.mock import patch
        from scripts.context_archive import api
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self):return b'{"object":{"sha":"ok"}}'
        with patch.dict(os.environ,{"GITHUB_TOKEN":"dummy"}):
            with patch("scripts.context_archive.urllib.request.urlopen",
                       side_effect=[http.client.RemoteDisconnected("transient"),Reply()]) as fetch:
                with patch("scripts.context_archive.time.sleep") as sleep:
                    self.assertEqual(api("GET","/repos/example/test/git/refs"),{"object":{"sha":"ok"}})
                self.assertEqual(fetch.call_count,2)
                sleep.assert_called_once()
            with patch("scripts.context_archive.urllib.request.urlopen",
                       side_effect=http.client.RemoteDisconnected("transient")) as fetch:
                with self.assertRaisesRegex(RuntimeError,"temporary connection failure"):
                    api("POST","/repos/example/test/git/trees",{"tree":[]})
                self.assertEqual(fetch.call_count,1)

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

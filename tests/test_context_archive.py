import datetime as dt,gzip,json,unittest
from unittest.mock import patch
from scripts.context_archive import pack,unpack,asof_id
class ArchiveTests(unittest.TestCase):
    def test_pack_is_roundtrip_and_reproducible(self):
        x={"asof_utc":"2026-10-24T17:00:00Z","games":[{"game_id":"1"}]}
        self.assertEqual(unpack(pack(x)),x)
        self.assertEqual(pack(x),pack(x))
        self.assertEqual(asof_id(x),"20261024T170000Z")
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

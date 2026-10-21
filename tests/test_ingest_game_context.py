import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.ingest_game_context import WeatherProvider,run
class PipelineTests(unittest.TestCase):
    def test_geocode_provider_failure_explicit(self):
        p=WeatherProvider()
        with patch("scripts.ingest_game_context.request_json",side_effect=OSError("blocked")):
            out=p.geocode("Raleigh","NC","USA")
        self.assertIsNone(out)
        self.assertEqual(len(p.errors),1)
    def test_invalid_cached_data_is_failure_not_empty_success(self):
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp)/"raw";raw.mkdir()
            (raw/"2026-10-01.json").write_text("{garbled")
            out=run(raw,Path(temp)/"context",None,1,now="2026-10-21T12:00:00Z")
            self.assertEqual(out["status"],"CONTEXT_PIPELINE_FAILED")
            self.assertTrue((Path(temp)/"context"/"context_manifest.json").exists())
if __name__=="__main__":unittest.main()

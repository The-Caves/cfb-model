"""2026 postgame grading source reads use checked-out local archive, not API."""
import gzip
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.personnel_forecast_grade import _archived_bytes,read


class LocalSettlementArchiveTests(unittest.TestCase):
    def test_reads_exact_compressed_source_bytes_without_any_api_calls(self):
        with tempfile.TemporaryDirectory() as root:
            rel="research_2026/forecast_grades_index.json"
            target=Path(root)/rel
            target.parent.mkdir(parents=True)
            expected=b'{"status":"immutable-research-archive"}'
            target.write_bytes(expected)
            with patch("scripts.personnel_forecast_grade.store.get_blob_file",
                       side_effect=AssertionError("No GitHub GET permitted")):
                self.assertEqual(_archived_bytes(rel,root),expected)
                with self.assertRaises(ValueError):
                    read(root) # Does not have initialized required forecast index.

    def test_requires_exact_source_and_rejects_paths_outside_checkout(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("../outside","/etc/passwd",
                         "research_2026/../../etc/passwd",
                         ".git/config","state/latest.json.gz"):
                with self.subTest(path=name),self.assertRaises(ValueError):
                    _archived_bytes(name,root)
            with self.assertRaisesRegex(ValueError,"Missing immutable"):
                _archived_bytes("research_2026/outcomes/never-collected.json.gz",root)
            other=Path(root)/"other"
            other.write_text("outside")
            protected=Path(root)/"research_2026/unsafe.json.gz"
            protected.parent.mkdir(exist_ok=True)
            protected.symlink_to(other)
            # This symlink stays inside the root, so file read remains safe.
            self.assertEqual(_archived_bytes("research_2026/unsafe.json.gz",root),
                             b"outside")

    def test_default_api_behavior_is_retained_for_legacy_callers(self):
        with patch("scripts.personnel_forecast_grade.store.get_blob_file",
                   return_value=b"legacy") as mock:
            self.assertEqual(_archived_bytes("research_2026/test.json.gz"),b"legacy")
            mock.assert_called_once_with("research_2026/test.json.gz")

if __name__=="__main__":
    unittest.main()

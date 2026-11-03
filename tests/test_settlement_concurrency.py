"""Skipped push workflows must not starve the serial context-state writer queue."""
import re
import unittest
from pathlib import Path

WORKFLOW=Path(".github/workflows/cfb-outcome-settlement.yml")


class SettlementQueueTests(unittest.TestCase):
    def test_lock_is_job_scoped_below_real_settlement_event_gate(self):
        source=WORKFLOW.read_text(encoding="utf-8")
        pre,after=source.split("\njobs:\n",1)
        self.assertNotIn("\nconcurrency:",pre)
        self.assertIn("  settle:\n",after)
        gate="    if: github.event_name != 'push' || contains(github.event.head_commit.message, '[run-settle]')"
        self.assertIn(gate,after)
        self.assertRegex(after,r"(?m)^    concurrency:$")
        self.assertRegex(after,r"(?m)^      group: cfb-context-state$")
        self.assertRegex(after,r"(?m)^      cancel-in-progress: false$")
        self.assertLess(after.index(gate),after.index("    concurrency:"))
        self.assertLess(after.index("    concurrency:"),after.index("    runs-on:"))
        self.assertEqual(source.count("group: cfb-context-state"),1)

    def test_no_bypass_of_postgame_source_protection(self):
        source=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("qb_postgame_starter_archive",source)
        self.assertIn("qb_starter_supervised",source)
        self.assertIn("qb_gamebook_link_discovery",source)
        self.assertIn("--archive-root .context-state",source)


if __name__=="__main__":
    unittest.main()

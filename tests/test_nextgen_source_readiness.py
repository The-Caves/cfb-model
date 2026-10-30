import io
import unittest
import pyarrow as pa
import pyarrow.parquet as pq
from scripts.nextgen_source_readiness import ASSETS,audit_payload,audit,STATUS

def sample(name,missing=False):
    fields=sorted(ASSETS[name][1])
    if missing:fields=fields[1:]
    table=pa.table({field:["x"] for field in fields})
    buffer=io.BytesIO()
    pq.write_table(table,buffer)
    return buffer.getvalue()

class SourceAuditTests(unittest.TestCase):
    def test_detect_verified_schema_not_original_pregame_publication(self):
        for name in ASSETS:
            record=audit_payload(name,sample(name),"2026-10-30T21:00:00Z")
            self.assertEqual(record["status"],"OBSERVED_SCHEMA_READY")
            self.assertFalse(record["original_publication_time_authenticated"])
            self.assertFalse(record["official_player_status_evidence"])
            self.assertFalse(record["usage_is_actual_snap_share"])
            self.assertFalse(record["drive_scoring_attribution_verified"])
            self.assertEqual(len(record["sha256"]),64)

    def test_missing_season_columns_never_count_as_source_ready(self):
        r=audit_payload("offense_usage_2026",sample("offense_usage_2026",True),
                        "2026-10-30T21:00:00Z")
        self.assertEqual(r["status"],"SOURCE_MISSING_COLUMNS_OR_ROWS")
        self.assertTrue(r["missing_required_columns"])

    def test_partial_network_failure_remains_explicit(self):
        def fetch(uri):
            if "/espn_cfb_drives/" in uri:raise ConnectionError("unavailable")
            return sample(next(k for k,v in ASSETS.items() if uri.endswith(v[0])))
        report=audit("2026-10-30T21:00:00Z",fetch)
        self.assertEqual(report["status"],STATUS)
        self.assertEqual(report["datasets_checked"],5)
        self.assertEqual(report["datasets_schema_ready"],4)
        self.assertEqual(report["sources"]["drives_2026"]["status"],
                         "SOURCE_UNAVAILABLE_OR_UNAUDITED")
        self.assertEqual(report["game_predictions_generated"],0)
        self.assertFalse(report["model_promoted"])

if __name__=="__main__":
    unittest.main()

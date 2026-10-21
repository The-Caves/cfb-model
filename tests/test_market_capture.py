import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.market_capture import capture
from scripts.market_vault import audit

DATA=[{"id":"provider-event-1","sport_key":"americanfootball_ncaaf",
       "commence_time":"2026-10-24T19:00:00Z",
       "home_team":"Example Home","away_team":"Example Away",
       "bookmakers":[{"key":"fanduel","last_update":"2026-10-21T16:55:00Z",
         "markets":[{"key":"spreads","outcomes":[
           {"name":"Example Home","point":-5.5,"price":-110},
           {"name":"Example Away","point":5.5,"price":-110}]}]}]}]
class ManualCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault=Path(self.tmp.name)/"vault.sqlite3"
        self.fixture=Path(self.tmp.name)/"offline_sample.json"
        self.fixture.write_text(json.dumps(DATA))
    def test_offline_fixture_saves_privately_without_network(self):
        def forbidden(*args,**kwargs):raise AssertionError("network not authorized")
        r=capture(vault_path=self.vault,fixture_path=self.fixture,
                  retrieved_at_utc="2026-10-21T17:00:00Z",fetcher=forbidden)
        self.assertEqual(r["quotes_added"],2)
        self.assertTrue(self.vault.exists())
        self.assertEqual(audit(self.vault)["snapshots"],1)
        self.assertNotIn("-110",json.dumps(r))
    def test_network_requires_explicit_consent(self):
        with self.assertRaisesRegex(ValueError,"disabled"):
            capture(vault_path=self.vault)
        self.assertFalse(self.vault.exists())
    def test_no_key_never_calls_network(self):
        with patch.dict(os.environ,{"ODDS_API_KEY":"","GITHUB_ACTIONS":""},clear=False):
            with self.assertRaisesRegex(ValueError,"ODDS_API_KEY"):
                capture(vault_path=self.vault,execute_network=True)
        self.assertFalse(self.vault.exists())
    def test_paid_historical_requires_extra_ack(self):
        with patch.dict(os.environ,{"ODDS_API_KEY":"private_fake_token","GITHUB_ACTIONS":""},clear=False):
            with self.assertRaisesRegex(ValueError,"acknowledgement"):
                capture(vault_path=self.vault,execute_network=True,
                        historical_date="2026-10-20T12:00:00Z",
                        fetcher=lambda *a,**kw: (_ for _ in ()).throw(AssertionError("network called")))
    def test_live_request_credit_ceiling_blocks_before_network(self):
        with patch.dict(os.environ,{"ODDS_API_KEY":"private_fake_token","GITHUB_ACTIONS":""}):
            with self.assertRaisesRegex(ValueError,"credit ceiling"):
                capture(vault_path=self.vault,execute_network=True,
                        max_estimated_credits=2,
                        fetcher=lambda *a,**kw: (_ for _ in ()).throw(AssertionError("network called")))
        self.assertFalse(self.vault.exists())
    def test_historical_request_requires_explicit_credit_ceiling(self):
        with patch.dict(os.environ,{"ODDS_API_KEY":"private_fake_token","GITHUB_ACTIONS":""}):
            with self.assertRaisesRegex(ValueError,"credit ceiling"):
                capture(vault_path=self.vault,execute_network=True,
                        historical_date="2026-10-21T17:00:00Z",
                        acknowledge_paid_historical=True,
                        fetcher=lambda *a,**kw: (_ for _ in ()).throw(AssertionError("network called")))
        self.assertFalse(self.vault.exists())
    def test_historical_limit_may_be_raised_consciously_for_one_request(self):
        test_data=json.loads(json.dumps(DATA))
        test_data[0]["bookmakers"][0]["last_update"]="2026-10-21T16:55:00Z"
        called=[]
        def fake_fetch(key,books,when):
            called.append(when)
            return {"timestamp":"2026-10-21T17:00:00Z","data":test_data},{"x-requests-last":30}
        with patch.dict(os.environ,{"ODDS_API_KEY":"private_fake_token","GITHUB_ACTIONS":""}):
            report=capture(vault_path=self.vault,execute_network=True,
                  historical_date="2026-10-21T17:00:00Z",
                  acknowledge_paid_historical=True,max_estimated_credits=30,
                  retrieved_at_utc="2026-10-26T12:00:00Z",fetcher=fake_fetch)
        self.assertEqual(len(called),1)
        self.assertEqual(report["credits_last"],30)
        self.assertEqual(report["quotes_added"],2)
    def test_public_actions_cannot_capture_real_provider(self):
        with patch.dict(os.environ,{"GITHUB_ACTIONS":"true","ODDS_API_KEY":"private_fake_token"}):
            with self.assertRaisesRegex(ValueError,"public GitHub Actions"):
                capture(vault_path=self.vault,execute_network=True)
    def test_real_provider_response_stored_with_credit_metadata(self):
        calls=[]
        def mocked(key,books,when):
            calls.append((key,books,when))
            return DATA,{"x-requests-remaining":100,"x-requests-used":20,
                         "x-requests-last":3}
        with patch.dict(os.environ,{"ODDS_API_KEY":"private_fake_token","GITHUB_ACTIONS":""}):
            r=capture(vault_path=self.vault,execute_network=True,
                      retrieved_at_utc="2026-10-21T17:00:00Z",fetcher=mocked)
        self.assertEqual(len(calls),1)
        self.assertEqual(r["credits_last"],3)
        self.assertNotIn("private_fake_token",json.dumps(r))
    def test_live_and_fixture_mutually_exclusive(self):
        with self.assertRaisesRegex(ValueError,"OR"):
            capture(vault_path=self.vault,fixture_path=self.fixture,execute_network=True)
    def test_historical_fixture_retains_provider_snapshot_time(self):
        history={"timestamp":"2026-10-20T12:00:00Z","data":DATA}
        # Fixture last_update must precede the historical snapshot too.
        history["data"][0]["bookmakers"][0]["last_update"]="2026-10-20T11:55:00Z"
        self.fixture.write_text(json.dumps(history))
        r=capture(vault_path=self.vault,fixture_path=self.fixture,
                  historical_date="2026-10-20T12:00:00Z",
                  retrieved_at_utc="2026-10-21T17:00:00Z")
        self.assertEqual(r["observation_kind"],"HISTORICAL_PROVIDER_SNAPSHOT")
        self.assertEqual(audit(self.vault)["quotes"],2)
if __name__=="__main__":unittest.main()

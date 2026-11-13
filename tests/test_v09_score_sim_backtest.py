import gzip,json,tempfile,unittest
from pathlib import Path
from scripts.site_history import _digest,ARCHIVE_STATUS,FINAL_STATUS
from scripts.v09_score_sim_backtest import read_frozen,evaluate,simulate,v04

def fixture(root):
    root=Path(root);base=root/"research_2026/site_board_snapshots";base.mkdir(parents=True)
    index={"status":ARCHIVE_STATUS,"schema_version":1,"runs":[]}
    finals={"status":FINAL_STATUS,"season":2026,"safe_for_betting":False,"games":{}}
    for i,date in enumerate(("2026-10-30","2026-10-31","2026-11-03")):
        captured=date+"T09:00:00Z";kickoff=date+"T20:00:00Z"
        row={"game_id":str(i),"home":"H","away":"A","kickoff_utc":kickoff,
             "frozen_forecast_observed_utc":date+"T08:00:00Z",
             "home_bias_quarantined":True,"v04_research_not_promoted":True,
             "v04_direct_source_no_v03_total_reuse":True,
             "v04_direct_home_points":27.,"v04_direct_away_points":21.,
             "v04_direct_home_margin":6.,"v04_direct_total_points":48.,
             "market_home_spread":-3.5,"market_total":48.5,
             "market_provider":"Book","market_observed_utc":captured}
        snap={"status":ARCHIVE_STATUS,"betting_status":"PASS_UNVALIDATED",
              "capture_utc":captured,"dashboard_run_id":str(i+100),"rows":[row]}
        path=f"research_2026/site_board_snapshots/2026/10/run-{i+100}.json.gz"
        out=root/path;out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(gzip.compress(json.dumps(snap).encode()))
        index["runs"].append({"path":path,"capture_utc":captured,
                              "run_id":str(i+100),"sha256":_digest(snap)})
        finals["games"][str(i)]={"game_id":str(i),"home":"H","away":"A",
            "kickoff_utc":kickoff,"outcome_known_at_utc":date+"T23:00:00Z",
            "home_score":31,"away_score":20,"record_sha256":"a"*64}
    (base/"index.json").write_text(json.dumps(index))
    (root/"research_2026/outcome_index.json").write_text(json.dumps(finals))
    return base

def standalone(i,date):
    return {"game_id":str(i),"home":"H","away":"A",
            "kickoff_utc":date+"T20:00:00Z","forecast_utc":date+"T08:00:00Z",
            "capture_utc":date+"T09:00:00Z","home_points":27.,"away_points":21.,
            "final_home":31,"final_away":20,"result_known_utc":date+"T23:00:00Z",
            "market":{"home_spread":-3.5,"total":48.5,
                      "provider":"Book","observed_at_utc":date+"T09:00:00Z"}}

class SimulationTests(unittest.TestCase):
    def test_immutable_source_and_walkforward_results(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture(temp)
            rows,coverage=read_frozen(temp,"2026-11-13T12:00:00Z")
            self.assertEqual(len(rows),3)
            self.assertEqual(coverage["snapshot_runs_verified"],3)
            result=evaluate(rows,"2026-11-13T12:00:00Z",min_train=2,trials=150)
            self.assertEqual(result["eligible_games"],1)
            self.assertFalse(result["promotion_eligible"])
            self.assertEqual(result["metrics"]["v04"]["ats"]["wins"],1)
            self.assertEqual(result["metrics"]["v04"]["over_under"]["losses"],1)

    def test_tampered_pregame_digest_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            idx=fixture(temp)/"index.json"
            doc=json.loads(idx.read_text());doc["runs"][0]["sha256"]="f"*64
            idx.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,"digest"):
                read_frozen(temp,"2026-11-13T12:00:00Z")

    def test_future_source_and_same_game_rejected(self):
        target=standalone(3,"2026-11-07")
        prior=standalone(1,"2026-11-01")
        self.assertEqual(simulate(target,[prior],"uncorrected",120)["training_games"],1)
        future=dict(prior,result_known_utc="2026-11-09T00:00:00Z")
        with self.assertRaisesRegex(ValueError,"leakage"):
            simulate(target,[future],"global",120)
        with self.assertRaisesRegex(ValueError,"leakage"):
            simulate(target,[target],"team_form",120)

    def test_no_book_line_stays_missing_and_deterministic(self):
        target=standalone(3,"2026-11-07")
        prior=[standalone(1,"2026-11-01"),standalone(2,"2026-11-02")]
        self.assertEqual(simulate(target,prior,"team_form",150),
                         simulate(target,prior,"team_form",150))
        target["market"]={"home_spread":None,"total":None,
                          "provider":None,"observed_at_utc":None}
        row=simulate(target,prior,"global",110)
        self.assertIsNone(row["home_cover_probability"])
        self.assertIsNone(row["over_probability"])

    def test_untrusted_v04_missing_fields(self):
        self.assertFalse(v04({"home_bias_quarantined":True}))
        self.assertFalse(v04({"home_bias_quarantined":True,
                              "v04_research_not_promoted":True}))

    def test_single_prior_day_abstains(self):
        report=evaluate([standalone(3,"2026-11-07"),standalone(1,"2026-11-02"),
                         standalone(2,"2026-11-02")],"2026-11-13T12:00:00Z",
                        min_train=2,trials=100)
        self.assertEqual(report["eligible_games"],0)
        self.assertEqual(report["skipped"]["only_one_past_football_date"],1)

if __name__=="__main__":unittest.main()

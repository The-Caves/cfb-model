"""Step 3G observed prospective research forecasts; all games/lines are fixtures."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.personnel_forecast import (
    project, verify, _check_training, _fixed_rows, MODEL, MIN_TRAIN,
    MARKET_ABSENT, archive)
from scripts.personnel_features import join_capture, BASE_FIELDS
from scripts.weekly_profiles import canonical
from scripts.pregame_evidence import sha

NOW = "2026-10-22T10:05:00Z"
CAP = "2026-10-22T10:00:00Z"
KICK = "2026-10-24T20:00:00Z"


def capture():
    def profile(team,add):
        return {"team":team,"prior_game_ids":["1"],
                "recent_form":{
                    "points_for":30+add,"points_against":24,
                    "margin":5+add,"win":0.60,
                    "epa_off_adj":0.2+add/100,
                    "epa_def_adj":0.1,"epa_pass":0.3,
                    "epa_rush":0.12,"success":0.4,
                    "explosive_pass":0.1,"explosive_rush":0.08,
                    "pressure":0.03,"drive_yards":31.0,
                    "pass_rate":0.56,"epa_coverage":1.0}}
    teams={"home":profile("Home School",2),
           "away":profile("Away School",-2)}
    source={
        "status":"OBSERVED_PREGAME_RESEARCH_CAPTURE",
        "season":2026,"run_id":"123456",
        "captured_at_utc":CAP,
        "sources":{
            "score_retrieved_utc":"2026-10-22T09:45:00Z",
            "advanced_retrieved_utc":"2026-10-22T09:45:00Z",
            "context_asof_utc":"2026-10-22T09:45:00Z",
            "context_captured_utc":"2026-10-22T09:50:00Z"},
        "games":[{
            "game_id":"993","home":"Home School","away":"Away School",
            "kickoff_utc":KICK,"team_profiles":teams,
            "team_profiles_sha256":sha(canonical(teams)),
            "profile_source":"RETROSPECTIVE_RECONSTRUCTION_UNVERIFIED"}],
        "historical_publication_times_verified":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    return join_capture(source,[],[])


def training(n=90):
    rows=[]
    for i in range(n):
        row={
            "game_id":str(i+1000),
            "kickoff_utc":(dt.datetime(2026,8,29,tzinfo=dt.timezone.utc)
                + dt.timedelta(minutes=5*i)).isoformat(),
            "home_score":19+(i%9),"away_score":15+(i%7),
            "betting_status":"PASS_UNVALIDATED"}
        for j,f in enumerate(BASE_FIELDS):
            row[f]=(-1)**(i+j)*((i%13)+j)/100
        rows.append(row)
    return rows


def predicted(n=90):
    return project(capture(),training(n),NOW,{"source":"TEST_ONLY"})


class Forecast3GTests(unittest.TestCase):
    def test_actual_fitted_2026_model_projections(self):
        result=predicted()
        self.assertTrue(verify(result))
        self.assertEqual(result["model_training"]["model"],MODEL)
        self.assertEqual(result["model_training"]["actual_2026_training_games"],90)
        self.assertTrue(result["model_training"]["model_fitted"])
        self.assertIsNotNone(result["model_training"]["fitted_parameters_sha256"])
        row=result["games"][0]
        self.assertEqual(row["game_id"],"993")
        self.assertIsInstance(row["projection"]["predicted_home_margin"],float)
        self.assertIsInstance(row["projection"]["predicted_total_points"],float)
        self.assertIsInstance(row["projection"]["research_home_win_probability"],float)
        self.assertEqual(row["market"]["status"],MARKET_ABSENT)
        self.assertEqual(result["summary"]["market_prices_written_publicly"],0)
        self.assertFalse(result["model_promoted"])
        self.assertFalse(row["projection"]["probability_calibrated"])
        self.assertFalse(result["safe_for_betting"])

    def test_too_few_actual_completed_games_must_pass_not_guess(self):
        r=predicted(89)
        self.assertTrue(verify(r))
        self.assertIsNone(r["games"][0]["projection"]["predicted_home_margin"])
        self.assertEqual(r["games"][0]["projection"]["prediction_status"],
                         "PASS_INSUFFICIENT_TRAINING")
        self.assertEqual(r["summary"]["research_numeric_projections"],0)

    def test_training_game_after_capture_rejected(self):
        old=training()
        old[2]["kickoff_utc"]="2026-10-22T11:00:00Z"
        with self.assertRaisesRegex(ValueError,"future training"):
            project(capture(),old,NOW,{})

    def test_duplicate_training_game_rejected(self):
        old=training()
        old[1]["game_id"]=old[0]["game_id"]
        with self.assertRaisesRegex(ValueError,"Duplicated"):
            project(capture(),old,NOW,{})

    def test_delayed_forecast_rejected(self):
        with self.assertRaisesRegex(ValueError,"Stale"):
            project(capture(),training(),"2026-10-22T11:00:00Z",{})

    def test_future_capture_rejected(self):
        with self.assertRaisesRegex(ValueError,"Stale"):
            project(capture(),training(),"2026-10-22T09:59:00Z",{})

    def test_invalid_source_feature_hash_rejected(self):
        joined=capture()
        joined["games"][0]["features"]["score_margin_form"]=200
        with self.assertRaises(ValueError):
            project(joined,training(),NOW,{})

    def test_actual_model_probabilities_uncalibrated_and_bounds(self):
        r=predicted()
        p=r["games"][0]["projection"]
        self.assertLessEqual(abs(p["predicted_home_margin"]),55)
        self.assertLessEqual(p["predicted_total_points"],110)
        self.assertGreaterEqual(p["predicted_home_points"],0)
        self.assertGreaterEqual(p["predicted_away_points"],0)
        self.assertGreaterEqual(p["research_home_win_probability"],0)
        self.assertLessEqual(p["research_home_win_probability"],1)

    def test_record_mutation_cannot_pass_integrity(self):
        r=predicted()
        r["games"][0]["projection"]["predicted_total_points"]=999
        with self.assertRaises(ValueError):
            verify(r)

    def test_no_synthetic_spread_allowed_in_public_forecasts(self):
        r=predicted()
        row=r["games"][0]
        row["market"]["observed_spread"]=-7.5
        with self.assertRaisesRegex(ValueError,"market quotes"):
            verify(r)

    def test_probabilities_cannot_be_certified_as_calibrated(self):
        r=predicted()
        row=r["games"][0]
        row["projection"]["probability_calibrated"]=True
        with self.assertRaises(ValueError):
            verify(r)

    def test_postkickoff_predictions_are_not_emitted(self):
        joined=capture()
        joined["games"][0]["kickoff_utc"]="2026-10-22T10:01:00Z"
        with self.assertRaises(ValueError):
            project(joined,training(),NOW,{})

    def test_training_rows_are_research_only(self):
        trows=training()
        trows[0]["betting_status"]="VALIDATED"
        with self.assertRaises(ValueError):
            project(capture(),trows,NOW,{})

    def test_public_archive_requires_current_workflow_and_branch(self):
        r=predicted()
        with patch.dict("os.environ",{},clear=True):
            with patch("scripts.personnel_forecast.store.branch_head",return_value="abc"):
                with self.assertRaisesRegex(ValueError,"GitHub run"):
                    archive(r)

    def test_accepts_real_espn_scoreboard_manifest_format(self):
        # ingest_espn.py does not put a season key in its manifest.
        # Its fixed 2026 request start/date timezone identify this intake.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            score=root/"manifest.json"
            adv=root/"advanced.json"
            score.write_text(json.dumps({
                "status":"SUCCESS","failures":[],
                "requested_start":"2026-08-01",
                "requested_end":"2026-10-22",
                "scoreboard_date_timezone":"America/New_York",
                "retrieved_at_utc":"2026-10-22T09:45:00Z"}))
            adv.write_text(json.dumps({
                "status":"RESEARCH_PBP_IMPORTED_VERIFIED_SCORE_MATCH",
                "season":2026,
                "historical_pregame_availability_verified":False,
                "retrieved_at_utc":"2026-10-22T09:46:00Z"}))
            fake=[{
                "game_id":"1","kickoff_utc":"2026-10-01T20:00:00Z",
                "home_score":"21","away_score":"14",
                "date":"2026-10-01","home":"Home School",
                "away":"Away School","neutral":"False"}]
            with patch("scripts.personnel_forecast.load_inputs",
                       return_value=(fake,{},{})):
                games,advanced,_,_=_check_training(
                    "games.csv","advanced.csv",adv,score,
                    {"captured_at_utc":CAP})
            self.assertEqual(games[0]["game_id"],"1")

    def test_future_source_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            score=root/"manifest.json"
            adv=root/"advanced.json"
            score.write_text(json.dumps({
                "status":"SUCCESS","failures":[],
                "requested_start":"2026-08-01",
                "scoreboard_date_timezone":"America/New_York",
                "retrieved_at_utc":"2026-10-22T10:01:00Z"}))
            adv.write_text(json.dumps({
                "status":"RESEARCH_PBP_IMPORTED_VERIFIED_SCORE_MATCH",
                "season":2026,
                "historical_pregame_availability_verified":False,
                "retrieved_at_utc":"2026-10-22T09:46:00Z"}))
            with self.assertRaisesRegex(ValueError,"not available"):
                _check_training("games.csv","advanced.csv",adv,score,
                                {"captured_at_utc":CAP})

    def test_no_paid_market_call_or_actual_lines_in_artifact(self):
        r=predicted()
        payload=json.dumps(r)
        self.assertNotIn("ODDS_API_KEY",payload)
        self.assertNotIn('"observed_spread": -',payload)
        self.assertNotIn('"observed_total": 4',payload)
        self.assertEqual(r["market_data_privacy"],"PRIVATE_OPT_IN_EXISTING_VAULT_NOT_EXPORTED")

if __name__=="__main__":
    unittest.main()

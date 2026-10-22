"""Step 3G.1: grade actual frozen observations; synthetic inputs are TESTS only."""
import copy
import datetime as dt
import math
import unittest

from scripts.personnel_forecast import project, checksum, STATUS as FORECAST_STATUS
from scripts.personnel_forecast_grade import (
    STATUS, grade, empty_grade_index, verify_prior_grade, choose_for_final,
    FORECAST_PATH)
from scripts.personnel_features import join_capture
from scripts.personnel_results_archive import (
    ROOT, _empty_index, _observe_index, _link_observed_finals, _finals)
from scripts.weekly_profiles import canonical
from scripts.pregame_evidence import sha

KICK="2026-10-24T20:00:00Z"
CAP="2026-10-22T10:00:00Z"
OBS="2026-10-22T10:05:00Z"
KNOWN="2026-10-25T02:00:00Z"
AFTER="2026-10-25T02:03:00Z"
HOME="Alabama Crimson Tide"
AWAY="Texas Longhorns"


def profile(team,x):
    return {
        "team":team,"prior_game_ids":["g01"],
        "recent_form":{
            "points_for":29+x,"points_against":22,"margin":6+x,
            "win":0.7,"epa_off_adj":0.17+x/100,"epa_def_adj":0.1,
            "epa_pass":0.15,"epa_rush":0.12,"success":0.45,
            "explosive_pass":0.08,"explosive_rush":0.09,
            "pressure":0.07,"drive_yards":32.3,"pass_rate":0.56,
            "epa_coverage":0.9}}


def joined(run="12345", cap=CAP, kick=KICK):
    teams={"home":profile(HOME,2),"away":profile(AWAY,-2)}
    c={
        "status":"OBSERVED_PREGAME_RESEARCH_CAPTURE","season":2026,
        "run_id":str(run),"captured_at_utc":cap,
        "sources":{
            "score_retrieved_utc":"2026-10-22T09:30:00Z",
            "advanced_retrieved_utc":"2026-10-22T09:40:00Z",
            "context_asof_utc":"2026-10-22T09:45:00Z",
            "context_captured_utc":"2026-10-22T09:50:00Z"},
        "games":[{
            "game_id":"1001","home":HOME,"away":AWAY,
            "kickoff_utc":kick,"team_profiles":teams,
            "team_profiles_sha256":sha(canonical(teams)),
            "profile_source":"RETROSPECTIVE_RECONSTRUCTION_UNVERIFIED"}],
        "historical_publication_times_verified":False,
        "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    return c,join_capture(c,[],[])


def rows(n=90):
    result=[]
    for i in range(n):
        t=dt.datetime(2026,9,1,tzinfo=dt.timezone.utc)+dt.timedelta(minutes=6*i)
        data={"game_id":str(5000+i),"kickoff_utc":t.isoformat(),
              "home_score":(22+i%10),"away_score":(17+i%9),
              "betting_status":"PASS_UNVALIDATED"}
        from scripts.personnel_features import BASE_FIELDS
        for j,key in enumerate(BASE_FIELDS):
            data[key]=((i+7*j)%29-14)/10
        result.append(data)
    return result


def scenario(include_final=True, second=False):
    c,j=joined()
    forecast=project(j,rows(),OBS,{"training_source":"test_fixture_only"})
    path=ROOT+"/forecasts/2026/10/22/run-12345.json.gz"
    ref={
        "run_id":"12345","path":path,
        "forecast_observed_utc":forecast["forecast_observed_utc"],
        "forecast_sha256":checksum(forecast),
        "pregame_games":len(forecast["games"]),
        "eligible_24_to_72h_games":1,"actual_market_quotes":0}
    index={"status":FORECAST_STATUS,"season":2026,
           "runs":[ref],"safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    fs={path:forecast}
    preg,added=_observe_index(_empty_index(),
        {"1001":(c["games"][0],j["games"][0])},
        ROOT+"/pregame/2026/10/22/run-12345.json.gz",CAP)
    if second:
        cap2="2026-10-22T11:00:00Z"
        c2,j2=joined("12346",cap2)
        next_f=project(j2,rows(),"2026-10-22T11:05:00Z",{"training_source":"test_fixture_only"})
        path2=ROOT+"/forecasts/2026/10/22/run-12346.json.gz"
        ref2={**ref,"run_id":"12346","path":path2,
              "forecast_observed_utc":next_f["forecast_observed_utc"],
              "forecast_sha256":checksum(next_f)}
        index["runs"].append(ref2)
        fs[path2]=next_f
        preg,_=_observe_index(preg,{"1001":(c2["games"][0],j2["games"][0])},
            ROOT+"/pregame/2026/10/22/run-12346.json.gz",cap2)
    if not include_final:
        return preg,_empty_index(),index,fs,{}
    retrieved=dt.datetime(2026,10,25,2,tzinfo=dt.timezone.utc)
    finals=_finals([{"game_id":"1001","home":HOME,"away":AWAY,
                    "kickoff_utc":KICK,"home_score":"28",
                    "away_score":"17"}],retrieved)
    out,records,_=_link_observed_finals(preg,_empty_index(),finals,retrieved,
            "b"*64,retrieved+dt.timedelta(minutes=1))
    return preg,out,index,fs,dict(records)


def check(preg,out,ix,fs,finals,now=AFTER,grade_index=None):
    return grade(grade_index or empty_grade_index(),out,preg,ix,fs,finals,now)


class ProspectiveGradingTests(unittest.TestCase):
    def test_no_completed_games_is_empty_research_not_success_claim(self):
        p,o,f,fs,l=scenario(False)
        index,created,result=check(p,o,f,fs,l,"2026-10-22T11:00:00Z")
        self.assertEqual(len(created),0)
        self.assertEqual(result["total_frozen_graded_games"],0)
        self.assertEqual(result["indexed_final_games"],0)
        self.assertFalse(result["model_validated"])
        self.assertEqual(result["betting_status"],"PASS_UNVALIDATED")

    def test_observed_final_creates_immutable_unvalidated_score(self):
        p,o,f,fs,l=scenario()
        index,created,report=check(p,o,f,fs,l)
        self.assertEqual(len(created),1)
        path,item=created[0]
        self.assertEqual(item["actual_margin"],11)
        self.assertEqual(item["actual_total"],45)
        self.assertEqual(item["forecast_run_id"],"12345")
        self.assertEqual(report["newly_graded_games"],1)
        self.assertEqual(report["total_frozen_graded_games"],1)
        self.assertIsNone(item["ats_grade"])
        self.assertIsNone(item["over_under_grade"])
        self.assertEqual(item["market_status"],"NOT_OBSERVED_PRIVATE_OPT_IN_ONLY")
        self.assertFalse(item["model_validated"])
        self.assertTrue(verify_prior_grade(index,{path:item}))
        self.assertGreaterEqual(item["forecast_lead_hours"],24)

    def test_repeated_run_is_idempotent_no_new_grades(self):
        p,o,f,fs,l=scenario()
        index,created,_=check(p,o,f,fs,l)
        later,new,report=check(p,o,f,fs,l,grade_index=index)
        self.assertEqual(len(new),0)
        self.assertEqual(report["outstanding"]["already_graded"],1)
        self.assertEqual(later,index)

    def test_late_final_cannot_grade_at_earlier_evaluation_cutoff(self):
        p,o,f,fs,l=scenario()
        _,grades,r=check(p,o,f,fs,l,"2026-10-25T01:55:00Z")
        self.assertFalse(grades)
        self.assertEqual(r["outstanding"]["label_not_observed_yet"],1)

    def test_modified_score_file_blocked(self):
        p,o,f,fs,l=scenario()
        original=next(iter(l))
        l[original]["home_score"]=40
        with self.assertRaisesRegex(ValueError,"checksum"):
            check(p,o,f,fs,l)

    def test_modified_forecast_file_blocked(self):
        p,o,f,fs,l=scenario()
        source=next(iter(fs))
        fs[source]["games"][0]["projection"]["predicted_home_margin"]=999.
        with self.assertRaises(ValueError):
            check(p,o,f,fs,l)

    def test_missing_original_forecast_bytes_rejected(self):
        p,o,f,fs,l=scenario()
        with self.assertRaisesRegex(ValueError,"Missing/unindexed"):
            check(p,o,f,{},l)

    def test_missing_independent_pregame_entry_blocks_grading(self):
        p,o,f,fs,l=scenario()
        p["games"]["1001"]=[]
        with self.assertRaisesRegex(ValueError,"matching previously archived"):
            check(p,o,f,fs,l)

    def test_latest_valid_forecast_selected_before_kickoff(self):
        p,o,f,fs,l=scenario(second=True)
        _,graded,summary=check(p,o,f,fs,l)
        self.assertEqual(len(graded),1)
        self.assertEqual(graded[0][1]["forecast_run_id"],"12346")

    def test_no_exactly_eligible_24_72h_forecast_is_not_retroactively_filled(self):
        p,o,f,fs,l=scenario()
        # Forecast is still a true observation, but no SOURCE file is
        # reachable from this evaluation cut: no row can be invented.
        p2=copy.deepcopy(p)
        original=next(iter(fs.values()))
        original["games"][0]["policy_24_to_72h_eligible"]=False
        with self.assertRaises(ValueError):
            check(p2,o,f,fs,l)

    def test_existing_immutable_grade_sha_fails_if_mutated(self):
        p,o,f,fs,l=scenario()
        ix,created,_=check(p,o,f,fs,l)
        path,obj=created[0]
        obj=copy.deepcopy(obj);obj["actual_home_score"]=32
        with self.assertRaisesRegex(ValueError,"integrity"):
            verify_prior_grade(ix,{path:obj})

    def test_game_identity_rewrite_blocked(self):
        p,o,f,fs,l=scenario()
        o["games"]["1001"]["away"]="A Different College"
        with self.assertRaises(ValueError):
            check(p,o,f,fs,l)

    def test_revised_selection_cannot_replace_an_existing_grade(self):
        p,o,f,fs,l=scenario()
        ix,_,_=check(p,o,f,fs,l)
        cp,co,cf,cfs,cl=scenario(second=True)
        nextidx,records,summary=check(cp,co,cf,cfs,cl,grade_index=ix)
        self.assertFalse(records)
        self.assertEqual(summary["outstanding"]["frozen_grade_conflict_requires_review"],1)
        self.assertEqual(nextidx,ix)


if __name__=="__main__":
    unittest.main()

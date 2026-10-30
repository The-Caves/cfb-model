import copy
import unittest
from scripts.qb_postgame_starter_archive import empty,plan,validate,verify_index,DANGER,STATUS,source_archive_run_id,reviewed_corrections
from scripts.qb_postgame_starter_labels import parse,collect,LABEL,UNKNOWN
from test_qb_postgame_starter_labels import GAME,payload,AT

def snapshot():
    return collect([GAME],AT,lambda gid:payload(),workers=1)

class PostgameQBArchiveTests(unittest.TestCase):
    def test_two_postgame_publishers_have_distinct_numeric_run_keys(self):
        espn=source_archive_run_id("40991919323","ESPN_SITE_GAME_SUMMARY")
        school=source_archive_run_id("40991919323","REVIEWED_OFFICIAL_SCHOOL_BOXSCORE_HTML")
        self.assertEqual(espn,"40991919323")
        self.assertEqual(school,"409919193232")
        self.assertNotEqual(school,espn)
        with self.assertRaises(ValueError):
            source_archive_run_id("40991919323","UNREVIEWED_PROVIDER")
        with self.assertRaises(ValueError):
            source_archive_run_id("not-numeric","ESPN_SITE_GAME_SUMMARY")
        first,_,_=plan(empty(),snapshot(),espn)
        # The second distinct source key remains eligible to write a new
        # source observation in the same underlying GitHub workflow run.
        second=snapshot()
        away=next(x for x in second["rows"] if x["team"]==GAME["away"])
        away.update({"label_status":LABEL,"starter_player":"B Starter",
                     "explicit_qb_starter_flags":1,"requires_manual_review":False})
        updated,record,counts=plan(first,second,school)
        self.assertIsNotNone(record)
        self.assertEqual(len(updated["runs"]),2)
        self.assertEqual(counts["eligible_provider_flag_starter_labels"],2)

    def test_audited_same_source_name_repair_appends_and_retains_prior(self):
        old,_,_=plan(empty(),snapshot(),"99")
        # First captured positive label was contaminated by team-logo alt text.
        old["slots"][GAME["game_id"]+"|"+GAME["home"]]["starter_player"]="A School B Starter"
        last=old["slots"][GAME["game_id"]+"|"+GAME["home"]]["observations"][-1]
        last["starter_player"]="A School B Starter"
        # This is only a fixture; all source, game, name and original SHA must agree.
        actual=snapshot()
        new_player=next(x for x in actual["rows"] if x["team"]==GAME["home"])
        new_player["source_url"]=last["source_url"]
        reviewed={GAME["game_id"]+"|"+GAME["home"]:{
            "old_player":"A School B Starter",
            "new_player":"A Starter",
            "source_url":last["source_url"],
            "old_source_payload_sha256":last["source_payload_sha256"]}}
        revised,record,summary=plan(old,actual,"100",reviewed)
        corrected=revised["slots"][GAME["game_id"]+"|"+GAME["home"]]
        self.assertEqual(corrected["starter_player"],"A Starter")
        self.assertEqual(corrected["effective_status"],LABEL)
        self.assertEqual(len(corrected["observations"]),2)
        self.assertEqual(corrected["observations"][-1]["reviewed_adjudication"]["old_player"],"A School B Starter")
        self.assertEqual(summary["quarantined_conflicts"],0)
        wrong=copy.deepcopy(reviewed)
        wrong[GAME["game_id"]+"|"+GAME["home"]]["old_source_payload_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"provenance"):
            plan(old,actual,"100",wrong)
        with self.assertRaisesRegex(ValueError,"provenance"):
            plan(old,actual,"100",{GAME["game_id"]+"|"+GAME["home"]:{
                **reviewed[GAME["game_id"]+"|"+GAME["home"]],"new_player":"Someone Else"}})
    def test_registered_corrections_are_source_bound_and_complete(self):
        registered=reviewed_corrections("config/official_school_qb_name_corrections_2026.json")
        self.assertEqual(len(registered),3)
        self.assertEqual(registered["401856732|Texas Longhorns"]["new_player"],"Arch Manning")

    def test_unknown_retained_and_one_accepted_starter(self):
        first,record,summary=plan(empty(),snapshot(),"99")
        self.assertTrue(verify_index(first))
        self.assertEqual(summary["new_starter_observations"],2)
        self.assertEqual(summary["eligible_provider_flag_starter_labels"],1)
        self.assertEqual(first["slots"][GAME["game_id"]+"|"+GAME["home"]]["effective_status"],LABEL)
        self.assertEqual(first["slots"][GAME["game_id"]+"|"+GAME["away"]]["effective_status"],UNKNOWN)
        self.assertEqual(record["rows"][1]["starter_player"],"A Starter")
        self.assertEqual(record["status"],STATUS)

    def test_identical_future_observations_are_not_double_counted(self):
        prior,_,_=plan(empty(),snapshot(),"99")
        follow,record,summary=plan(prior,snapshot(),"100")
        self.assertIsNone(record)
        self.assertEqual(follow["runs"],prior["runs"])
        self.assertEqual(summary["eligible_provider_flag_starter_labels"],1)
        self.assertEqual(summary["new_starter_observations"],0)

    def test_unknown_can_mature_to_new_explicit_source_label(self):
        prior,_,_=plan(empty(),snapshot(),"99")
        second=snapshot()
        away=next(r for r in second["rows"] if r["team"]==GAME["away"])
        away.update({"starter_player":"B Starter",
                     "label_status":LABEL,
                     "explicit_qb_starter_flags":1,
                     "requires_manual_review":False})
        updated,record,summary=plan(prior,second,"100")
        self.assertEqual(summary["eligible_provider_flag_starter_labels"],2)
        self.assertEqual(summary["new_starter_observations"],1)
        self.assertEqual(len(record["rows"]),1)
        entry=updated["slots"][GAME["game_id"]+"|"+GAME["away"]]
        self.assertEqual(entry["effective_status"],LABEL)
        self.assertEqual(len(entry["observations"]),2)

    def test_changed_explicit_starter_is_quarantined(self):
        prior,_,_=plan(empty(),snapshot(),"99")
        second=snapshot()
        home=next(r for r in second["rows"] if r["team"]==GAME["home"])
        home["starter_player"]="Another QB"
        updated,record,summary=plan(prior,second,"100")
        self.assertEqual(summary["quarantined_conflicts"],1)
        self.assertEqual(summary["eligible_provider_flag_starter_labels"],0)
        entry=updated["slots"][GAME["game_id"]+"|"+GAME["home"]]
        self.assertEqual(entry["effective_status"],DANGER)
        self.assertIsNone(entry["starter_player"])

    def test_later_removed_explicit_flag_quarantines_old_label(self):
        old,_,_=plan(empty(),snapshot(),"99")
        second=snapshot()
        home=next(r for r in second["rows"] if r["team"]==GAME["home"])
        home.update({"starter_player":None,"label_status":UNKNOWN,
                     "explicit_qb_starter_flags":0})
        new,_,summary=plan(old,second,"100")
        self.assertEqual(summary["quarantined_conflicts"],1)
        self.assertEqual(new["slots"][GAME["game_id"]+"|"+GAME["home"]]["effective_status"],DANGER)

    def test_invalid_or_future_source_is_refused(self):
        x=snapshot()
        x["rows"][0]["source_payload_sha256"]="not_a_sha"
        with self.assertRaisesRegex(ValueError,"Source"):
            validate(x)
        x=snapshot()
        x["rows"][0]["starter_player"]="Imaginary QB"
        with self.assertRaisesRegex(ValueError,"Unsigned"):
            validate(x)

    def test_no_run_replacement_and_tampered_index_ref(self):
        prior,_,_=plan(empty(),snapshot(),"99")
        with self.assertRaisesRegex(ValueError,"Already archived"):
            plan(prior,snapshot(),"99")
        prior["runs"][0]["path"]="research_2026/qb_postgame_starters/2026/10/29/../100.json.gz"
        with self.assertRaisesRegex(ValueError,"Corrupt"):
            verify_index(prior)

if __name__=="__main__":unittest.main()

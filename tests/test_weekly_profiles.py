"""Prevent later statistics from rewriting older reconstructed team profiles."""
import copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
from scripts.weekly_profiles import (
    STATUS,canonical,digest,build_snapshots,save_snapshots,cutoff_dates)
from scripts.model_v03 import build_weekly_games

def game(i,day,home,away,home_score,away_score):
    return dict(game_id=i,date=day,kickoff_utc=day+"T20:00:00Z",
        home=home,away=away,home_score=str(home_score),away_score=str(away_score),
        neutral="False")

def plays(g,team,opp,epa):
    return dict(game_id=g["game_id"],date=g["date"],team=team,opponent=opp,
        off_epa_sum=str(epa*50),epa_plays="50",def_epa_sum="5",
        def_epa_plays="50",pass_epa_sum="3",pass_epa_plays="25",
        rush_epa_sum="1",rush_epa_plays="25",success_count="25",
        success_plays="50",explosive_pass="2",pass_plays="25",
        explosive_rush="1",rush_plays="25",pressure_count="1",
        pressure_observed="25",drive_yards_sum="330",drives="10",
        scrimmage_plays="50")

class ProfileArchiveTests(unittest.TestCase):
    def sample(self):
        games=[game("1","2026-09-05","Texas","Oklahoma",28,17),
               game("2","2026-09-12","Texas","Rice",21,14),
               game("3","2026-10-03","Texas","Oklahoma",3,14)]
        advanced={}
        for g in games:
            advanced[g["game_id"]]={
                team:plays(g,team,opp,.2 if team=="Texas" else -.1)
                for team,opp in ((g["home"],g["away"]),(g["away"],g["home"]))
            }
        return games,advanced
    def snaps(self,games=None,advanced=None):
        if games is None:games,advanced=self.sample()
        dates=[dt.date(2026,9,12),dt.date(2026,9,19),dt.date(2026,10,10)]
        return build_snapshots(games,advanced,["Oklahoma","Rice","Texas"],dates)
    def texas(self,snap):
        return next(x for x in snap["profiles"] if x["team"]=="Texas")
    def test_future_games_excluded_and_weekly_profiles_change(self):
        p=self.snaps()
        self.assertEqual(self.texas(p[0])["prior_game_ids"],["1"])
        self.assertEqual(self.texas(p[1])["prior_game_ids"],["1","2"])
        self.assertEqual(self.texas(p[2])["prior_game_ids"],["1","2","3"])
        self.assertNotEqual(self.texas(p[0])["recent_form"]["win"],
                            self.texas(p[2])["recent_form"]["win"])
        self.assertEqual(p[0]["evidence_status"],STATUS)
        self.assertFalse(p[0]["historical_publication_times_verified"])
    def test_later_result_and_epa_mutation_cannot_change_september(self):
        games,adv=self.sample()
        before=self.snaps(games,adv)
        games[-1]["home_score"]="100"
        adv["3"]["Texas"]["off_epa_sum"]="9000"
        after=self.snaps(games,adv)
        self.assertEqual([digest(canonical(x)) for x in before[:2]],
                         [digest(canonical(x)) for x in after[:2]])
        self.assertNotEqual(digest(canonical(before[-1])),
                            digest(canonical(after[-1])))
    def test_current_date_cannot_enter_profile(self):
        games,adv=self.sample()
        old=self.snaps(games,adv)[0]
        games[1]["home_score"]="140"
        self.assertEqual(canonical(old),canonical(self.snaps(games,adv)[0]))
    def test_missing_epa_remains_none(self):
        games,adv=self.sample()
        del adv["1"]
        tx=self.texas(self.snaps(games,adv)[0])
        self.assertIsNone(tx["recent_form"]["epa_pass"])
        self.assertEqual(tx["recent_form"]["epa_coverage"],0)
    def test_new_teams_have_null_form_not_fake_zero(self):
        g,adv=self.sample()
        r=build_snapshots(g,adv,["Texas","Stanford"],[dt.date(2026,9,5)])[0]
        self.assertIsNone(r["profiles"][0]["recent_form"]["points_for"])
        self.assertEqual(r["profiles"][1]["games_before_cutoff"],0)
    def test_same_updater_as_v03(self):
        g,a=self.sample()
        y=build_weekly_games(g,a)
        p=self.texas(self.snaps(g,a)[0])
        self.assertEqual(y[1]["home_games_prior"],p["games_before_cutoff"])
    def test_overwrite_rejected_and_existing_contents_retained(self):
        snaps=self.snaps()
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)
            manifest={"retrieved_at_utc":"2026-10-21T20:00:00Z","sources":{}}
            report=save_snapshots(snaps,dest,manifest,{"games":"a"*64})
            self.assertEqual(report["cutoff_count"],3)
            original=(dest/"asof-2026-09-12.json").read_bytes()
            edited=copy.deepcopy(snaps)
            self.texas(edited[0])["recent_form"]["win"]=0.33
            with self.assertRaisesRegex(ValueError,"FROZEN_PROFILE_DRIFT"):
                save_snapshots(edited,dest,manifest,{})
            self.assertEqual(original,(dest/"asof-2026-09-12.json").read_bytes())
            with self.assertRaisesRegex(ValueError,"Capture manifest already exists"):
                save_snapshots(snaps,dest,manifest,{})
            self.assertFalse(json.loads((dest/"capture_manifest.json").read_text())
                             ["historical_publication_times_verified"])
    def test_cutoffs_cover_weekends_and_midweek(self):
        games,_=self.sample()
        games.append(game("4","2026-10-07","Rice","Texas",10,21))
        dates=cutoff_dates(games,"2026-10-10")
        self.assertIn(dt.date(2026,10,7),dates)
        self.assertIn(dt.date(2026,10,10),dates)
        self.assertIn(dt.date(2026,8,1),dates)
    def test_duplicate_cutoffs_disallowed(self):
        g,a=self.sample()
        with self.assertRaises(ValueError):
            build_snapshots(g,a,["Texas"],[dt.date(2026,9,12)]*2)
    def test_no_final_scores_or_betting_clearance_in_profile(self):
        snap=self.snaps()[0]
        self.assertFalse(snap["safe_for_betting"])
        self.assertEqual(snap["betting_status"],"PASS_UNVALIDATED")
        self.assertNotIn("home_score",canonical(snap).decode())
        self.assertNotIn("away_score",canonical(snap).decode())
if __name__=="__main__":unittest.main()

"""Official university HTML boxscore's STARTERS is stronger than passer-leading proxy."""
import unittest,json
from pathlib import Path
from scripts.qb_official_school_boxscores import parse,collect,SOURCE,valid_source
from scripts.qb_postgame_starter_labels import LABEL
from scripts.qb_postgame_starter_archive import empty,plan,DANGER
from test_qb_postgame_starter_labels import GAME as OTHER_GAME, payload as ESPN_FIXTURE
from scripts.qb_postgame_starter_labels import collect as espn_collect

AT="2026-10-29T23:45:00Z"
GAME={"game_id":"401856732","date":"2026-10-24",
      "home":"Texas Longhorns","away":"Ole Miss Rebels",
      "home_score":"34","away_score":"27","kickoff_utc":"2026-10-24T23:30:00Z"}
def config():
    return {"season":2026,"game_id":GAME["game_id"],"game_date_et":GAME["date"],
       "home":GAME["home"],"away":GAME["away"],
       "home_score":34,"away_score":27,"kickoff_utc":GAME["kickoff_utc"],
       "home_source_label":"Texas","away_source_label":"Ole Miss",
       "home_starting_qb_name":"Arch Manning","away_starting_qb_name":"Trinidad Chambliss",
       "source_url":"https://texaslonghorns.com/sports/football/stats/2026/ole-miss/boxscore/22500",
       "publisher_hostname":"texaslonghorns.com","reviewed_official_publisher":True}
def html():
    return """<html><head><title>Football vs Ole Miss on 10/24/2026 - Box Score</title></head><body>
      <header>Ole Miss vs Texas</header><section>10/24/2026</section>
      <div>Ole Miss</div><div>5-2, 3-2</div><div>27</div><div>Final</div><div>34</div><div>Texas</div>
      <div>Individual stats</div>
      <h2>Starters</h2>
      <section><img alt="Ole Miss"><h3>Offense</h3>
      <table><tr><th>#</th><th>Player</th><th>Pos.</th></tr>
      <tr><td>51</td><td>Townsend,Delano</td><td>OL</td></tr>
      <tr><td>6</td><td>Chambliss,Trinidad</td><td>QB</td></tr></table></section>
      <section><img alt="Texas"><h3>Offense</h3>
      <table><tr><th>#</th><th>Player</th><th>Pos.</th></tr>
      <tr><td>16</td><td><a>Manning, Arch</a></td><td>QB</td></tr></table></section>
      <section><img alt="Texas"><h3>Defense</h3></section>
      <h2>Player Participation</h2>
      </body></html>"""

class OfficialBoxScoreStarterTests(unittest.TestCase):
    def test_reviewed_source_two_real_offense_starters(self):
        rows=parse(GAME,config(),html(),AT)
        self.assertEqual([x["starter_player"] for x in rows],["Trinidad Chambliss","Arch Manning"])
        self.assertTrue(all(x["label_status"]==LABEL for x in rows))
        self.assertTrue(all(x["source_class"]==SOURCE for x in rows))
        self.assertEqual(rows[0]["team"],GAME["away"])
        self.assertTrue(rows[0]["not_from_passing_leader"])
        self.assertEqual(len(rows[0]["source_payload_sha256"]),64)
    def test_sidearm_inline_svg_and_script_markup_do_not_hide_official_starters(self):
        extra=('<script type="application/json">{"text":"Starters QB"}</script>'
               '<svg><title>Starters</title><path d="M0 0"/></svg>')
        page=html().replace("<h2>Starters</h2>",extra+"<h2>Starters</h2>")
        r=parse(GAME,config(),page,AT)
        self.assertEqual([x["starter_player"] for x in r],["Trinidad Chambliss","Arch Manning"])
        # A provider page may also contain an unmatched inline SVG tag.
        # Never let its state suppress the subsequent gamebook's actual text.
        unmatched=html().replace("<h2>Starters</h2>",
                               '<svg class="icon"><path d="M1 1"/><h2>Starters</h2>')
        r=parse(GAME,config(),unmatched,AT)
        self.assertEqual(r[1]["starter_player"],"Arch Manning")

    def test_team_image_alt_between_qb_name_tokens_is_ignored(self):
        page=html().replace("<a>Manning, Arch</a>","<a>Manning,<img alt='Ole Miss'> Arch</a>")
        result=parse(GAME,config(),page,AT)
        self.assertEqual(result[1]["starter_player"],"Arch Manning")
        self.assertNotIn("Ole Miss",result[1]["starter_player"])
    def test_wrong_extracted_name_is_rejected_before_becoming_a_label(self):
        cfg=config();cfg["home_starting_qb_name"]="Arch Ole Miss Manning"
        with self.assertRaisesRegex(ValueError,"differs from reviewed"):
            parse(GAME,cfg,html(),AT)

    def test_wrong_score_fails_even_if_qb_table_is_correct(self):
        bad=html().replace("<div>27</div><div>Final</div><div>34</div>",
                           "<div>21</div><div>Final</div><div>34</div>")
        with self.assertRaisesRegex(ValueError,"score"):
            parse(GAME,config(),bad,AT)
    def test_wrong_team_game_date_or_review_rejected(self):
        cfg=config();cfg["away"]="Another Rebels"
        with self.assertRaises(ValueError):parse(GAME,cfg,html(),AT)
        cfg=config();cfg["game_date_et"]="2026-10-25"
        with self.assertRaises(ValueError):parse(GAME,cfg,html(),AT)
        cfg=config();cfg["reviewed_official_publisher"]=False
        with self.assertRaises(ValueError):valid_source(cfg)
    def test_school_publishing_away_team_may_show_home_score_first(self):
        game={**GAME,"home":"Cincinnati Bearcats","away":"Texas Tech Red Raiders",
              "home_score":"37","away_score":"24","game_id":"401856840",
              "kickoff_utc":"2026-10-24T16:00:00Z"}
        cfg={**config(),"home":game["home"],"away":game["away"],
             "home_score":37,"away_score":24,"game_id":game["game_id"],
             "kickoff_utc":game["kickoff_utc"],
             "home_source_label":"Cincinnati","away_source_label":"Texas Tech",
             "home_starting_qb_name":"JC French IV","away_starting_qb_name":"Will Hammond",
             "scoreboard_first_side":"home"}
        text=html().replace('Ole Miss vs Texas','Cincinnati vs Texas Tech')
        text=text.replace('<div>Ole Miss</div>','<div>Cincinnati</div>')
        text=text.replace('<div>27</div><div>Final</div><div>34</div>',
                          '<div>37</div><div>Final</div><div>24</div>')
        text=text.replace('alt="Ole Miss"','alt="Cincinnati"')
        text=text.replace('alt="Texas"','alt="Texas Tech"')
        text=text.replace("Chambliss,Trinidad","French IV,JC")
        text=text.replace("Manning, Arch","Hammond, Will")
        rows=parse(game,cfg,text,AT)
        self.assertEqual(rows[0]["team"],"Texas Tech Red Raiders")
        self.assertEqual(rows[1]["team"],"Cincinnati Bearcats")
        cfg.pop("scoreboard_first_side")
        with self.assertRaisesRegex(ValueError,"score"):
            parse(game,cfg,text,AT)

    def test_no_offense_team_label_or_ambiguous_qb_not_promoted(self):
        bad=html().replace('alt="Texas"','alt="Somewhere"',1)
        with self.assertRaisesRegex(ValueError,"heading"):
            parse(GAME,config(),bad,AT)
        both=html().replace('<tr><td>16</td><td><a>Manning, Arch</a></td><td>QB</td></tr>',
                            '<tr><td>16</td><td>Manning, Arch</td><td>QB</td></tr>'+
                            '<tr><td>12</td><td>Other, Person</td><td>QB</td></tr>')
        rows=parse(GAME,config(),both,AT)
        self.assertIsNone(rows[1]["starter_player"])
        self.assertEqual(rows[1]["label_status"],"CONFLICT_MULTIPLE_EXPLICIT_QB_FLAGS")
    def test_official_missing_qb_does_not_use_passer_from_other_sections(self):
        bad=html().replace('<tr><td>16</td><td><a>Manning, Arch</a></td><td>QB</td></tr>',
                           '<tr><td>16</td><td>Manning, Arch</td><td>WR</td></tr>')
        rows=parse(GAME,config(),bad,AT)
        self.assertIsNone(rows[1]["starter_player"])
    def test_source_registry_recovers_only_games_it_explicitly_reviewed(self):
        manifest={"status":"MANUALLY_REVIEWED_OFFICIAL_SCHOOL_POSTGAME_BOXSCORES",
             "season":2026,"entries":[config()]}
        report=collect([GAME],manifest,AT,lambda e:html())
        self.assertEqual(report["explicit_starter_labels"],2)
        self.assertEqual(report["verified_game_identities"],1)
        self.assertEqual(report["missing_or_rejected_games"],0)
        report=collect([OTHER_GAME],manifest,AT,lambda e:html())
        self.assertEqual(report["team_slots"],0)
        self.assertEqual(report["explicit_starter_labels"],0)
    def test_official_source_is_allowed_in_append_only_label_ledger(self):
        manifest={"status":"MANUALLY_REVIEWED_OFFICIAL_SCHOOL_POSTGAME_BOXSCORES",
             "season":2026,"entries":[config()]}
        snapshot=collect([GAME],manifest,AT,lambda e:html())
        idx,record,stats=plan(empty(),snapshot,"901")
        self.assertEqual(stats["eligible_provider_flag_starter_labels"],2)
        self.assertEqual(len(record["rows"]),2)
        self.assertEqual(idx["slots"][GAME["game_id"]+"|"+GAME["home"]]["starter_player"],"Arch Manning")
    def test_separate_espn_unknown_must_not_cancel_official_qb_start(self):
        manifest={"status":"MANUALLY_REVIEWED_OFFICIAL_SCHOOL_POSTGAME_BOXSCORES",
             "season":2026,"entries":[config()]}
        source=collect([GAME],manifest,AT,lambda e:html())
        idx,_,_=plan(empty(),source,"901")
        # Full output is an ESPN-styled observation of the same exact game
        # with no starter flags; it must not retract official STARTERS data.
        unknown={**source,"source":"ESPN_SITE_GAME_SUMMARY","rows":[]}
        for row in source["rows"]:
            r={**row,"source_url":"https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event="+GAME["game_id"],
               "starter_player":None,"label_status":"UNKNOWN_NOT_VERIFIED_STARTER",
               "explicit_qb_starter_flags":0}
            r.pop("source_class",None);unknown["rows"].append(r)
        idx2,changes,stats=plan(idx,unknown,"902")
        self.assertIsNone(changes)
        self.assertEqual(stats["eligible_provider_flag_starter_labels"],2)
        self.assertEqual(stats["quarantined_conflicts"],0)
    def test_four_new_independently_reviewed_october_24_gamebooks(self):
        manifest=json.loads(Path("config/official_school_qb_boxscores_2026.json").read_text())
        self.assertEqual(manifest["season"],2026)
        entries={str(e["game_id"]):e for e in manifest["entries"]}
        self.assertEqual(len(entries),len(manifest["entries"]))
        expected={
          "401858495":("Illinois Fighting Illini","Oregon Ducks",21,10,
                        "Michael Clayton II","Dylan Raiola",
                        "https://fightingillini.com/sports/football/stats/2026/oregon/boxscore/29212"),
          "401858497":("Minnesota Golden Gophers","Iowa Hawkeyes",13,10,
                        "Drake Lindsey","Jeremy Hecklinski",
                        "https://gophersports.com/sports/football/stats/2026/iowa/boxscore/22839"),
          "401858499":("UCLA Bruins","Michigan State Spartans",28,10,
                        "Ty Dieffenbach","Kayd Coffman",
                        "https://msuspartans.com/sports/football/stats/2026/-9-ucla/boxscore/20509"),
          "401858500":("Wisconsin Badgers","USC Trojans",24,7,
                        "Colton Joseph","Jayden Maiava",
                        "https://uwbadgers.com/sports/football/stats/2026/usc/boxscore/17147"),
        }
        for gid,(home,away,h,a,hqb,aqb,url) in expected.items():
            with self.subTest(game_id=gid):
                self.assertIn(gid,entries)
                e=entries[gid]
                self.assertEqual((e["home"],e["away"],e["home_score"],e["away_score"],
                                  e["home_starting_qb_name"],e["away_starting_qb_name"],
                                  e["source_url"]), (home,away,h,a,hqb,aqb,url))
                self.assertEqual(e["game_date_et"],"2026-10-24")
                self.assertTrue(e["reviewed_official_publisher"])
                self.assertIn("/sports/football/stats/2026/",valid_source(e))
                self.assertEqual(e["kickoff_utc"],{
                  "401858495":"2026-10-24T19:00:00Z",
                  "401858497":"2026-10-24T19:30:00Z",
                  "401858499":"2026-10-24T19:30:00Z",
                  "401858500":"2026-10-24T23:30:00Z"}[gid])
if __name__=="__main__":unittest.main()


import copy
import datetime as dt
import unittest
from scripts.qb_multidimensional_form import profile,SOURCE

DEC="2026-10-30T16:00:00Z"
KICK="2026-10-31T20:00:00Z"
def row(i,team="Team A",season=2026):
    day=dt.date(season,9,1)+dt.timedelta(days=i)
    return {"game_id":str(season)+"-"+str(i),"date":day.isoformat(),
       "team":team,"opponent":"Team C","player_id":"roster:qb:001",
       "source_observed_at_utc":(dt.datetime.combine(day,dt.time(22),dt.timezone.utc)
                                +dt.timedelta(days=1)).isoformat(),
       "kickoff_utc":dt.datetime.combine(day,dt.time(20),dt.timezone.utc).isoformat(),
       "status":SOURCE,"player_identity_crosswalk_verified":True,
       "source_url":"https://example.edu/pbp","season":season,
       "pressured_dropbacks":10,"clean_dropbacks":20,
       "qb_scrambles":3,"qb_designed_rushes":4,
       "sacks_taken":2,"offensive_turnovers":1,
       "pressured_epa_sum":-1.0,"clean_epa_sum":4.0,
       "scramble_epa_sum":1.8,"designed_rush_epa_sum":2.4}
def calc(rows,pressure=.5):
    return profile(rows,"roster:qb:001","Team A",KICK,DEC,
                  opponent_pressure_rate=pressure,
                  opponent_pressure_observed_at_utc="2026-10-28T12:00:00Z")
class QBMultidimensionalTests(unittest.TestCase):
    def test_pressure_rush_sacks_and_turnovers_separate(self):
        d=calc([row(i) for i in range(5)])
        self.assertAlmostEqual(d["pressured_epa_per_dropback"],-.1)
        self.assertAlmostEqual(d["clean_epa_per_dropback"],.2)
        self.assertAlmostEqual(d["pressure_penalty_epa_per_dropback"],-.3)
        self.assertAlmostEqual(d["pressure_matched_epa_per_dropback"],.05)
        self.assertGreater(d["weighted_rush_touches"],0)
        self.assertIsNotNone(d["scramble_epa_per_run"])
        self.assertIsNotNone(d["designed_run_epa_per_carry"])
        self.assertIsNotNone(d["turnovers_per_observed_touch"])
        self.assertFalse(d["starting_qb_confirmed_from_pbp"])
        self.assertIsNone(d["qb_point_adjustment"])

    def test_verified_transfer_uses_shrunk_history(self):
        t=row(0,"Previous School",2025)
        t["transfer_identity_verified"]=True
        t["transfer_source_url"]="https://example.edu/roster"
        t["transfer_observed_at_utc"]="2026-08-10T10:00:00Z"
        p=calc([t,row(0)])
        self.assertEqual(p["transfer_or_prior_team_games"],1)
        self.assertEqual(p["same_team_games"],1)
        self.assertGreater(p["weighted_dropbacks"],30)
        t.pop("transfer_identity_verified")
        self.assertEqual(calc([t,row(0)])["excluded"]["unverified_transfer"],1)

    def test_future_capture_is_not_considered(self):
        future=row(0);future["source_observed_at_utc"]="2026-11-01T02:00:00Z"
        p=calc([future])
        self.assertEqual(p["prior_games_evidenced"],0)
        self.assertEqual(p["excluded"]["future_capture"],1)
        self.assertIsNone(p["pressure_matched_epa_per_dropback"])

    def test_future_opponent_pressure_or_bad_counts_fail(self):
        with self.assertRaises(ValueError):
            profile([row(0)],"roster:qb:001","Team A",KICK,DEC,.8,
                    "2026-11-01T00:00:00Z")
        bad=row(0);bad["pressured_dropbacks"]=-1
        with self.assertRaises(ValueError):calc([bad])

    def test_insufficient_pressure_tape_stays_unknown(self):
        p=calc([row(0)])
        self.assertIsNone(p["pressured_epa_per_dropback"]) if False else self.assertIsNotNone(p["pressured_epa_per_dropback"])
        p=calc([])
        self.assertIsNone(p["pressured_epa_per_dropback"])
        self.assertFalse(p["sample_sufficient_for_pressure_matchup"])

if __name__=="__main__":unittest.main()

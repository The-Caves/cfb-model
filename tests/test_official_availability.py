import unittest,datetime as dt,tempfile,csv
from pathlib import Path
from scripts.official_availability import (eligible_report,parse_player,extract,
  fetch_and_match,published_timestamp,CONFERENCES,SOURCE_PAGE)
G={"game_id":"99","date_et":"2026-10-24","home":"Alabama Crimson Tide",
   "away":"Auburn Tigers","kickoff_utc":"2026-10-24T20:00:00Z"}
ALIASES={"Alabama":"Alabama Crimson Tide","Auburn":"Auburn Tigers"}
def card(status="Initial Report",published="2026-10-24",clock="09:00:00",
         rows=None):
    if rows is None:rows=[{"name":"QB #12 Player One","status":"Out"}]
    return {"ReportType":status,"publishDate":published,"postedTime":clock,
      "conferenceTimeZone":"CT","footer":{"date":"2026-10-24"},
      "games":[{"teamDisplayName":"Alabama","rows":rows},
               {"teamDisplayName":"Auburn","rows":[]}]}
class PublishedOfficialTests(unittest.TestCase):
    def test_parse_display_and_no_qb_inference(self):
        p=parse_player({"name":"QB #12 Sample Quarterback","status":"Out"})
        self.assertEqual((p["position"],p["status"]),("QB","OUT"))
        self.assertEqual(p["player"],"Sample Quarterback")
    def test_major_conference_official_sources_registered(self):
        self.assertEqual(set(CONFERENCES),{"SEC","B10","ACC","B12"})
        self.assertEqual(set(SOURCE_PAGE),set(CONFERENCES))
    def test_out_first_half_is_not_limited_or_full_game_out(self):
        for publisher in ("Out (1st Half)", "Out - (1st Half)"):
            p=parse_player({"name":"OL #77 Example Lineman","status":publisher})
            self.assertEqual(p["status"],"OUT_FIRST_HALF")
            rows,qa=extract("B10",{"a":card(rows=[{"name":"OL #77 Example Lineman",
                       "status":publisher}])},[G],ALIASES,"2026-10-24T17:00:00Z")
            self.assertEqual(qa["official_reports_accepted"],1)
            self.assertEqual(next(r["status"] for r in rows if r["kind"]=="AVAILABILITY"),
                             "OUT_FIRST_HALF")

    def test_name_without_known_position_is_not_truncated(self):
        p=parse_player({"name":"AK Dear","status":"Questionable"})
        self.assertEqual(p["player"],"AK Dear")
        self.assertEqual(p["position"],"OTHER")
    def test_pending_does_not_attest(self):
        rows,qa=extract("SEC",{"a":card(status="Report Pending")},[G],ALIASES,
               "2026-10-24T17:00:00Z")
        self.assertEqual(rows,[])
        self.assertEqual(qa["pending_cards"],1)
    def test_real_acc_report_player_position_alias(self):
        p=parse_player({"name":"ILB #0 Popo Aguirre","status":"Questionable"})
        self.assertEqual(p["position"],"LB")
        self.assertEqual(p["player"],"Popo Aguirre")
        self.assertEqual(p["status"],"QUESTIONABLE")
        p=parse_player({"name":"DB #0 Ja'Maric Morris","status":"Available"})
        self.assertEqual(p["position"],"DB")
        self.assertEqual(p["player"],"Ja'Maric Morris")
    def test_published_with_valid_game_and_cutoff(self):
        rows,qa=extract("SEC",{"a":card()},[G],ALIASES,"2026-10-24T17:00:00Z")
        self.assertEqual(len(rows),3)
        self.assertEqual(qa["official_reports_accepted"],1)
        self.assertEqual(sum(x["kind"]=="TEAM_REPORT" for x in rows),2)
        self.assertEqual(sum(x["kind"]=="AVAILABILITY" for x in rows),1)
        self.assertFalse(any(x["kind"]=="QB_STARTER" for x in rows))
    def test_report_published_in_future_is_rejected(self):
        rows,qa=extract("SEC",{"a":card(clock="13:00:00")},[G],ALIASES,
                        "2026-10-24T17:00:00Z")
        self.assertEqual(rows,[])
    def test_wrong_match_and_ambiguous_report_quarantined(self):
        game={**G,"game_id":"100"}
        rows,qa=extract("SEC",{"a":card()},[G,game],ALIASES,
                        "2026-10-24T17:00:00Z")
        self.assertEqual(rows,[])
        self.assertEqual(qa["report_cards"][0]["game_match"],"NO_UNIQUE_ESPN_GAME_MATCH")
    def test_exempt_admin_status_not_player_availability(self):
        # Live SEC/Big12 reports may include publisher Exempt rows. This is
        # neither AVAILABLE nor OUT, so it must be excluded from player claims.
        body=card(rows=[{"name":"QB #10 Player Exempt","status":"Exempt"},
                        {"name":"QB #12 Player One","status":"Questionable"}])
        rows,qa=extract("SEC",{"a":body},[G],ALIASES,
                        "2026-10-24T17:00:00Z")
        self.assertEqual(qa["official_reports_accepted"],1)
        self.assertEqual(qa["report_cards"][0]["excluded_exempt_rows"],1)
        actual=[r for r in rows if r["kind"]=="AVAILABILITY"]
        self.assertEqual(len(actual),1)
        self.assertEqual(actual[0]["player"],"Player One")
        self.assertEqual(actual[0]["status"],"QUESTIONABLE")
        self.assertFalse(any("Exempt" in r.get("player","") for r in rows))
    def test_unknown_non_exempt_still_quarantines_report(self):
        rows,qa=extract("SEC",{"a":card(rows=[{"name":"QB #12 Star","status":"Exempt"},
                           {"name":"RB #11 Player","status":"Injured"}])},
                        [G],ALIASES,"2026-10-24T17:00:00Z")
        self.assertEqual(rows,[])
        self.assertEqual(qa["report_cards"][0]["publication_status"],"PLAYER_ROW_SCHEMA_ERROR")
    def test_unknown_status_quarantines_whole_card(self):
        rows,qa=extract("SEC",{"a":card(rows=[{"name":"QB #12 Player One","status":"Injured"}])},
                         [G],ALIASES,"2026-10-24T17:00:00Z")
        self.assertEqual(rows,[])
        self.assertEqual(qa["report_cards"][0]["publication_status"],"PLAYER_ROW_SCHEMA_ERROR")
    def test_missing_side_rows_cannot_claim_full_coverage(self):
        broken=card();broken["games"][1].pop("rows")
        rows,qa=extract("SEC",{"a":broken},[G],ALIASES,"2026-10-24T17:00:00Z")
        self.assertEqual(rows,[])
    def test_no_archive_backfill_or_unknown_healthy(self):
        self.assertEqual(parse_player({"name":"WR #5 Player Name","status":"Available"})["status"],"AVAILABLE")
    def test_publisher_report_time_ct_to_utc(self):
        self.assertEqual(published_timestamp(card()).isoformat(),"2026-10-24T14:00:00+00:00")
if __name__=="__main__":unittest.main()

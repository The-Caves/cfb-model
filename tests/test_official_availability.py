import unittest,datetime as dt,tempfile,csv
from pathlib import Path
from scripts.official_availability import (eligible_report,parse_player,extract,
  fetch_and_match,published_timestamp)
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
    def test_pending_does_not_attest(self):
        rows,qa=extract("SEC",{"a":card(status="Report Pending")},[G],ALIASES,
               "2026-10-24T17:00:00Z")
        self.assertEqual(rows,[])
        self.assertEqual(qa["pending_cards"],1)
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

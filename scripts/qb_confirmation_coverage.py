"""Make starter verification actionable without manufacturing confirmations.

The source system can name an expected player (chart + recent usage) even when
no official game-specific "will start" statement exists. Coverage therefore
has two separate denominators and all 24/72-hour deadlines are auditable.
"""
import argparse,csv,datetime as dt,json
from pathlib import Path
from scripts.game_context import parse_time
from scripts.qb_expected_starters import STATUS as SOURCE

STATUS="QB_GAMEWEEK_CONFIRMATION_COVERAGE_AND_REVIEW_PRIORITY"
def build(expected,worklist,observed):
    if (expected.get("status")!=SOURCE or
        expected.get("betting_status")!="PASS_UNVALIDATED" or
        worklist.get("status")!="QB_STARTER_MANUAL_REVIEW_WORKLIST_RESEARCH_ONLY" or
        worklist.get("betting_status")!="PASS_UNVALIDATED"):
        raise ValueError("Untrusted QB evidence inputs")
    when=parse_time(observed)
    if parse_time(expected["observed_at_utc"])>when:
        raise ValueError("Candidate source after triage decision")
    index={(str(x["game_id"]),x["team"]):x for x in worklist["rows"]}
    if len(index)!=len(worklist["rows"]):raise ValueError("Duplicate official source worklist")
    rows=[]
    for candidate in expected["games"]:
        kickoff=parse_time(candidate["kickoff_utc"])
        if kickoff<=when:continue
        key=(str(candidate["game_id"]),candidate["team"])
        official=index.get(key)
        if official is None or official["opponent"]!=candidate["opponent"] or parse_time(official["kickoff_utc"])!=kickoff:
            raise ValueError("Official source candidate mismatched with depth chart")
        hours=(kickoff-when).total_seconds()/3600
        player=candidate.get("starter")
        status=candidate.get("starter_status")
        confirmed=candidate["is_confirmed_starter"]
        if confirmed and (not player or not status=="CONFIRMED_REVIEWED_PREKICKOFF"):
            raise ValueError("Invalid claimed starter confirmation")
        reason=("OFFICIAL_STARTER_ALREADY_REVIEWED" if confirmed else
            "CHECK_OFFICIAL_GAMEWEEK_ARTICLE_FOR_EXPLICIT_THIS_GAME_STARTER" if official.get("reviewed_official_preview_url") else
            "RECONCILE_CHART_AND_RECENT_PASSER_WITH_COACH_REPORT" if "CONFLICT" in status else
            "FIND_EXPLICIT_OFFICIAL_THIS_GAME_STARTER_STATEMENT")
        priority=(0 if hours<=24 else 1 if hours<=72 else 2,0 if not player else 1)
        rows.append({"game_id":key[0],"team":key[1],
            "opponent":candidate["opponent"],"kickoff_utc":candidate["kickoff_utc"],
            "lead_hours":round(hours,2),"confirmed_starter":confirmed,
            "expected_starter":player,"expected_source_status":status,
            "expected_confidence":candidate.get("confidence"),
            "depth_label":candidate.get("depth_label"),
            "chart_rank":candidate.get("depth_rank"),
            "chart_source_url":candidate.get("chart_source_url"),
            "historical_last_passer":candidate.get("last_game_leading_passer_proxy"),
            "official_athletics_homepage":official.get("official_athletics_homepage"),
            "official_gameweek_preview_url":official.get("reviewed_official_preview_url"),
            "official_game_notes_url":official.get("reviewed_game_notes_link"),
            "official_rss_url":official.get("official_rss_url"),
            "review_reason":reason,"priority":priority,
            "can_automatically_confirm_starter":False,
            "betting_status":"PASS_UNVALIDATED"})
    rows.sort(key=lambda x:(x["priority"],x["kickoff_utc"],x["team"]))
    n=len(rows)
    return {"status":STATUS,"season":2026,"observed_at_utc":when.isoformat(),
       "summary":{"team_slots":n,"named_expected":sum(bool(x["expected_starter"]) for x in rows),
         "confirmed":sum(x["confirmed_starter"] for x in rows),
         "unconfirmed":sum(not x["confirmed_starter"] for x in rows),
         "next_72h_unconfirmed":sum(x["lead_hours"]<=72 and not x["confirmed_starter"] for x in rows),
         "next_24h_unconfirmed":sum(x["lead_hours"]<=24 and not x["confirmed_starter"] for x in rows),
         "chart_recent_conflicts":sum("CONFLICT" in x["expected_source_status"] for x in rows),
         "direct_official_gameweek_previews":sum(bool(x["official_gameweek_preview_url"]) for x in rows)},
       "rows":rows,"historically_verified_source_claims_not_inferred":True,
       "model_promoted":False,"betting_status":"PASS_UNVALIDATED","safe_for_betting":False}
def run(expected_path,worklist_path,output,csv_output=None):
    expected=json.loads(Path(expected_path).read_text())
    worklist=json.loads(Path(worklist_path).read_text())
    result=build(expected,worklist,dt.datetime.now(dt.timezone.utc).isoformat())
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    if csv_output:
        p=Path(csv_output);p.parent.mkdir(parents=True,exist_ok=True)
        data=[{**r,"priority":".".join(map(str,r["priority"]))} for r in result["rows"]]
        with p.open("w",newline="",encoding="utf-8") as f:
            if data:
                writer=csv.DictWriter(f,fieldnames=data[0].keys())
                writer.writeheader();writer.writerows(data)
    print(json.dumps(result["summary"]))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for f in ("expected","worklist","output"):p.add_argument("--"+f,required=True)
    p.add_argument("--csv");a=p.parse_args()
    run(a.expected,a.worklist,a.output,a.csv)

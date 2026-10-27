"""Persist point-in-time official QB source watch audits to the context-state branch.

Only machine screening and file fingerprints are archived. No QB1 claims,
retroactively changed predictions, or unauthenticated source-publication times.
Each GitHub Actions run has its own immutable archive path.
"""
import argparse,datetime as dt,hashlib,json,os
from pathlib import Path
from scripts import context_archive as store
from scripts.personnel_results_archive import _commit_material
from scripts.game_context import parse_time

STATUS="QB_OFFICIAL_SOURCE_WATCH_IMMUTABLE_RESEARCH_ONLY"
ROOT="research_2026/qb_source_watch"
MAX_CAPTURE_LAG_SECONDS=1800
def plan(html,notes,now,run_id):
    if not str(run_id).isdigit():raise ValueError("GitHub workflow ID missing")
    if html.get("status")!="OFFICIAL_GAMEWEEK_QB_LANGUAGE_REVIEW_ONLY" or notes.get("status")!="OFFICIAL_QB_NOTES_DOCUMENT_REVIEW_ONLY":
        raise ValueError("Unexpected official-source audit kind")
    for payload,group in ((html,"html"),(notes,"notes")):
        if payload.get("season")!=2026 or payload.get("betting_status")!="PASS_UNVALIDATED" or payload.get("model_predictions_modified") is not False:
            raise ValueError("Untrusted research-only source audit")
        if not isinstance(payload.get("entries"),list) or not isinstance(payload.get("summary"),dict):
            raise ValueError("Incomplete source audit")
        captured=parse_time(payload["captured_at_utc"])
        if captured>now or (now-captured).total_seconds()>MAX_CAPTURE_LAG_SECONDS:
            raise ValueError("Source audit not freshly observed")
        if group=="html" and payload.get("confirmed_starters_added")!=0:
            raise ValueError("Scraping cannot confirm a starter")
        if group=="notes" and payload.get("official_starting_qb_confirmations")!=0:
            raise ValueError("PDF keyword search cannot confirm QB1")
        seen=set()
        for row in payload["entries"]:
            key=(str(row["game_id"]),row["team"])
            if key in seen:raise ValueError("Duplicated source observation")
            seen.add(key)
            if row.get("confirmed_starter") is not False or row.get("status")!="REVIEW_ONLY_NOT_CONFIRMED":
                raise ValueError("A source snippet was silently promoted")
            if not str(row.get("source_url","")).startswith("https://"):
                raise ValueError("Missing approved source URL")
            if parse_time(row["kickoff_utc"])<=captured:
                raise ValueError("Captured source after kickoff")
            if parse_time(row["captured_at_utc"])!=captured:
                raise ValueError("Mismatched source record capture time")
            sha=row.get("content_sha256")
            if sha is not None and (not isinstance(sha,str) or len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha)):
                raise ValueError("Invalid source fingerprint")
    capture=max(parse_time(html["captured_at_utc"]),parse_time(notes["captured_at_utc"]))
    return {"status":STATUS,"season":2026,"run_id":str(run_id),
        "archive_created_at_utc":now.isoformat(),"latest_source_capture_utc":capture.isoformat(),
        "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
        "official_starting_qb_confirmations":0,"model_predictions_modified":False,
        "source_publication_times_independently_verified":False,
        "html_sha256":hashlib.sha256(store.encode(html)).hexdigest(),
        "pdf_review_sha256":hashlib.sha256(store.encode(notes)).hexdigest(),
        "summary":{"html":html["summary"],"pdf":notes["summary"],
                   "full_text_source_rows":html["summary"].get("full_articles_fetched",0)+notes["summary"].get("direct_pdf_extracted",0),
                   "verified_starter_game_slots":0},
        "html_observations":html["entries"],"official_pdf_observations":notes["entries"],
        "warning":"Immutable historical source-capture audit, NOT authenticated report publication time, source approval, or pregame starting QB evidence."}

def archive(report):
    if report["status"]!=STATUS:raise ValueError("Not a source watch research archive")
    stamp=parse_time(report["latest_source_capture_utc"])
    path=ROOT+"/"+stamp.strftime("%Y/%m/%d")+"/run-"+report["run_id"]+".json.gz"
    blob=store.pack(report)
    old=store.get_blob_file(path)
    if old is not None:
        if old!=blob:raise ValueError("Immutable source watch collision")
        return {"status":"ALREADY_ARCHIVED","path":path,"summary":report["summary"]}
    sha=_commit_material({path:blob},report["run_id"])
    return {"status":"ARCHIVED","path":path,"github_commit_sha":sha,"summary":report["summary"]}

def run(html_path,notes_path,run_id=None,now=None,persist=True):
    now=now or dt.datetime.now(dt.timezone.utc)
    run_id=run_id or os.environ.get("GITHUB_RUN_ID","")
    html=json.loads(Path(html_path).read_text(encoding="utf-8"))
    notes=json.loads(Path(notes_path).read_text(encoding="utf-8"))
    snapshot=plan(html,notes,now,run_id)
    return archive(snapshot) if persist else snapshot

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--html",required=True)
    p.add_argument("--notes",required=True)
    args=p.parse_args()
    print(json.dumps(run(args.html,args.notes),sort_keys=True))

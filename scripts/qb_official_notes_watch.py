"""Read-only game-week OFFICIAL direct PDF notes screening.

A note's position depth chart, an appearance, or keyword mention is NOT
a school declaration of the starter for this particular game. No picks update.
"""
import argparse,csv,datetime as dt,hashlib,io,json,re,urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from scripts.qb_gameweek_watch import QB,START,INJURY,passages,safe

STATUS="OFFICIAL_QB_NOTES_DOCUMENT_REVIEW_ONLY"
MAX_BYTES=16_000_000
MAX_PAGES=100

def trusted_notes(url,publisher):
    if not url or not safe(url) or not safe(publisher):return False
    src=urlsplit(url);host=urlsplit(publisher).hostname
    if src.hostname==host:return True
    return src.hostname=="s3.us-east-2.amazonaws.com" and src.path.startswith("/sidearm.nextgen.sites/"+host+"/documents/2026/")

def get_notes(url):
    if not safe(url):raise ValueError("Source URL not trusted")
    req=urllib.request.Request(url,headers={"User-Agent":"CFB-2026-Official-Football-Notes-Watch/0.1","Accept":"application/pdf"})
    with urllib.request.urlopen(req,timeout=16) as r:
        final=r.geturl()
        mime=r.headers.get("Content-Type","")
        body=r.read(MAX_BYTES+1)
    if len(body)>MAX_BYTES:raise ValueError("Game notes exceed bounded filesize")
    if not safe(final) or urlsplit(final).hostname!=urlsplit(url).hostname:
        raise ValueError("Game notes redirect away from source publisher")
    return body,mime

def pages_text(raw):
    # Import lazily so source matching and synthetic tests do not need pypdf.
    from pypdf import PdfReader
    pdf=PdfReader(io.BytesIO(raw),strict=False)
    if pdf.is_encrypted:raise ValueError("Encrypted game notes cannot be reviewed")
    if len(pdf.pages)>MAX_PAGES:raise ValueError("Official notes have too many pages")
    chunks=[]
    for page in pdf.pages:
        value=page.extract_text(extraction_mode="plain") or ""
        chunks.append(" ".join(value.split())[:15000])
    return " ".join(chunks)[:350000],len(pdf.pages)

def observe(config,now,fetcher=get_notes,extractor=pages_text,previous=None):
    if (config.get("status")!="REVIEWED_OFFICIAL_GAMEWEEK_LINKS_NOT_QB_STARTERS"
        or config.get("season")!=2026 or not isinstance(config.get("entries"),list)
        or now.tzinfo is None):raise ValueError("Unapproved game-week source registry")
    prior={(str(e["game_id"]),e["team"]):e for e in previous.get("entries",[])} if isinstance(previous,dict) and previous.get("status")==STATUS else {}
    seen=set();rows=[]
    for e in config["entries"]:
        key=(str(e["game_id"]),e["team"])
        if key in seen:raise ValueError("Duplicated game-school notes")
        seen.add(key)
        if e.get("starter_confirmed") is not False or e.get("evidence_type")!="OFFICIAL_GAMEWEEK_PREVIEW_NO_QB1_CLAIM":raise ValueError("Not a reviewed non-starter source")
        kickoff=dt.datetime.fromisoformat(e["kickoff_utc"].replace("Z","+00:00"))
        if kickoff<=now:continue
        url=e.get("game_notes_url")
        if not url:continue
        if not trusted_notes(url,e["preview_url"]):raise ValueError("Wrong university game note host")
        row={"game_id":key[0],"team":key[1],"opponent":e["opponent"],"kickoff_utc":e["kickoff_utc"],
             "source_url":url,"captured_at_utc":now.isoformat(),
             "status":"REVIEW_ONLY_NOT_CONFIRMED","confirmed_starter":False,
             "source_read_status":"PENDING","source_change":"UNKNOWN",
             "content_sha256":None,"total_pdf_pages":None,
             "possible_qb1_language":[],"qb_injury_language":[],"source_publication_time_attested":False}
        try:
            raw,mime=fetcher(url)
            if len(raw)>MAX_BYTES:raise ValueError("Oversize fetched game notes")
            if not raw.startswith(b"%PDF-"):
                row["source_read_status"]="NOT_DIRECT_PDF_LANDING_PAGE"
                row["source_change"]="NO_COMPARABLE_PDF_BYTES"
            else:
                if "pdf" not in mime.lower() and "octet-stream" not in mime.lower():
                    raise ValueError("Mismatched PDF response MIME")
                text,pages=extractor(raw)
                if not 1<=pages<=MAX_PAGES:raise ValueError("Implausible PDF page count")
                row["total_pdf_pages"]=pages
                row["source_read_status"]="DIRECT_PDF_TEXT" if len(text)>=100 else "DIRECT_PDF_NO_SEARCHABLE_TEXT"
                if row["source_read_status"]=="DIRECT_PDF_TEXT":
                    # A document fingerprint captures changes, not verified time of the claimed event.
                    sha=hashlib.sha256(raw).hexdigest()
                    row["content_sha256"]=sha
                    last=prior.get(key,{}).get("content_sha256")
                    row["source_change"]="FIRST_CAPTURE" if not last else "UNCHANGED" if last==sha else "CHANGED_REVIEW_REQUIRED"
                    row["possible_qb1_language"]=passages(text,START)
                    row["qb_injury_language"]=passages(text,INJURY) if QB.search(text) else []
                else:row["source_change"]="PDF_TEXT_EXTRACTION_UNSUPPORTED"
        except (ValueError,OSError,EOFError) as exc:
            row["source_read_status"]="FETCH_OR_PARSE_FAILED";row["source_change"]="UNKNOWN_FETCH_FAILED"
            row["error_kind"]=type(exc).__name__;row["error_reason"]=str(exc)[:130]
        rows.append(row)
    counts={"official_game_note_urls":len(rows),
            "direct_pdf_extracted":sum(x["source_read_status"]=="DIRECT_PDF_TEXT" for x in rows),
            "pdf_landing_pages":sum(x["source_read_status"]=="NOT_DIRECT_PDF_LANDING_PAGE" for x in rows),
            "unreadable":sum(x["source_read_status"] in ("FETCH_OR_PARSE_FAILED","DIRECT_PDF_NO_SEARCHABLE_TEXT") for x in rows),
            "changed":sum(x["source_change"]=="CHANGED_REVIEW_REQUIRED" for x in rows),
            "keyword_candidates":sum(bool(x["possible_qb1_language"]) for x in rows)}
    return {"status":STATUS,"season":2026,"captured_at_utc":now.isoformat(),
            "betting_status":"PASS_UNVALIDATED","safe_for_betting":False,
            "official_starting_qb_confirmations":0,"model_predictions_modified":False,
            "report_health":"NO_DIRECT_PDF_TEXT" if rows and not counts["direct_pdf_extracted"] else "PARTIAL" if counts["unreadable"] or counts["pdf_landing_pages"] else "OK",
            "summary":counts,"entries":rows,
            "warning":"Game notes and depth positions are NOT confirmed starters; a qualified reviewer must validate explicit game-specific assertions and timestamps."}

def run(config_file,output,previous_file=None,csv_file=None):
    data=json.loads(Path(config_file).read_text())
    previous=json.loads(Path(previous_file).read_text()) if previous_file and Path(previous_file).exists() else None
    report=observe(data,dt.datetime.now(dt.timezone.utc),previous=previous)
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    if csv_file:
        fields=("game_id","team","opponent","kickoff_utc","source_url","source_read_status","source_change","total_pdf_pages","possible_qb1_language","qb_injury_language")
        with Path(csv_file).open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for item in report["entries"]:
                w.writerow({k:" | ".join(item[k]) if k.endswith("_language") else item.get(k) for k in fields})
    print(json.dumps(report["summary"],sort_keys=True))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--config",required=True);p.add_argument("--output",required=True)
    p.add_argument("--previous");p.add_argument("--csv");a=p.parse_args()
    run(a.config,a.output,a.previous,a.csv)

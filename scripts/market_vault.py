"""Append-only, LOCAL ONLY, research quote vault. SQLite file is not encrypted.

This module never publishes prices to a public GitHub branch or CI artifact.
The vault path must resolve strictly outside the checked-out repository.
"""
import datetime as dt
import hashlib
import json
import os
import sqlite3
import stat
from pathlib import Path
from scripts.game_context import parse_time

ROOT=Path(__file__).resolve().parent.parent
DB_VERSION=1

def default_path():
    return Path.home()/".local"/"share"/"cfb-model"/"market_quotes.sqlite3"

def safe_path(path,create=False):
    p=Path(path).expanduser()
    if not p.is_absolute():raise ValueError("Use an absolute private vault path")
    if p.is_symlink():raise ValueError("Refusing symlink vault")
    resolved=p.resolve()
    if resolved==ROOT or ROOT in resolved.parents:
        raise ValueError("Market quote history must be outside public repository")
    if resolved.exists() and (not resolved.is_file() or not stat.S_ISREG(resolved.stat().st_mode)):
        raise ValueError("Quote vault must be a regular file")
    if create and not resolved.parent.exists():
        resolved.parent.mkdir(parents=True,mode=0o700)
    if create:
        if resolved.parent.is_symlink():
            raise ValueError("Refusing symlink directory")
        if stat.S_IMODE(resolved.parent.stat().st_mode)&0o077:
            raise PermissionError("Vault directory must be private (chmod 700)")
        if not resolved.exists():
            fd=os.open(str(resolved),os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
            os.close(fd)
    if resolved.exists() and stat.S_IMODE(resolved.stat().st_mode)&0o077:
        raise PermissionError("Vault file must be private (chmod 600)")
    return resolved

SCHEMA="""
CREATE TABLE IF NOT EXISTS snapshots(
    snapshot_id TEXT PRIMARY KEY,
    source_snapshot_sha256 TEXT NOT NULL,
    provider TEXT NOT NULL,
    observed_at_utc TEXT NOT NULL,
    retrieved_at_utc TEXT NOT NULL,
    kind TEXT NOT NULL,
    bookmaker_keys_json TEXT NOT NULL,
    quote_count INTEGER NOT NULL,
    quarantine_count INTEGER NOT NULL,
    credits_remaining INTEGER,
    credits_used_total INTEGER,
    credits_last INTEGER,
    created_at_utc TEXT NOT NULL,
    betting_status TEXT NOT NULL CHECK(betting_status='PASS_UNVALIDATED')
);
CREATE TABLE IF NOT EXISTS quotes(
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    event_id TEXT NOT NULL,
    bookmaker TEXT NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    line_points REAL,
    american_odds INTEGER NOT NULL,
    home_team_source TEXT NOT NULL,
    away_team_source TEXT NOT NULL,
    kickoff_utc TEXT NOT NULL,
    observed_at_utc TEXT NOT NULL,
    retrieved_at_utc TEXT NOT NULL,
    provider_last_update_utc TEXT,
    PRIMARY KEY(snapshot_id,event_id,bookmaker,market,selection)
);
CREATE INDEX IF NOT EXISTS quotes_lookup
ON quotes(event_id,bookmaker,market,selection,observed_at_utc);
CREATE TRIGGER IF NOT EXISTS no_update_quotes
BEFORE UPDATE ON quotes BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_quotes
BEFORE DELETE ON quotes BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_update_snapshots
BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_snapshots
BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT,'append-only'); END;
"""

def connect(path,create=False):
    p=safe_path(path,create)
    if not p.exists():raise FileNotFoundError("Private market quote vault does not exist")
    db=sqlite3.connect(str(p),timeout=15)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=DELETE")
    db.executescript(SCHEMA)
    return db

def validate(bundle):
    if bundle.get("betting_status")!="PASS_UNVALIDATED" or bundle.get("safe_for_betting") is not False:
        raise ValueError("Only unvalidated source research may enter market vault")
    sourcehash=bundle.get("source_snapshot_sha256")
    if not isinstance(sourcehash,str) or len(sourcehash)!=64:
        raise ValueError("Missing provider source checksum")
    try:int(sourcehash,16)
    except ValueError:raise ValueError("Invalid source checksum") from None
    observed=parse_time(bundle["observed_at_utc"])
    retrieved=parse_time(bundle["retrieved_at_utc"])
    if observed>retrieved:raise ValueError("Snapshot from the future")
    rows=bundle.get("quotes")
    if not isinstance(rows,list):raise ValueError("Missing normalized market quotes")
    seen=set()
    for row in rows:
        if row.get("snapshot_sha256")!=sourcehash or row.get("betting_status")!="PASS_UNVALIDATED":
            raise ValueError("Quote and snapshot provenance mismatch")
        if row.get("match_status") not in ("UNMATCHED_PROVIDER_EVENT","MATCHED_ASOF","QUARANTINED"):
            raise ValueError("Unrecognized ESPN mapping status")
        for field in ("kickoff_utc","observed_at_utc","retrieved_at_utc"):
            parse_time(row[field])
        if parse_time(row["observed_at_utc"])!=observed or parse_time(row["retrieved_at_utc"])!=retrieved:
            raise ValueError("Quote has different source observation or retrieval time")
        if observed>=parse_time(row["kickoff_utc"]):
            raise ValueError("Post-kickoff quote is not pregame history")
        update=row.get("provider_last_update_utc")
        if update and parse_time(update)>observed:
            raise ValueError("Market update after observation")
        if row.get("quote_role")!="OBSERVED_NOT_AUTHENTICATED_OPEN_OR_CLOSE":
            raise ValueError("Unproven opening/closing quote role")
        if row.get("bookmaker") is None or row.get("market") not in ("SPREAD","TOTAL","MONEYLINE"):
            raise ValueError("Unsupported market or book")
        identity=(row["provider_event_id"],row["bookmaker"],row["market"],row["selection"])
        if identity in seen:raise ValueError("Duplicate quote in source snapshot")
        seen.add(identity)
    return observed,retrieved

def store(path,bundle,usage=None):
    """Idempotently archive a normalizer result and provider credit counters."""
    observed,retrieved=validate(bundle)
    sourcehash=bundle["source_snapshot_sha256"]
    books=sorted({q["bookmaker"] for q in bundle["quotes"]})
    digest=hashlib.sha256(json.dumps({
        "hash":sourcehash,"observed":observed.isoformat(),
        "retrieved":retrieved.isoformat(),"books":books},sort_keys=True).encode()).hexdigest()
    usage=usage or {}
    counts={key:usage.get(key) for key in ("x-requests-remaining","x-requests-used","x-requests-last")}
    if any(x is not None and (type(x) is not int or x<0) for x in counts.values()):
        raise ValueError("Invalid provider credit counters")
    db=connect(path,create=True)
    try:
        with db:
            before=db.execute("SELECT 1 FROM snapshots WHERE snapshot_id=?",(digest,)).fetchone()
            if before:
                return {"status":"DUPLICATE_SNAPSHOT","snapshots_added":0,"quotes_added":0,
                        "betting_status":"PASS_UNVALIDATED"}
            db.execute("""INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (digest,sourcehash,bundle.get("market_source","the-odds-api-v4"),
               observed.isoformat(),retrieved.isoformat(),
               "HISTORICAL" if observed!=retrieved else "LIVE_CAPTURE",
               json.dumps(books),len(bundle["quotes"]),len(bundle.get("rejected",[])),
               counts["x-requests-remaining"],counts["x-requests-used"],
               counts["x-requests-last"],
               dt.datetime.now(dt.timezone.utc).isoformat(),"PASS_UNVALIDATED"))
            for row in bundle["quotes"]:
                db.execute("""INSERT INTO quotes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (digest,str(row["provider_event_id"]),row["bookmaker"],row["market"],
                   row["selection"],row.get("line_points"),row["american_odds"],
                   row["home_team_source"],row["away_team_source"],row["kickoff_utc"],
                   row["observed_at_utc"],row["retrieved_at_utc"],
                   row.get("provider_last_update_utc")))
        return {"status":"SAVED_PRIVATE_SNAPSHOT","snapshots_added":1,
                "quotes_added":len(bundle["quotes"]),"betting_status":"PASS_UNVALIDATED"}
    finally:db.close()

def asof_quotes(path,event_id,bookmaker,market,selection,cutoff_utc,max_age_minutes=180):
    """Most recent observed pregame price; never label it executable."""
    if max_age_minutes<=0:raise ValueError("Invalid quote age limit")
    cutoff=parse_time(cutoff_utc)
    db=connect(path)
    try:
        records=db.execute("""SELECT line_points,american_odds,observed_at_utc,
                    retrieved_at_utc,kickoff_utc,provider_last_update_utc
                    FROM quotes WHERE event_id=? AND bookmaker=? AND market=?
                      AND selection=? ORDER BY observed_at_utc DESC""",
                    (event_id,bookmaker,market,selection)).fetchall()
    finally:db.close()
    found=[]
    for line,price,observed,retrieved,kickoff,update in records:
        o=parse_time(observed)
        if o<=cutoff and o<parse_time(kickoff):
            found.append((o,line,price,observed,retrieved,kickoff,update))
    if not found:return {"status":"NO_OBSERVED_QUOTE","betting_status":"PASS_UNVALIDATED"}
    best=max(found,key=lambda x:x[0])
    age=(cutoff-best[0]).total_seconds()/60
    return {"status":"OBSERVED_PRICE" if age<=max_age_minutes else "STALE_PRICE",
            "bookmaker":bookmaker,"provider_event_id":event_id,"market":market,
            "selection":selection,"line_points":best[1],"american_odds":best[2],
            "observed_at_utc":best[3],"retrieved_at_utc":best[4],
            "provider_last_update_utc":best[6],"quote_age_minutes":round(age,2),
            "price_executable_verified":False,"betting_status":"PASS_UNVALIDATED"}

def audit(path):
    db=connect(path)
    try:
        s=db.execute("SELECT COUNT(*),COUNT(DISTINCT source_snapshot_sha256) FROM snapshots").fetchone()
        q=db.execute("SELECT COUNT(*),COUNT(DISTINCT bookmaker) FROM quotes").fetchone()
        last=db.execute("SELECT MAX(observed_at_utc) FROM snapshots").fetchone()[0]
        return {"snapshots":s[0],"distinct_source_hashes":s[1],
                "quotes":q[0],"bookmakers":q[1],"latest_observed_utc":last,
                "safe_for_betting":False,"betting_status":"PASS_UNVALIDATED"}
    finally:db.close()

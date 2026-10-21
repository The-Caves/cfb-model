"""Live, pregame, official SEC/Big Ten student-athlete availability extraction.

Public structured publisher endpoints from official conference report embeds.
Only current reports, never historical archive, are accepted as pregame evidence.
The API provides statuses, NOT a starting-QB confirmation or injury diagnosis.
All failures and ambiguous joins quarantine player claims.
"""
import csv,datetime as dt,hashlib,json,re,urllib.request,urllib.error
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.game_context import parse_time
from scripts.availability_context import FIELDS

ROOT="https://app.hdintelligence.com"
PUBLISH_PATH="/api/get-publish-public"
CONFERENCES={"SEC":"SEC","B10":"B10"}
SOURCE_PAGE={
  "SEC":"https://www.secsports.com/fbreports",
  "B10":"https://bigten.org/sports/2026/9/10/FB_Availability_Reports.aspx"}
TIMEZONES={"CT":"America/Chicago","ET":"America/New_York",
           "MT":"America/Denver","PT":"America/Los_Angeles"}
STATUS_MAP={"Out":"OUT","Out - (1st Half)":"LIMITED",
 "Questionable":"QUESTIONABLE","Doubtful":"DOUBTFUL",
 "Probable":"PROBABLE","Game Time Decision":"GAME_TIME_DECISION",
 "Available":"AVAILABLE"}
POSITION_SET={"QB","RB","WR","TE","OL","DL","EDGE","LB","CB","S","K","P"}
GAME_DAY_FORMAT="%Y-%m-%d"
def request_public(conference,timeout=25,max_bytes=30_000_000):
    payload=json.dumps({"sport":"Football","organization":conference,"conference":conference}).encode()
    req=urllib.request.Request(ROOT+PUBLISH_PATH,method="POST",data=payload,headers={
        "Content-Type":"application/json","Accept":"application/json","Origin":ROOT,
        "User-Agent":"CFB-2026-Official-Public-Report-Ingest/0.1"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        raw=response.read(max_bytes+1)
    if len(raw)>max_bytes:raise ValueError("Public publisher payload over size limit")
    parsed=json.loads(raw)
    if not isinstance(parsed,dict):raise ValueError("Public publisher payload is not an object")
    return parsed,hashlib.sha256(raw).hexdigest()

def aliases_from_csv(file):
    with Path(file).open(newline="",encoding="utf-8-sig") as stream:
        records=list(csv.DictReader(stream))
    out={}
    for r in records:
        short=r["archived_team"].strip();long=r["espn_display_name"].strip()
        if not short or not long or short in out:raise ValueError("Invalid or duplicate canonical alias")
        out[short]=long
    # Explicit safe publisher spellings; all mapped to unique registered schools.
    for displayed,original in {"Ohio St.":"Ohio State","Penn St.":"Penn State",
                               "Michigan St.":"Michigan State","Miss. State":"Mississippi State",
                               "Miss St.":"Mississippi State","Ole Miss":"Ole Miss"}.items():
        if original in out:out[displayed]=out[original]
    return out

def published_timestamp(card):
    date=card.get("publishDate")
    clock=card.get("postedTime")
    tz=TIMEZONES.get(str(card.get("conferenceTimeZone") or "").upper())
    if not isinstance(date,str) or not isinstance(clock,str) or not tz:
        raise ValueError("Missing publisher date/time/timezone")
    local=dt.datetime.strptime(date+" "+clock,"%Y-%m-%d %H:%M:%S")
    return local.replace(tzinfo=ZoneInfo(tz)).astimezone(dt.timezone.utc)

def parse_player(row):
    if not isinstance(row,dict):raise ValueError("Invalid publisher player row")
    # Public football report card uses display name "QB #12 Player Name".
    raw=row.get("name")
    if not isinstance(raw,str) or not raw.strip():raise ValueError("Missing player display name")
    m=re.fullmatch(r"\s*([A-Za-z/-]+)\s+(?:#\d+\s+)?(.{2,100}?)\s*",raw)
    if m:
        position=m.group(1).upper().strip()
        player=m.group(2).strip()
    else:
        position="OTHER";player=raw.strip()
    if position not in POSITION_SET:position="OTHER"
    if len(player)<2 or len(player)>100:raise ValueError("Invalid player name")
    label=str(row.get("status") or "").strip()
    status=STATUS_MAP.get(label)
    if status is None:raise ValueError("Unsupported report designation: "+label[:50])
    return {"player":player,"position":position,"status":status,
            "official_status":label,"jersey_display":raw}

def eligible_report(card,received_at):
    if not isinstance(card,dict):return False,"SCHEMA_INVALID",None
    mode=str(card.get("ReportType") or "").strip()
    if not mode or "pending" in mode.lower():return False,"REPORT_PENDING",None
    if any(x in mode.lower() for x in ("cancel","unavailable","not posted","error","suspend")):
        return False,"REPORT_NOT_PUBLISHED",None
    try:published=published_timestamp(card)
    except (ValueError,TypeError):return False,"MISSING_PUBLICATION_TIME",None
    if published>received_at:return False,"PUBLISH_TIME_IN_FUTURE",published
    if (received_at-published).total_seconds()>36*3600:return False,"STALE_PUBLISHED_REPORT",published
    return True,"PUBLISHED",published

def game_for_card(card,games,aliases,now):
    sides=card.get("games")
    if not isinstance(sides,list) or len(sides)!=2:return None,"INVALID_TWO_TEAM_REPORT"
    short=[side.get("teamDisplayName") for side in sides]
    resolved=[aliases.get(s) if isinstance(s,str) else None for s in short]
    if not all(resolved) or resolved[0]==resolved[1]:return None,"TEAM_ALIAS_UNVERIFIED"
    d=(card.get("footer") or {}).get("date")
    try:day=dt.date.fromisoformat(d)
    except (ValueError,TypeError):return None,"MISSING_GAME_DATE"
    candidates=[g for g in games if g["date_et"]==day.isoformat()
      and {g["home"],g["away"]}==set(resolved)
      and parse_time(g["kickoff_utc"])>now]
    if len(candidates)!=1:return None,"NO_UNIQUE_ESPN_GAME_MATCH"
    return candidates[0],"MATCHED"

def extract(conference,feed,games,aliases,captured):
    """Transform a live public feed into timestamped, scoreboard-matched records."""
    now=parse_time(captured)
    records=[];meta={"conference":conference,"card_count":len(feed),"report_cards":[],"status":"FETCHED"}
    seen=set()
    for card_id,card in feed.items():
        report={"publisher_card_id":str(card_id),"type":str(card.get("ReportType","")) if isinstance(card,dict) else "",
                "source_url":SOURCE_PAGE[conference]}
        meta["report_cards"].append(report)
        g,match=game_for_card(card,games,aliases,now) if isinstance(card,dict) else (None,"INVALID_CARD")
        report["game_match"]=match
        if not g:continue
        report["game_id"]=g["game_id"]
        okay,reason,published=eligible_report(card,now)
        report["publication_status"]=reason
        if not okay:continue
        kickoff=parse_time(g["kickoff_utc"])
        if not published<now<kickoff:
            report["publication_status"]="POST_CUTOFF_OR_INVALID_TIMING";continue
        gamesides=card["games"]
        # Validate *all* relevant rows before attesting that either side
        # has a verified official report. Partial parsing must never count.
        parsed=[]
        for side in gamesides:
            team=aliases[side["teamDisplayName"]]
            rawrows=side.get("rows")
            if not isinstance(rawrows,list):
                report["publication_status"]="MISSING_TEAM_PLAYER_ROWS";parsed=[];break
            try:individual=[parse_player(r) for r in rawrows]
            except (ValueError,TypeError) as exc:
                report["publication_status"]="PLAYER_ROW_SCHEMA_ERROR"
                report["error"]=str(exc)[:140];parsed=[];break
            parsed.append((team,individual))
        if len(parsed)!=2:continue
        signature=(str(g["game_id"]),published.isoformat())
        if signature in seen:
            report["publication_status"]="DUPLICATE_GAME_REPORT";continue
        seen.add(signature)
        t=published.isoformat().replace("+00:00","Z")
        captured_iso=now.isoformat().replace("+00:00","Z")
        for team,players in parsed:
            base={"season":"2026","game_id":str(g["game_id"]),"team":team,
                 "kickoff_utc":g["kickoff_utc"],"published_at_utc":t,
                 "captured_at_utc":captured_iso,"source_url":SOURCE_PAGE[conference],
                 "reviewed_by":"AUTOMATED_OFFICIAL_PUBLISHER_STRUCTURED"}
            records.append({**base,"kind":"TEAM_REPORT","player":"ALL","position":"TEAM","status":"VERIFIED"})
            for p in players:
                records.append({**base,"kind":"AVAILABILITY","player":p["player"],
                                "position":p["position"],"status":p["status"]})
        report["publication_status"]="ACCEPTED_VERIFIED_OFFICIAL_REPORT"
        report["player_rows"]=sum(len(players) for _,players in parsed)
        report["published_utc"]=t
    meta["official_reports_accepted"]=sum(x.get("publication_status")=="ACCEPTED_VERIFIED_OFFICIAL_REPORT" for x in meta["report_cards"])
    meta["player_records"]=sum(x["kind"]=="AVAILABILITY" for x in records)
    meta["pending_cards"]=sum(x.get("publication_status")=="REPORT_PENDING" for x in meta["report_cards"])
    return records,meta

def fetch_and_match(upcoming,aliases_file,output,now=None,fetcher=request_public):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    aliases=aliases_from_csv(aliases_file)
    result={"fetched_at_utc":None,"feeds":{},"betting_status":"PASS_UNVALIDATED",
        "official_statuses_are_not_qb_starter_confirmations":True,
        "injury_diagnoses_included":False}
    allrows=[]
    for conf in CONFERENCES:
        try:
            data,sha=fetcher(conf)
            stamp=dt.datetime.now(dt.timezone.utc)
            records,meta=extract(conf,data,upcoming,aliases,stamp.isoformat())
            meta["sha256"]=sha
            meta["fetched_at_utc"]=stamp.isoformat()
            allrows.extend(records)
        except Exception as exc:
            meta={"status":"OFFICIAL_FEED_UNAVAILABLE","error":str(exc)[:230]}
        result["feeds"][conf]=meta
    timestamp=dt.datetime.now(dt.timezone.utc).isoformat()
    result["fetched_at_utc"]=timestamp
    result["records"]=len(allrows)
    result["official_game_reports"]=sum(v.get("official_reports_accepted",0) for v in result["feeds"].values())
    result["player_designations"]=sum(v.get("player_records",0) for v in result["feeds"].values())
    result["errors"]=sum(v.get("status")=="OFFICIAL_FEED_UNAVAILABLE" for v in result["feeds"].values())
    with (out/"availability_verified_2026.csv").open("w",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(allrows)
    (out/"official_availability_manifest.json").write_text(json.dumps(result,indent=2)+"\n")
    return allrows,result
